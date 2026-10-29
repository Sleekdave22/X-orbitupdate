'use strict';
/** Exercise the actual browser send handler against failed/uncertain transport. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Element,walk,content}=require('./browser-test-dom.cjs');
const page=fs.readFileSync(__dirname+'/index.html','utf8');
const handler=page.slice(page.indexOf("async function send(text=''") ,page.indexOf('function inlineVisible'));

/** Build an isolated composer; never contacts a server or reads account storage. */
function fixture(){
 const nodes=new Map(),rows=new Map(),calls=[];let nextError=new Error('Offline'),wait=null;
 const el=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
 el('once').checked=true;el('previewOnce').checked=true;el('draft').value='Original';
 const context={busy:false,chatVersion:1,peer:{id:'recipient'},account:{id:'sender',token:'fixture-session'},replyTarget:{id:7},
  globalThis:{crypto:{randomUUID:()=> 'stable-send-key'}},document:{createElement:tag=>new Element(tag)},window:{},
  el,pendingRows:rows,clearReply(){context.replyTarget=null},groupSenderLabels(){},messages(){context.refreshes++},error(){},refreshes:0,
  makePending(text,file,client){const row=new Element(),dot=new Element();dot.className='delivery-status';row.append(dot);row.querySelector=selector=>walk(row).find(n=>selector==='.delivery-status'?n===dot:n.className==='send-failure');el('messages').append(row);rows.set(client,row);return row},
  paintReceipt(dot,data,sending=false){dot.state=data.failed?'failed':sending?'sending':'sent'},
  FileReader:class {readAsDataURL(file){this.result='data:'+file.type+';base64,'+file.data;this.onload()}},
  async api(path,body){calls.push({path,body});if(wait)await wait;if(nextError)throw nextError;return {id:12}},
 };
 vm.createContext(context);vm.runInContext(handler,context);
 return {context,el,calls,rows,succeed(){nextError=null},pause(){wait=new Promise(resolve=>this.release=()=>{wait=null;resolve()})},button(label){return walk(el('messages')).find(n=>n.tagName==='BUTTON'&&n.textContent===label)}};
}

(async()=>{
 const f=fixture();await f.context.send('Original');
 assert.equal(f.rows.size,1);assert.equal(f.el('messages').children[0].querySelector('.delivery-status').state,'failed');
 assert.match(content(f.el('messages')),/Not sent · Offline/);assert.equal(f.el('draft').value,'Original');assert.equal(f.context.busy,false);
 const retry=f.button('Retry'),original=JSON.stringify(f.calls[0]);
 f.context.replyTarget={id:42};f.el('draft').value='A newer draft';f.succeed();f.pause();
 const sending=retry.onclick();await retry.onclick();assert.equal(f.calls.length,2,'Double retry taps make one request');
 f.release();await sending;
 assert.equal(JSON.stringify(f.calls[1]),original,'Retry retains peer, caption, reply, privacy and client ID');
 assert.equal(f.el('draft').value,'A newer draft');assert.equal(f.context.replyTarget.id,42,'Do not erase a newer reply selection');
 assert.equal(f.context.refreshes,1);await retry.onclick();assert.equal(f.calls.length,2,'Successful action cannot be resubmitted');

 for(const changed of ['account','peer','chatVersion']){
  const f=fixture();await f.context.send('Original');f.succeed();
  if(changed==='account')f.context.account={id:'another',token:'another-session'};
  if(changed==='peer')f.context.peer={id:'someone-else'};
  if(changed==='chatVersion')f.context.chatVersion++;
  await f.button('Retry').onclick();assert.equal(f.calls.length,1,changed+' cannot send a stale preview');
 }

 const file=fixture();await file.context.send('Original',{size:8,type:'image/png',name:'photo.png',data:'cGhvdG8='});
 file.succeed();await file.button('Retry').onclick();
 assert.equal(JSON.stringify(file.calls[1]),JSON.stringify(file.calls[0]),'Attachment retry keeps original bytes/metadata');
 assert.equal(file.el('draft').value,'');assert.equal(file.el('once').checked,false);
 const discarded=fixture();await discarded.context.send('Original');discarded.button('Remove unsent preview').onclick();assert.equal(discarded.rows.size,0);assert.equal(discarded.el('messages').children.length,0);

 const departed=fixture();departed.succeed();departed.pause();const sendingAway=departed.context.send('Original');
 departed.context.chatVersion++;departed.el('draft').value='Another conversation';departed.release();await sendingAway;
 assert.equal(departed.el('draft').value,'Another conversation');assert.equal(departed.context.refreshes,0);
 console.log('Failed sends, stable retry IDs/bytes, duplicate taps, stale sessions/chats, new drafts/replies and preview discard passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
