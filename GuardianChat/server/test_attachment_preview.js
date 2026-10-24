const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/index.html','utf8');
for(const script of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(script[1]);
const trayMarkup=html.slice(html.indexOf('<form id="composer">'),html.indexOf('</form>',html.indexOf('<form id="composer">')));
assert(trayMarkup.includes('<section id="outgoing" hidden'));
assert(!html.includes('<dialog id="outgoing">'));
assert(!html.includes('id="previewCaption"')); // The normal composer holds the caption.
function node(){return {value:'',checked:false,hidden:true,clientHeight:600,scrollHeight:900,scrollTop:0,children:[],style:{setProperty(k,v){this[k]=v}},replaceChildren(){this.children=[]},append(v){this.children.push(v)},querySelectorAll(){return []},focus(){},addEventListener(){},click(){this.onclick()}}}
const nodes=new Proxy({}, {get(o,k){return o[k]??=(node())}}),revoked=[],sent=[];
let context={el:id=>nodes[id],document:{createElement:()=>node(),addEventListener(){}},window:{},ResizeObserver:class{constructor(fn){context.resize=fn}observe(){}},URL:{createObjectURL:f=>'blob:'+f.name,revokeObjectURL:u=>revoked.push(u)},busy:false,pendingFile:null,outURL:null,previewVoice:null,previewVoiceURL:null,previewRecording:false,speech:null,voiceRecorder:null,voiceStarting:false,forwardTargets:null,peer:{id:'peer'},error:m=>context.errorMessage=m,stopVoice(){},send:(text,file)=>sent.push({text,file}),sendForward:()=>{context.forwarded=true}};
vm.createContext(context);
const wire=html.slice(html.indexOf("el('composer').onsubmit="),html.indexOf('function createChatCamera('));
const clean=html.slice(html.indexOf('function showOutgoing(){'),html.indexOf(";el('closeViewer').onclick"));
vm.runInContext(clean+';'+wire,context);
for(const type of ['image/png','video/mp4','audio/mp4','application/pdf']){
 const file={name:type.split('/')[0],type,size:10};nodes.draft.value='Keep this caption';context.stageFile(file);
 assert.equal(nodes.outgoing.hidden,false);assert.equal(nodes.outgoing.style['--attachment-height'],'120px');
 assert.equal(nodes.draft.value,'Keep this caption');assert.equal(context.pendingFile,file);
 if(type.startsWith('image/'))assert.equal(nodes.outPreview.children.length,1);
 if(type.startsWith('video/')||type.startsWith('audio/'))assert(nodes.outPreview.children[0].controls);
 nodes.cancelMedia.onclick();assert(nodes.outgoing.hidden);assert.equal(context.pendingFile,null);assert.equal(nodes.draft.value,'Keep this caption');
}
assert.equal(sent.length,0);assert.equal(revoked.length,4);
context.stageFile({name:'one',type:'image/png',size:10});nodes.chat.clientHeight=300;context.resize();assert.equal(nodes.outgoing.style['--attachment-height'],'60px');
context.stageFile({name:'two',type:'application/pdf',size:10});assert(revoked.includes('blob:one'));
context.stageFile({name:'large',type:'image/png',size:9*1024*1024});assert.equal(context.pendingFile.name,'two');assert(context.errorMessage);
nodes.previewOnce.checked=true;nodes.draft.value='Caption at send';nodes.composer.onsubmit({preventDefault(){}});
assert.equal(sent.length,1);assert.equal(sent[0].text,'Caption at send');assert.equal(sent[0].file.name,'two');assert(nodes.outgoing.hidden);assert(nodes.once.checked);
context.stageFile({name:'private',type:'image/png',size:10});nodes.previewProtected.checked=true;nodes.composer.onsubmit({preventDefault(){}});assert(context.forwarded);assert.equal(sent.length,1);
context.busy=true;context.stageFile({name:'blocked',type:'image/png',size:10});assert.equal(context.pendingFile.name,'private');nodes.cancelMedia.onclick();assert(!nodes.outgoing.hidden);
console.log('Inline attachment staging, captions, media kinds, size limits, resizing, cancel, cleanup and Send routing passed');
