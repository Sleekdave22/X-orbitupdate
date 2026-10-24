const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const store=new Map(),styles={},requests=[];
store.set('guardianchat-account',JSON.stringify({id:'alpha',token:'alpha-session'}));
const ctx={JSON,Date,console,localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},window:{addEventListener(){}},document:{readyState:'loading',documentElement:{dataset:{},style:{setProperty:(k,v)=>styles[k]=v}},getElementById:()=>null,addEventListener(){}},setInterval(){},fetch:(path,opts)=>new Promise(resolve=>requests.push({path,opts,resolve}))};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/personalization.js','utf8'),ctx);
const choices=JSON.parse(fs.readFileSync(__dirname+'/personalization.json','utf8'));
const reply=(n,id)=>requests[n].resolve({ok:true,json:async()=>({palette:id,choices})});
(async()=>{
 const a=ctx.window.OrbitPersonalization.refresh(true);
 store.set('guardianchat-account',JSON.stringify({id:'beta',token:'beta-session'}));
 const b=ctx.window.OrbitPersonalization.refresh(true);
 reply(0,'pink-matte-black');await a;assert.equal(styles['--personal-bubble'],'#7C3AED','Old account response is ignored');
 reply(1,'blue-gold');await b;assert.equal(styles['--personal-bubble'],'#2458bc');assert.equal(styles['--personal-accent'],undefined,'Theme accent is not controlled by bubble preferences');assert.equal(styles['--personal-received'],'#e8b84a');assert.equal(styles['--personal-heading-dark'],choices.find(p=>p.id==='blue-gold').headingDark);assert.equal(styles['--personal-heading-light'],choices.find(p=>p.id==='blue-gold').headingLight);assert.equal(styles['--personal-received-ink'],'#24170a');assert.equal(requests[1].opts.headers.Authorization,'Bearer beta-session');assert(!store.has('xorbit-palette-alpha'));
 store.delete('guardianchat-account');await ctx.window.OrbitPersonalization.refresh(true);assert.equal(styles['--personal-bubble'],'#7C3AED','Logout clears the previous account colour');
 store.set('guardianchat-account',JSON.stringify({id:'beta',token:'new-session'}));const c=ctx.window.OrbitPersonalization.refresh(true);reply(2,'green-pink');await c;assert.equal(styles['--personal-bubble'],'#1d7148');assert.equal(styles['--personal-received'],'#f2c0d5');
 console.log('Account colours ignore stale responses, reset on logout and refresh with the correct session.');
})().catch(e=>{console.error(e);process.exitCode=1});
