const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/index.html','utf8');
const snippet=source.slice(source.indexOf('function createChatCamera('),source.indexOf('// End chat camera controller.'));
const ctx={File:class File{constructor(parts,name,opts){Object.assign(this,{parts,name,...opts})}}};vm.createContext(ctx);vm.runInContext(snippet,ctx);
function fixture(){let owner='account:peer',stopped=0,staged=[],constraints,pendingBlob;const listeners={};const dialog={open:false,showModal(){this.open=true},close(){this.open=false;listeners.close?.()},addEventListener(k,v){listeners[k]=v}};
const video={videoWidth:1920,videoHeight:1080,srcObject:null,play:async()=>{}},status={},capture={disabled:true};
const stream={getTracks:()=>[{stop(){stopped++}}]};
const hooks={dialog,video,status,capture,context:()=>owner,stage:f=>staged.push(f),requestMedia:async c=>{constraints=c;return stream},createCanvas:()=>({getContext:()=>({drawImage(){}}),toBlob:cb=>cb({size:12})})};
return {hooks,stream,dialog,video,status,capture,staged,get stopped(){return stopped},get constraints(){return constraints},owner:v=>owner=v};}
(async()=>{
 let f=fixture(),c=ctx.createChatCamera(f.hooks);await c.open();assert.equal(f.staged.length,0,'Opening the camera never sends/stages a photo');assert.equal(f.constraints.audio,false);assert.equal(f.capture.disabled,false);await c.take();assert.equal(f.staged.length,1);assert.equal(f.staged[0].name,'Camera photo.jpg');assert.equal(f.dialog.open,false);assert.equal(f.video.srcObject,null);assert.equal(f.stopped,1);
 f=fixture();let permission;f.hooks.requestMedia=()=>new Promise(r=>permission=r);c=ctx.createChatCamera(f.hooks);const opening=c.open();c.close();permission(f.stream);await opening;assert.equal(f.stopped,1);assert.equal(f.staged.length,0);assert.equal(f.dialog.open,false);
 f=fixture();c=ctx.createChatCamera(f.hooks);await c.open();f.owner('different:peer');await c.take();assert.equal(f.staged.length,0);assert.equal(f.stopped,1);
 f=fixture();f.hooks.requestMedia=async()=>{throw Error('declined')};c=ctx.createChatCamera(f.hooks);await c.open();assert.match(f.status.textContent,/permission declined/);assert.equal(f.capture.disabled,true);
 f=fixture();let finishBlob;f.hooks.createCanvas=()=>({getContext:()=>({drawImage(){}}),toBlob:cb=>finishBlob=cb});c=ctx.createChatCamera(f.hooks);await c.open();const taking=c.take();c.close();await c.open();const before=f.stopped;finishBlob({size:12});await taking;assert.equal(f.dialog.open,true,'An old capture cannot close a newly opened camera');assert.equal(f.stopped,before);assert.equal(f.staged.length,0);c.close();
 console.log('Camera permission/cancel/stale-account races, capture-to-preview and track cleanup passed');
})().catch(e=>{console.error(e);process.exitCode=1});
