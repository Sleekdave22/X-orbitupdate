'use strict';
/** Request controls use actual module code with a synthetic account and transport. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Element,walk,content}=require('./browser-test-dom.cjs');
class Node extends Element{
 get childElementCount(){return this.children.length}
 addEventListener(){}
 showModal(){this.open=true}
 close(){this.open=false}
 focus(){}
}
const body=new Node(),requests=[];let owner='recipient',refreshed=0,feedback='',fail=false;
const runtime={window:{},crypto:{randomUUID:()=> 'stable-key'},document:{body,createElement:tag=>new Node(tag)}};
vm.createContext(runtime);vm.runInContext(fs.readFileSync(__dirname+'/message-requests.js','utf8'),runtime);
const api=async(path,data)=>{requests.push({path,data});if(fail)throw Error('Offline');return {state:'pending'}};
const services={api,current:()=>owner,refresh:async()=>refreshed++,error:e=>feedback=e};
const row=new Node();runtime.window.OrbitMessageRequests.mount(row,{id:'sender',previews:[{text:'<img onerror="bad">'}]},services);
assert.match(content(row),/<img onerror/);assert.equal(walk(row).filter(n=>n.tagName==='IMG').length,0);
const button=(root,text)=>walk(root).find(n=>n.tagName==='BUTTON'&&n.textContent===text);
(async()=>{
 await button(row,'Decline').onclick();assert.equal(requests[0].path,'/social/message_decline');assert.equal(refreshed,1);
 await button(row,'Decline & Block').onclick();assert.equal(requests[1].path,'/social/message_decline_block');
 button(row,'Report').onclick();const reason=walk(row).find(n=>n.tagName==='TEXTAREA');reason.value='Test report reason';
 await button(row,'Submit report').onclick();assert.equal(requests.at(-1).path,'/social/message_report');assert.equal(requests.length,3,'Report has no implicit decline/block');
 owner='other-account';await button(row,'Accept').onclick();assert.equal(requests.length,3,'Stale recipient cannot accept another account’s request');
 const dialog=runtime.window.OrbitMessageRequests.compose('target',{api,current:()=>owner});
 const introduction=walk(dialog).find(n=>n.tagName==='TEXTAREA');introduction.value='Introduction';fail=true;
 await button(dialog,'Send request').onclick();assert.match(content(dialog),/Offline/);assert.equal(button(dialog,'Send request').hidden,false);
 const original=JSON.stringify(requests.at(-1));fail=false;await button(dialog,'Send request').onclick();assert.equal(JSON.stringify(requests.at(-1)),original,'Retry retains intro text/recipient/client key');assert.match(content(dialog),/awaiting acceptance/);
 assert.equal(feedback,'');console.log('Private request previews, accept/decline/block/report separation, stale-account guards and introduction retry passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
