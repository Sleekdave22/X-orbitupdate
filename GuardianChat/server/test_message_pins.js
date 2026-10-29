'use strict';
/** Pin UI tests use the production module with disposable DOM and transport. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Element,walk,content}=require('./browser-test-dom.cjs');
class Node extends Element{
 addEventListener(){}
 showModal(){this.open=true}
 close(){this.open=false}
}
const body=new Node(),bar=new Node();let context={owner:'a',peer:'b',version:1},lastError='',requests=[],resolve;
const runtime={window:{},document:{body,createElement:tag=>new Node(tag)}};
vm.createContext(runtime);vm.runInContext(fs.readFileSync(__dirname+'/message-pins.js','utf8'),runtime);
let jumped=0;
const pins=runtime.window.OrbitMessagePins.create({bar,current:()=>context,jump:id=>jumped=id,error:e=>lastError=e,
 api:async(path,data)=>{requests.push({path,data});return new Promise(done=>resolve=done)}});
const first={id:12,preview:'<img onerror="bad">',name:'Author'},second={id:11,preview:'Protected media',name:'Reader'};
pins.render([first,second],context);assert.equal(bar.hidden,false);assert.match(content(bar),/<img onerror/);assert.equal(walk(bar).filter(n=>n.tagName==='IMG').length,0);
const preview=bar.children[0];pins.render([first,second],context);assert.equal(bar.children[0],preview,'Unchanged polls preserve existing focus/layout');
preview.onclick();assert.equal(jumped,12);
bar.children[1].onclick();assert.equal(body.children.at(-1).open,true);assert.match(content(body),/Author/);assert.match(content(body),/Protected media/);
(async()=>{
 const action=pins.toggle(first);await pins.toggle(first);assert.equal(requests.length,1);assert.equal(requests[0].data.pinned,false);
 resolve({pins:[second]});await action;assert.equal(pins.has(12),false);assert.equal(body.children.length,0);
 const stale=bar.children[0];context={owner:'other',peer:'b',version:2};stale.onclick();assert.equal(jumped,12,'Stale preview cannot navigate a new account');
 pins.render([first],{owner:'a',peer:'b',version:1});assert.equal(pins.has(12),false);
 const pending=pins.toggle(first);context={owner:'other',peer:'c',version:3};resolve({pins:[first]});await pending;assert.equal(pins.has(12),false,'Late response cannot populate another conversation');
 pins.reset();assert.equal(bar.hidden,true);assert.equal(bar.children.length,0);assert.equal(lastError,'');
 console.log('Pin previews/list navigation, text-only rendering, stable polls, duplicate edits and stale-account/chat isolation passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
