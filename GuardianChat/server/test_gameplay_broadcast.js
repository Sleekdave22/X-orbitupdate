const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/gaming.js','utf8');
const roomCode=fs.readFileSync(__dirname+'/stream-relay-ui.js','utf8');
assert(source.includes("room.media!=='relay'"),'legacy mesh rooms must not offer the relay-only native publisher');
async function scenario(native=true){
 const elements=[],timers=[],requests=[];let captured=0,stops=0,starts=0,now=0;
 class Element{constructor(tag,text=''){this.tag=tag;this.dataset={};this.textContent=text;this.disabled=false;this.hidden=false;this.value='';this.children=[];elements.push(this)}append(...v){this.children.push(...v)}replaceChildren(...v){this.children=v}setAttribute(){}after(){}async play(){} }
 const state={room:'',active:false,pending:false,status:''};const root=new Element('main');const doc={hidden:false,addEventListener(){},removeEventListener(){}};
 const ctx={native,streamCleanup:null,crypto:{randomUUID:()=> 'client-test'},node:(...a)=>new Element(...a),button:(text,fn)=>{const e=new Element('button',text);e.onclick=fn;return e},$:()=>root,document:doc,window:{addEventListener(){},removeEventListener(){}},account:{id:'host',token:'fixture'},data:{},tab:'',load(){},setInterval:fn=>{timers.push(fn);return timers.length},clearInterval(){},Date:{now:()=>now},console,navigator:{mediaDevices:{getUserMedia:async()=>{captured++;throw Error('Camera test only')}}},fetch:async()=>({}),openSocialProfile(){},mountLiveRoomUI:()=>({setActive(){},renderComments(){},renderReactions(){},cleanup(){}}),api:async(path,body)=>{requests.push({path,body});return {live:{active:state.active,viewers:0},signals:[],comments:[],reactions:[],likes:0,liked:false}}};
 if(native)ctx.GuardianGaming={startGameplay:id=>{starts++;state.pending=true},stopGameplay:()=>{stops++;state.active=false;state.room=''},gameplayStatus:()=>JSON.stringify(state)};
 vm.createContext(ctx);vm.runInContext(roomCode+';this.openStream=relayStreamRoom;this.cleanup=()=>streamCleanup?.()',ctx);
 await ctx.openStream({id:'a'.repeat(32),a:'host',b:'viewer'});const screen=elements.find(e=>e.textContent==='Broadcast gameplay screen'),camera=elements.find(e=>e.textContent==='Start live camera'),end=elements.find(e=>e.textContent==='End broadcast');
 if(!native){assert(screen.hidden);assert(!camera.disabled);return}
 screen.onclick();assert.equal(starts,1);assert(camera.disabled);assert.equal(captured,0);assert(!requests.some(r=>r.path==='/gaming/stream_begin'));
 // Cancellation must allow a fresh consent attempt after the short service-start grace period.
 state.pending=false;now=4000;await timers[0]();assert(!screen.disabled);assert(!camera.disabled);
 screen.onclick();state.pending=false;state.room='a'.repeat(32);state.active=true;state.status='LIVE screen';await timers[0]();assert(!end.disabled);
 // Going to the game must not stop native sharing.
 doc.hidden=true;await timers[0]();assert.equal(stops,0);assert.equal(captured,0);
 doc.hidden=false;await end.onclick();assert.equal(stops,1);assert.equal(state.active,false);
 ctx.cleanup();assert.equal(stops,1);
}
(async()=>{await scenario();await scenario(false);console.log('Screen broadcast bridge, consent cancellation, no camera capture, background continuation, stop and browser fallback passed')})().catch(e=>{console.error(e);process.exitCode=1});
