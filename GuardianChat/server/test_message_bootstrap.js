'use strict';
/** The pin initializer runs before the main page's lexical error handler exists. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(__dirname+'/index.html','utf8');
const start=html.indexOf('let pinMessageReading=false;'),end=html.indexOf('\n',html.indexOf("el('messages').addEventListener('scroll'",start));
assert(start>0&&end>start);
let options,seen;
const box={addEventListener(){}};
const context={window:{OrbitMessagePins:{create:value=>{options=value;return {}}}},account:{id:'fixture'},peer:{id:'peer'},activeScreen:'chat',chatVersion:1,el:()=>box,api(){},remember:value=>seen=value};
vm.createContext(context);
vm.runInContext(html.slice(start,end)+"\nconst error=message=>remember(message);",context);
assert.equal(typeof options.error,'function');options.error('Inline failure');assert.equal(seen,'Inline failure');assert.equal(options.current().peer,'peer');
console.log('Conversation controls initialize safely before the inline error callback is assigned.');
