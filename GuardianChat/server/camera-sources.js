'use strict';
window.OrbitCameraSources={create(){
 const el=(tag,text='')=>{const x=document.createElement(tag);x.textContent=text;return x};
 const element=el('section'),camera=el('select'),audio=el('select'),quality=el('select'),refresh=el('button','Find cameras'),notice=el('p');let closed=false,locked=false,pending=null;
 element.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:8px;width:100%;align-items:end';
 const field=(label,control)=>{const l=el('label',label);l.style.cssText='display:flex;flex-direction:column;gap:4px;min-width:0';control.style.cssText='width:100%;min-width:0';control.setAttribute('aria-label',label);l.append(control);element.append(l)};
 const option=(value,label)=>{const o=el('option',label);o.value=value;return o};
 camera.append(option('','Default camera'));audio.append(option('','Default microphone'),option('none','No audio'));
 for(const [value,label] of [['720','720p · 30 fps'],['1080','1080p · 30 fps'],['480','480p · 15 fps']])quality.append(option(value,label));quality.value='720';
 field('Camera source · physical or virtual',camera);field('Audio source',audio);field('Video quality',quality);refresh.type='button';const help=el('details'),summary=el('summary','Using a virtual camera');help.append(summary,el('p','Start your virtual-camera application on this PC, then choose its camera here. OBS: Start Virtual Camera. Virtual-camera video and microphone/audio are selected separately.'));notice.style.cssText='grid-column:1/-1;margin:0';help.style.cssText='grid-column:1/-1';element.append(refresh,notice,help);
 function update(select,items,defaults){const chosen=select.value;select.replaceChildren(...defaults.map(([value,label])=>option(value,label)),...items.map((d,i)=>option(d.deviceId,d.label||('Device '+(i+1)))));if(chosen&&![...defaults.map(x=>x[0]),...items.map(x=>x.deviceId)].includes(chosen))select.append(option(chosen,'Selected device disconnected'));select.value=chosen}
 async function enumerate(){if(closed)return;const devices=await navigator.mediaDevices.enumerateDevices();if(closed)return;update(camera,devices.filter(d=>d.kind==='videoinput'),[['','Default camera']]);update(audio,devices.filter(d=>d.kind==='audioinput'),[['','Default microphone'],['none','No audio']]);notice.textContent='Choose any physical or virtual camera your browser lists.';}
 async function unlock(){if(closed||locked)return;refresh.disabled=true;try{pending=await navigator.mediaDevices.getUserMedia({video:true,audio:false});pending.getTracks().forEach(t=>t.stop());pending=null;await enumerate()}catch(e){notice.textContent='Camera list unavailable: '+e.message}finally{refresh.disabled=closed||locked}}
 function setBusy(value){locked=value;for(const x of [camera,audio,quality,refresh])x.disabled=value}
 async function capture(){if(closed)throw Error('This broadcast screen is closed');const sizes={'480':[640,480,15],'720':[1280,720,30],'1080':[1920,1080,30]},[width,height,fps]=sizes[quality.value]||sizes['720'];setBusy(true);try{
  const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:width},height:{ideal:height},frameRate:{ideal:fps,max:30},...(camera.value?{deviceId:{exact:camera.value}}:{facingMode:'user'})},audio:audio.value==='none'?false:audio.value?{deviceId:{exact:audio.value}}:true});
  if(closed){stream.getTracks().forEach(t=>t.stop());throw Error('This broadcast screen is closed')}await enumerate().catch(()=>{});if(closed){stream.getTracks().forEach(t=>t.stop());throw Error('This broadcast screen is closed')}return stream;
 }catch(e){setBusy(false);throw Error('Could not open the selected camera/audio source. Start its virtual-camera application or choose another device. '+e.message)}}
 const changed=()=>enumerate().catch(()=>{});navigator.mediaDevices?.addEventListener?.('devicechange',changed);if(navigator.mediaDevices?.enumerateDevices)enumerate().catch(()=>{});
 refresh.onclick=unlock;
 return {element,capture,setBusy,destroy(){closed=true;pending?.getTracks().forEach(t=>t.stop());pending=null;navigator.mediaDevices?.removeEventListener?.('devicechange',changed)}};
}};
