const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag,text=''){this.tagName=tag;this.textContent=text;this.children=[];this.style={};this.dataset={};this.value='';this.disabled=false}
 append(...items){this.children.push(...items)}replaceChildren(...items){this.children=items}
 querySelectorAll(selector){return flatten(this).filter(x=>selector==='input[type=password]'&&x.tagName==='input'&&x.type==='password')}
}
const flatten=e=>[e,...e.children.flatMap(flatten)],elements={walletView:new Element('section'),walletStatus:new Element('p'),walletBack:new Element('button')},events={},requests=[];let delayed=null,delayQuote=false;
const summary={mode:'test',id:'fixture-wallet',status:'active_test',available_kobo:50000,reserved_kobo:0,finance_overview:false,transfer_limit_kobo:1000000,daily_limit_kobo:5000000};
const context=vm.createContext({document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},window:{addEventListener:(n,fn)=>events[n]=fn},localStorage:{getItem:()=>JSON.stringify({id:'fixture-owner',token:'fixture-token'})},location:{assign(){},reload(){}},Intl,Date,crypto:{randomUUID:()=> 'test-ui-idempotency-key'},fetch:async(path,init)=>{
 const body=init.body?JSON.parse(init.body):null;requests.push({path,body});let data=path.includes('/summary')?summary:path.includes('/history')?{mode:'test',transactions:[]}:path.includes('/quote')?{mode:'test',quote:'fixed-quote',recipient:{id:'fixed-recipient',name:'Recipient',nickname:'recipient'},amount_kobo:body.amount_kobo,fee_kobo:0,currency:'NGN'}:{mode:'test',reference:'test-receipt'};
 if(delayQuote&&path.includes('/quote'))await new Promise(resolve=>delayed=resolve);
 return {ok:true,json:async()=>data};
}});
const button=text=>flatten(elements.walletView).find(x=>x.tagName==='button'&&x.textContent===text),field=label=>flatten(elements.walletView).find(x=>x.tagName==='label'&&x.textContent===label).children[0],form=()=>flatten(elements.walletView).find(x=>x.tagName==='form'),event={preventDefault(){}};
(async()=>{
 vm.runInContext(fs.readFileSync(__dirname+'/wallet.js','utf8'),context);await new Promise(setImmediate);
 for(const name of ['Add Money','Withdraw','Payment Methods']){assert(button(name).disabled);assert.match(button(name).dataset.help,/Unavailable/)}
 button('Send test funds').onclick();field('Recipient @nickname or X ORBIT ID').value='@recipient';field('Amount in test NGN').value='1.01';await form().onsubmit(event);assert.equal(requests.at(-1).body.amount_kobo,101);
 field('Account password').value='fixture-password';const cancel=button('Cancel'),send=button('Confirm and send test funds'),pending=form().onsubmit(event);assert(cancel.disabled);assert(send.disabled);await pending;assert.match(elements.walletStatus.textContent,/Test transfer posted/);
 const transfer=requests.find(r=>r.path.includes('/transfer'));assert.equal(transfer.body.quote,'fixed-quote');assert.equal(transfer.body.idempotency_key,'test-ui-idempotency-key');assert(!JSON.stringify(summary).includes('fixture-password'));
 button('Send test funds').onclick();field('Recipient @nickname or X ORBIT ID').value='@recipient';field('Amount in test NGN').value='1e4';await form().onsubmit(event);assert.match(elements.walletStatus.textContent,/two decimal places/);
 field('Amount in test NGN').value='2.00';delayQuote=true;const stale=form().onsubmit(event);events.storage({key:'guardianchat-account'});assert.equal(elements.walletView.children.length,0);delayed();await stale;assert.equal(elements.walletView.children.length,0);assert.match(elements.walletStatus.textContent,/Account changed/);
 console.log('Test wallet disabled services, exact kobo parsing, bound confirmation, submission locking and account-switch response isolation passed');
})().catch(e=>{console.error(e);process.exitCode=1});
