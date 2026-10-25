const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {Element,walk,content}=require('./browser-test-dom.cjs');
const source=fs.readFileSync(__dirname+'/market.js','utf8');new vm.Script(source);new vm.Script(fs.readFileSync(__dirname+'/market-chat.js','utf8'));
let destination=null;const context={document:{createElement:t=>new Element(t)},showListing:id=>destination=id};vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('const node='),source.indexOf('let sum='))+source.slice(source.indexOf('function adCard('),source.indexOf('async function message(')),context);
const card=context.adCard({id:'listing-1',title:'Samsung S21',nickname:'seller',uid:'seller-id',description:'Private detail in full screen',price:'12345',images:['photo']});
assert(content(card).includes('Samsung S21'));assert(content(card).includes('@seller'));assert(!content(card).includes('12345'));assert(!content(card).includes('Private detail'));assert(!walk(card).some(e=>e.tagName==='IMG'));
const poster=walk(card).find(e=>e.tagName==='EM');assert.equal(poster.className,'listing-handle');const button=walk(card).find(e=>e.tagName==='BUTTON');button.onclick();assert.equal(destination,'listing-1');
console.log('Compact advert title/italic handle, hidden detail, and exact listing navigation passed.');
