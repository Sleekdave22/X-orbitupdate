const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{Element,walk,content}=require('./browser-test-dom.cjs');
class E extends Element{
 constructor(tag='div'){super(tag);this.events={};this.open=false}
 addEventListener(k,f){this.events[k]=f}
 querySelectorAll(s){return walk(this).filter(n=>n.tagName==='INPUT'&&n.checked)}
 reset(){this.resetCalled=true}
 scrollIntoView(){this.scrolled=true}
}
const html=fs.readFileSync(__dirname+'/market.html','utf8'),ids=[...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]),nodes=Object.fromEntries(ids.map(id=>[id,new E()]));
let calls=[],fail=true,key=0,seen=[];
const demand={id:'group',title:'Phone',description:'<b>Public text</b>',category:'electronics',kind:'PRODUCT',requesters:5,hot:true,mine:false};
const context={window:{},document:{hidden:false,getElementById:id=>nodes[id],createElement:tag=>new E(tag)},crypto:{randomUUID:()=> 'client-'+(++key)},matchMedia:()=>({matches:true}),encodeURIComponent,console};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/market-demand.js','utf8'),context);
const api=async(path,body)=>{calls.push({path,body});if(path.startsWith('/market/demands'))return {demands:[demand],mine:[],more:false,preferences:{updates:false,categories:[]},policy:{threshold:5,daily_push_limit:2}};if(path.startsWith('/market/demand?id='))return {demand};if(path==='/market/demand_request'&&fail)throw Error('Network retry');return {ok:true}};
context.window.OrbitDemand.mount({api,account:{id:'me'},seller:()=>true,catalog:()=>({categories:[{id:'electronics',name:'Electronics'}]}),onVisible:ids=>seen.push([...ids])});
const tick=()=>new Promise(setImmediate);
(async()=>{
 nodes.marketDemand.open=true;nodes.marketDemand.events.toggle();await tick();await tick();assert(content(nodes.demandList).includes('5 distinct accounts'));assert.equal(nodes.demandList.children[0].children[1].textContent,'<b>Public text</b>');assert(!calls.some(c=>c.path.includes('save_listing')));
 nodes.demandTitle.value='Phone';nodes.demandDescription.value='Phone wanted';nodes.demandCategory.value='electronics';nodes.demandKind.value='PRODUCT';
 const event={preventDefault(){}};await nodes.demandRequest.onsubmit(event);const first=calls.findLast(c=>c.path==='/market/demand_request').body.client_id;assert.equal(nodes.sendDemand.disabled,false);assert(content(nodes.demandStatus).includes('Network retry'));assert(!nodes.demandRequest.resetCalled);assert.equal(nodes.demandTitle.value,'Phone');
 await nodes.demandRequest.onsubmit(event);assert.equal(calls.findLast(c=>c.path==='/market/demand_request').body.client_id,first);
 fail=false;await nodes.demandRequest.onsubmit(event);assert(nodes.demandRequest.resetCalled);assert.equal(calls.findLast(c=>c.path==='/market/demand_request').body.client_id,first);
 await context.window.OrbitDemand.open('group');assert(nodes.marketDemand.scrolled);assert(content(nodes.demandFocus).includes('Requested opportunity'));
 assert(html.indexOf('id="marketDemand"')>html.indexOf('id="view"'),'Demand extends content without moving existing top controls');
 assert(html.includes('id="tabBrowse"')&&html.includes('id="tabShop"')&&html.includes('id="sellItem"'));
 console.log('Additive Demand panel, real API routing, text-only content, retry identity, draft preservation and notification destination passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
