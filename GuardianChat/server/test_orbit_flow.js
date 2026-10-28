const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/orbit-flow.js','utf8');
function setup({supported=true,reduced=false}={}){
 const events={},dataset={},storage=new Map(),routes=[];let release,started=0;
 const context={window:{matchMedia:()=>({matches:reduced}),addEventListener:(n,fn)=>(events[n]=fn)},document:{documentElement:{dataset}},sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},Date,location:{assign:p=>routes.push(p)},setTimeout:()=>1,clearTimeout(){}};
 if(supported)context.document.startViewTransition=fn=>{started++;const update=Promise.resolve().then(fn),done=new Promise(r=>release=r);return {ready:Promise.resolve(),updateCallbackDone:update,finished:update.then(()=>done)}};
 vm.createContext(context);vm.runInContext(source,context);
 return {flow:context.window.OrbitFlow,events,dataset,routes,context,release:()=>release(),started:()=>started};
}
const tick=()=>new Promise(setImmediate);
(async()=>{
 const s=setup();let changes=0;await s.flow.local(()=>++changes,-1);assert.equal(changes,1);assert.equal(s.dataset.orbitFlow,'back');s.flow.local(()=>++changes,1);await tick();assert.equal(changes,1,'A running transition cannot duplicate a tab action');s.release();await tick();await s.flow.local(()=>++changes,1);assert.equal(changes,2);s.release();await tick();
 s.flow.navigate('/vibe.html');s.flow.navigate('/');assert.deepEqual(s.routes,['/vibe.html']);s.events.pageshow();s.flow.navigate('/');assert.deepEqual(s.routes,['/vibe.html','/'],'Back/forward restoration must release navigation');
 for(const options of [{supported:false},{reduced:true}]){const f=setup(options);let n=0;await f.flow.local(()=>n++);assert.equal(n,1);assert.equal(f.started(),0)}
 const f=setup(),handlers={},host={clientWidth:390,addEventListener:(n,fn)=>handlers[n]=fn,setPointerCapture(){}};
 let selected=1;const visited=[],items=Array.from({length:4},(_,i)=>({activate(){const e={preventDefault(){this.blocked=true},stopImmediatePropagation(){}};handlers.click(e);if(!e.blocked){visited.push(i);selected=i}}}));
 f.flow.bindTabs(host,items,()=>selected);let dragPrevented=false;handlers.dragstart({preventDefault(){dragPrevented=true}});assert(dragPrevented,'Dragging artwork must use the app gesture, not native image dragging');
 const e=x=>({clientX:x,clientY:20,pointerId:1,button:0,preventDefault(){}});
 handlers.pointerdown(e(300));handlers.pointermove(e(180));handlers.pointerup(e(180));assert.deepEqual(visited,[2],'A gesture must activate the next destination, not suppress its own action');
 const stray={preventDefault(){this.blocked=true},stopImmediatePropagation(){}};handlers.click(stray);assert(stray.blocked,'Suppress the trailing pointer click only');
 f.events.pageshow();handlers.pointerdown(e(80));handlers.pointermove(e(220));handlers.pointercancel(e(220));assert.deepEqual(visited,[2]);
 assert(!fs.readFileSync(__dirname+'/orbit-switcher.js','utf8').includes('querySelector(\'main\')?.animate'),'The page container must never be transformed around fixed tabs');
 console.log('Unified transitions, reduced-motion/unsupported fallback, duplicate prevention, history restoration and all four swipe destinations passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
