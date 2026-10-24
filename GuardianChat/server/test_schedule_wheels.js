const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element{
 constructor(tag,text='',cls=''){this.tagName=tag.toUpperCase();this.textContent=text;this.className=cls;this.children=[];this.attrs={};this.dataset={};this.scrollTop=0;this.type=tag==='button'?'submit':'';this.listeners={}}
 append(...items){for(const item of items){item.parent=this;this.children.push(item)}}
 replaceChildren(...items){this.children=[];this.append(...items)}
 setAttribute(k,v){this.attrs[k]=String(v)}
 showModal(){this.open=true}focus(){}addEventListener(n,f){this.listeners[n]=f}
 close(){this.open=false;this.listeners.close?.()}remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this)}
}
const document={body:new Element('body'),head:new Element('head'),getElementById(id){return document.head.children.find(x=>x.id===id)}};
const context=vm.createContext({document,window:{},Date,Intl,URLSearchParams,setTimeout,clearTimeout,node:(...x)=>new Element(...x),button:(text,fn)=>{let e=new Element('button',text);e.onclick=fn;return e}});
vm.runInContext(fs.readFileSync(__dirname+'/scheduling.js','utf8'),context);
const all=e=>[e,...e.children.flatMap(all)],current=()=>document.body.children.at(-1),wheel=name=>all(current()).find(e=>e.attrs.role==='listbox'&&e.attrs['aria-label']===name),click=text=>all(current()).find(e=>e.tagName==='BUTTON'&&e.textContent===text).onclick();
let saved=null;
context.scheduleWheelPicker({label:'Kickoff UTC',type:'datetime-local',value:'2028-01-31T19:45',onSet:v=>saved=v});
const month=wheel('Month');month.children[1].onclick();assert.equal(wheel('Day').children.length,29);click('Set date & time');assert.equal(saved,'2028-02-29T19:45');assert.equal(document.body.children.length,0);
saved=null;context.scheduleWheelPicker({label:'Start',type:'time',value:'19:45',onSet:v=>saved=v});wheel('Hour').scrollTop=20*42;wheel('Minute').scrollTop=7*42;click('Set time');assert.equal(saved,'20:07');
saved=null;context.scheduleWheelPicker({label:'End',type:'time',value:'23:59',onSet:v=>saved=v});wheel('Minute').onkeydown({key:'Home',preventDefault(){}});click('Cancel');assert.equal(saved,null);
context.scheduleWheelPicker({label:'Start',type:'time',value:'00:00',onSet:v=>saved=v});wheel('Hour').onkeydown({key:'End',preventDefault(){}});click('Set time');assert.equal(saved,'23:00');
const parent=new Element('form'),field=context.scheduleWheelField(parent,'Start','start','time','19:00');const opener=all(parent).find(e=>e.tagName==='BUTTON');assert.equal(opener.type,'button');opener.onclick();wheel('Hour').children[21].onclick();click('Cancel');assert.equal(field.value,'19:00');opener.onclick();wheel('Hour').children[21].onclick();click('Set time');assert.equal(field.value,'21:00');assert.equal(document.body.children.length,0);
console.log('Wheel date clamping, scroll selection, keyboard selection, cancel, Set and non-submitting field controls passed');
