'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname,'comparison-compat.js'),'utf8');
class Element {
  constructor(tag,text='') {this.tagName=tag;this.textContent=text;this.children=[];this.dataset={};this.style={};}
  append(...items) {this.children.push(...items);}
  prepend(...items) {this.children.unshift(...items);}
  replaceChildren(...items) {this.children=items;}
  querySelector(query) {return this.querySelectorAll(query)[0] || null;}
  querySelectorAll(query) {
    const result=[];
    for (const item of this.children) {
      if (query==='button'&&item.tagName==='button' || query==='[data-comparison-notice]'&&item.dataset?.comparisonNotice) result.push(item);
      if (item.querySelectorAll) result.push(...item.querySelectorAll(query));
    }
    return result;
  }
}
const text = node => [node.textContent,...node.children.map(text)].join(' ');
function setup(responders={}) {
  const calls=[],view=new Element('section'),header=new Element('h1','Orbit Play');
  const tabs=['leagues','seasons','open','ratings','profile','streams','admin','studio'].map(key=>{const item=new Element('button',key);item.dataset.tab=key;return item;});
  const state={
    console,URL,Request,Response,Headers,JSON,Promise,Date,Number,Map,Set,Array,Object,Error,
    location:new URL('https://example.test/gaming.html'),
    document:{querySelector:q=>q==='header h1'?header:null,querySelectorAll:q=>q==='nav [data-tab]'?tabs:[],getElementById:id=>id==='view'?view:null,createElement:tag=>new Element(tag),addEventListener(){}},
    STUDIO_FIELDS:{accept_seconds:['x',1],group_size:['x',1],start_rating:['x',1]},
    tab:'leagues', data:null,
    render(){view.replaceChildren(new Element('p','Fork content'));},
    applyPublishedTheme(){throw Error('The published theme must not be applied');},
    async studioView(){view.append(new Element('button','Preview theme draft'));},
    async fetch(input,init) {
      const isRequest=input instanceof Request;
      const url=new URL(isRequest?input.url:String(input),'https://example.test');
      const effective={method:init?.method || (isRequest?input.method:'GET'),headers:init?.headers || (isRequest?input.headers:undefined),credentials:init?.credentials || (isRequest?input.credentials:undefined),body:init?.body};
      calls.push({url,init,effective,input});
      const reply=responders[url.pathname+url.search] ?? responders[url.pathname];
      if (reply instanceof Error) throw reply;
      if (typeof reply==='function') return reply(input,init);
      if (reply instanceof Response) return reply.clone();
      return new Response(JSON.stringify(reply??{ok:true}),{status:200,headers:{'Content-Type':'application/json','Content-Length':'999','Content-Encoding':'gzip','X-Original':'retained'}});
    }
  };
  state.window=state;vm.createContext(state);vm.runInContext(code,state);
  return {state,calls,view};
}
const auth={headers:{Authorization:'Bearer synthetic-test-token','X-Test':'kept'},credentials:'same-origin'};
const policy={id:7,config:{k:24,placements:10,grades:[{name:'Bronze',minimum:0},{name:'Silver',minimum:1300},{name:'Gold',minimum:1500},{name:'Platinum',minimum:1700},{name:'Diamond',minimum:1900},{name:'Elite',minimum:2100}]}};
const rating={game:'football',rating:1531.27,played:22,activity:22,verified_placements:21,placement_required:10,provisional:false,grade:'Gold',policy:7};
const engine={config:{start_rating:1000,theme:{accent:'#ffffff'},presentation:{game_tabs:['open'],labels:{gaming:'Different published label'},custom_sections:[{id:'custom_server'}]}},ids:[{game:'football'}],ratings:[rating],notices:[{text:'Existing notice'}],matches:[{id:'unchanged',state:'verified',score_a:3,score_b:1}]};
function responders() {return {
  '/gamebox/summary':engine,
  '/rankings/policy':policy,
  '/rankings/history?game=football':{history:[{rating_before:1519.27,rating_after:1531.27,outcome:'W',created:123,source:'existing-result',kind:'open'}]},
  '/rankings/leaderboard?game=football&mine=1&limit=1':{players:[],my_rank:{global_rank:3}}
};}
let count=0;
async function test(name,fn) {await fn();count++;console.log('PASS '+name);}
(async()=>{
  await test('Authoritative ratings and outcomes are copied; no new award or balance is calculated',async()=>{
    const source=JSON.stringify(engine),{state,calls}=setup(responders());
    const response=await state.fetch('/gamebox/summary',auth),result=await response.json();
    assert.equal(result.rating_cards[0].rating,rating.rating);
    assert.equal(result.rating_cards[0].rank,3);assert.equal(result.rating_cards[0].matches,21);
    assert.equal(result.rating_cards[0].tier,'Gold');assert.equal(result.rating_cards[0].wins,null);
    assert.deepEqual(result.rating_cards[0].history[0],{before:1519.27,after:1531.27,change:12,outcome:1,created:123,kind:'open',source:'existing-result'});
    assert.deepEqual(result.ratings,engine.ratings);assert.deepEqual(result.matches,engine.matches);
    assert.equal(JSON.stringify(engine),source);assert.ok(calls.every(c=>c.effective.method==='GET'));
    assert.equal(response.headers.get('content-length'),null);assert.equal(response.headers.get('content-encoding'),null);assert.equal(response.headers.get('x-original'),'retained');
  });
  await test('The source theme and tab layout are retained without writing published settings',async()=>{
    const {state,calls}=setup(responders()),result=await(await state.fetch('/gamebox/summary',auth)).json();
    assert.equal(result.config.theme.accent,'#7C3AED');assert.equal(result.config.theme.paper,'#0B1520');
    assert.equal(result.config.start_rating,undefined);assert.equal(result.config.presentation.labels.gaming,'Orbit Play');
    assert.deepEqual(result.config.presentation.game_tabs,['leagues','seasons','open','ratings','profile','streams']);assert.deepEqual(result.config.presentation.custom_sections,[]);
    assert.ok(calls.every(c=>c.effective.method==='GET'));
  });
  await test('Only active owned game identities are adapted for the legacy profile',async()=>{
    const source={profile:{uid:'owner',tag:'Player',game_id:'old'},player_stats:{wins:12,losses:9}},copy=JSON.stringify(source);
    const {state}=setup({'/gaming/summary':source,'/identities/mine':{identities:[{game:'football',game_id:'Active-ID',state:'active'},{game:'chess',game_id:'Disabled-ID',state:'disabled'}]}});
    const result=await(await state.fetch('/gaming/summary',auth)).json();
    assert.deepEqual(result.profile.game_ids,{football:'Active-ID'});assert.deepEqual(result.player_stats,source.player_stats);assert.equal(JSON.stringify(source),copy);
  });
  await test('Incompatible competitive, result, identity and administrative mutations never reach the server',async()=>{
    const {state,calls}=setup();
    for (const method of ['POST','PUT','DELETE','PATCH']) for (const endpoint of ['/gamebox/identity','/gamebox/studio_save','/gamebox/studio_publish','/gamebox/review','/gamebox/queue','/gaming/profile','/gaming/report','/rankings/publish','/identities/change','/scheduling/save']) {
      const result=await state.fetch(endpoint,{...auth,method,body:JSON.stringify({game_id:'must-not-change',rating:9999,balance:999})});
      assert.equal(result.status,409);assert.match((await result.json()).error,/Competition editing is available in X ORBIT Original/);
    }
    assert.equal(calls.length,0);
  });
  await test('Native-independent chat, contacts and notification acknowledgements pass through unchanged',async()=>{
    const {state,calls}=setup(),body=JSON.stringify({recipient:'peer',text:'Shared message'}),init={...auth,method:'POST',body};
    for (const endpoint of ['/messages','/contacts','/delivered']) await state.fetch(endpoint,init);
    assert.equal(calls.length,3);assert.ok(calls.every(call=>call.init===init));assert.equal(calls[0].effective.body,body);
  });
  await test('Authorization and caller credentials stay on same-origin read contracts, with account-scoped caching',async()=>{
    const {state,calls}=setup(responders());
    await state.fetch(new Request('https://example.test/gamebox/summary',{headers:auth.headers,credentials:'omit'}));
    const extra=calls.filter(call=>call.url.pathname.startsWith('/rankings/'));
    assert.equal(extra.length,3);assert.ok(extra.every(call=>new Headers(call.effective.headers).get('Authorization')==='Bearer synthetic-test-token'));
    assert.ok(extra.every(call=>call.url.origin==='https://example.test'&&call.effective.credentials==='omit'));
    await state.fetch('/gamebox/summary',auth);assert.equal(calls.filter(call=>call.url.pathname.startsWith('/rankings/')).length,3);
    await state.fetch('/gamebox/summary',{headers:{Authorization:'Bearer second-synthetic-account'}});
    assert.equal(calls.filter(call=>call.url.pathname.startsWith('/rankings/')).length,6);
  });
  await test('Server permission errors and offline failures are not converted to successful saves',async()=>{
    const denied=new Response(JSON.stringify({error:'Sign in again'}),{status:401}),{state}=setup({'/gamebox/summary':denied});
    const result=await state.fetch('/gamebox/summary',auth);assert.equal(result.status,401);assert.deepEqual(await result.json(),{error:'Sign in again'});
    const offline=setup({'/gaming/summary':Error('Network unavailable')});await assert.rejects(()=>offline.state.fetch('/gaming/summary',auth),/Network unavailable/);
  });
  await test('Unavailable ranking supplements never invent an initial 1000 rating, rank or complete history',async()=>{
    const routes=responders();routes['/rankings/policy']=new Response('{"error":"Unavailable"}',{status:503});routes['/rankings/history?game=football']=Error('Offline');routes['/rankings/leaderboard?game=football&mine=1&limit=1']=Error('Offline');
    const {state}=setup(routes),result=await(await state.fetch('/gamebox/summary',auth)).json();
    assert.equal(result.rating_cards[0].rating,1531.27);assert.equal(result.rating_cards[0].rank,null);assert.equal(result.rating_cards[0].rank_available,false);assert.equal(result.rating_cards[0].history_available,false);assert.deepEqual(result.rating_cards[0].history,[]);assert.equal(result.comparison.rating_errors.length,1);
  });
  await test('Studio loads supported fields but cannot apply shared colours or publish a different contract',async()=>{
    const config={theme:{accent:'#ffffff'},presentation:{game_tabs:['open'],labels:{gaming:'Server'}}};
    const {state}=setup({'/gamebox/studio':{limits:{accept_seconds:[1,10],group_size:[6,16],open_schedule_seconds:[60,120]},published:{config:JSON.stringify(config)},draft:{config:JSON.stringify(config)},versions:[]}});
    const result=await(await state.fetch('/gamebox/studio',auth)).json();
    assert.deepEqual(Object.keys(result.limits),['accept_seconds','group_size']);assert.equal(JSON.parse(result.published.config).theme.accent,'#7C3AED');
    assert.ok(!JSON.parse(result.published.config).presentation.game_tabs.includes('ratings'));
    state.XOrbitComparison.ready();assert.doesNotThrow(()=>state.applyPublishedTheme(config));
  });
  await test('The explicit render hook shows current server grades and accurate history without misleading fork tiers',async()=>{
    const {state,view}=setup(responders()),result=await(await state.fetch('/gamebox/summary',auth)).json();
    state.data={engine:result,games:{football:'Football'}};state.tab='ratings';state.XOrbitComparison.ready();state.render();
    const output=text(view);assert.match(output,/1531\.27/);assert.match(output,/Gold 1500/);assert.match(output,/Diamond 1900/);assert.match(output,/K-factor: 24/);assert.match(output,/1519\.27 → 1531\.27/);assert.match(output,/not a lifetime wins\/losses total/);assert.doesNotMatch(output,/NaN|1000|1,000|1200|1,200/);
    assert.match(output,/Competition editing is available in X ORBIT Original/);
    await state.studioView();assert.equal(view.querySelectorAll('button')[0].disabled,true);
    state.tab='leagues';state.render();assert.match(text(view),/Fork content/);assert.equal(view.querySelectorAll('[data-comparison-notice]').length,1);
  });
  await test('Missing rating rows use the server profile endpoint rather than a client-side starting value',async()=>{
    const routes=responders();routes['/gamebox/summary']={...engine,ratings:[]};routes['/rankings/profile?game=football']={...rating,rating:1500,verified_placements:0,provisional:true,grade:null};
    const {state}=setup(routes),result=await(await state.fetch('/gamebox/summary',auth)).json();assert.equal(result.rating_cards[0].rating,1500);assert.equal(result.rating_cards[0].tier,'Provisional');assert.equal(result.rating_cards[0].matches,0);
  });
  console.log(count+' comparison compatibility checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
