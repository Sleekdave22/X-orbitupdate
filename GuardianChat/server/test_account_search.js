const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node{
 constructor(){this.children=[];this.hidden=false;this.value='';this.textContent=''}
 append(...nodes){this.children.push(...nodes)}replaceChildren(){this.children=[]}
 get childElementCount(){return this.children.length}
}
const ids=['globalSearchForm','globalSearchQuery','globalSearchStatus','globalSearchResults','globalSearchMore'],nodes=Object.fromEntries(ids.map(id=>[id,new Node()])),pending=[];
const context={window:{},account:{id:'owner'},el:id=>nodes[id],document:{createElement:()=>new Node()},api:path=>new Promise((resolve,reject)=>pending.push({path,resolve,reject})),openSocialProfile:id=>context.opened=id};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/account-search.js','utf8').split('/* A separate magnifier')[0],context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const submit=()=>nodes.globalSearchForm.onsubmit({preventDefault(){}});
(async()=>{
 nodes.globalSearchQuery.value='Old search';submit();
 nodes.globalSearchQuery.value='New search';nodes.globalSearchQuery.oninput();submit();
 pending[0].resolve({users:[{id:'old',name:'Old',nickname:'old'}],next_offset:null});await tick();assert.equal(nodes.globalSearchResults.childElementCount,0);
 pending[1].resolve({users:[{id:'new',name:'New',nickname:'new'}],next_offset:20});await tick();assert.equal(nodes.globalSearchResults.childElementCount,1);assert.equal(nodes.globalSearchMore.hidden,false);
 nodes.globalSearchResults.children[0].children[0].onclick();assert.equal(context.opened,'new');
 nodes.globalSearchMore.onclick();assert(pending[2].path.endsWith('&offset=20'));pending[2].reject(Error('Offline'));await tick();assert.equal(nodes.globalSearchMore.hidden,false);assert.equal(nodes.globalSearchStatus.textContent,'Offline');
 nodes.globalSearchMore.onclick();context.account={id:'other'};pending[3].resolve({users:[{id:'private',name:'Private',nickname:'private'}],next_offset:null});await tick();assert.equal(nodes.globalSearchResults.childElementCount,1);
 context.window.OrbitAccountSearch.resetForAccount();assert.equal(nodes.globalSearchResults.childElementCount,0);assert.equal(nodes.globalSearchQuery.value,'');
 console.log('Search ignores stale/other-account responses, clears account changes, opens public profiles and retries failed pagination.');
})().catch(e=>{console.error(e);process.exitCode=1});
