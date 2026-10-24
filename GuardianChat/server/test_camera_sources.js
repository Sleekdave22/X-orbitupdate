const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {Element,walk}=require('./browser-test-dom.cjs');
const devices=[{kind:'videoinput',deviceId:'physical',label:'Webcam'},{kind:'videoinput',deviceId:'obs',label:'OBS Virtual Camera'},{kind:'videoinput',deviceId:'other',label:'Other Virtual Camera'},{kind:'audioinput',deviceId:'mic',label:'Microphone'}];
const requests=[],stopped=[],listeners=new Map();let nextCapture=null;
const media={enumerateDevices:async()=>devices,getUserMedia:async constraints=>{requests.push(constraints);if(nextCapture)return nextCapture;return {getTracks:()=>[{stop:()=>stopped.push(1)}]}},addEventListener:(k,f)=>listeners.set(k,f),removeEventListener:k=>listeners.delete(k)};
const context={document:{createElement:tag=>new Element(tag)},navigator:{mediaDevices:media},Error};context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/camera-sources.js','utf8'),context);
(async()=>{
 const picker=context.OrbitCameraSources.create();await new Promise(setImmediate);
 assert.equal(requests.length,0,'Opening controls never starts a camera');
 const selects=walk(picker.element).filter(n=>n.tagName==='SELECT'),[camera,audio,quality]=selects;
 assert(camera.children.some(o=>o.textContent==='OBS Virtual Camera'));assert(camera.children.some(o=>o.textContent==='Other Virtual Camera'));
 camera.value='other';audio.value='none';quality.value='1080';await picker.capture();
 assert.equal(requests[0].video.deviceId.exact,'other');assert.equal(requests[0].video.height.ideal,1080);assert.equal(requests[0].video.frameRate.max,30);assert.equal(requests[0].audio,false);
 picker.setBusy(false);camera.value='obs';audio.value='mic';await picker.capture();assert.equal(requests[1].video.deviceId.exact,'obs');assert.equal(requests[1].audio.deviceId.exact,'mic');
 picker.destroy();assert(!listeners.has('devicechange'));
 const pending=context.OrbitCameraSources.create();await Promise.resolve();let finish;nextCapture=new Promise(resolve=>finish=resolve);const opening=pending.capture();pending.destroy();finish({getTracks:()=>[{stop:()=>stopped.push(1)}]});await assert.rejects(opening,/closed/);assert(stopped.length>0,'Late camera streams are stopped after navigation');
 console.log('Any virtual/physical camera, audio choice, quality bounds, explicit permission and navigation cleanup passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
