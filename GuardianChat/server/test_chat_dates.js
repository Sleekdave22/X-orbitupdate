'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {Element,walk}=require('./browser-test-dom.cjs');

/** Flat message-list fixture with layout offsets, not a general CSS renderer. */
class Node extends Element{
 get isConnected(){return !!this.parent||this===container}
 matches(selector){return selector.split(',').some(part=>this.className===part.slice(1))}
 querySelectorAll(selector){return walk(this).slice(1).filter(node=>node.matches(selector))}
 insertBefore(node,target){const index=this.children.indexOf(target);assert(index>=0);node.parent=this;this.children.splice(index,0,node)}
 get scrollHeight(){return this.children.length*20}
 getBoundingClientRect(){const top=this===container?100:100+container.children.indexOf(this)*20-container.scrollTop;return {top,bottom:top+20}}
}
const container=new Node();container.clientHeight=40;container.scrollTop=0;
const context={window:{},Date,Number,document:{createElement:()=>new Node()}};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/chat-dates.js','utf8'),context);
const dates=context.window.OrbitChatDates;
let now=new Date(2026,0,1,0,20).getTime();
assert.equal(dates.label(now,now),'Today');assert.equal(dates.label(now-3600000,now),'Yesterday');assert.equal(dates.label(0,now),'');assert.equal(dates.key(NaN),null);
for(let i=0;i<16;i++){const row=new Node();row.className=i===6?'call-event':'message';row.dataset.time=String(new Date(2025,11,30+Math.floor(i/6),10).getTime());row.dataset.messageId=String(i+1);container.append(row)}
container.scrollTop=90;const anchor=container.children[4],oldOffset=anchor.getBoundingClientRect().top;
dates.sync(container,now);assert.equal(container.querySelectorAll('.chat-date-divider').length,3);assert.equal(anchor.getBoundingClientRect().top,oldOffset,'Date markers preserve the visible reading anchor');
const markers=container.querySelectorAll('.chat-date-divider');dates.sync(container,now);assert.equal(container.querySelectorAll('.chat-date-divider')[0],markers[0],'Unchanged polls do not rebuild labels');assert.equal(container.querySelectorAll('.chat-date-divider').at(-1).textContent,'Today');
dates.sync(container,new Date(2026,0,2,0,20).getTime());assert.equal(container.querySelectorAll('.chat-date-divider').at(-1).textContent,'Yesterday');
process.env.TZ='America/New_York';now=new Date(2026,2,9,0,15).getTime();const earlier=new Date(2026,2,8,0,45).getTime();assert(now-earlier<86400000);assert.equal(dates.label(earlier,now),'Yesterday','DST uses local calendar arithmetic');
console.log('Local dates, year rollover, DST, mixed call rows, stable polling and reading-anchor preservation passed.');
