/* Shared browser transitions; fixed navigation never becomes a moving container. */
(()=>{'use strict';
const native=()=>typeof GuardianGaming!=='undefined'||typeof GuardianWallet!=='undefined',reduced=()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
let pending=null,leaving=false;
document.documentElement.dataset.orbitTransitions=typeof document.startViewTransition==='function'?'browser':'fallback';
function direction(value){document.documentElement.dataset.orbitFlow=Number(value)<0?'back':'forward'}
try{const saved=JSON.parse(sessionStorage.getItem('orbit-flow')||'null');if(saved&&Date.now()-saved.at<10000)direction(saved.direction)}catch(_){}
function navigate(page,sign=1){if(leaving)return;leaving=true;direction(sign);try{sessionStorage.setItem('orbit-flow',JSON.stringify({direction:sign,at:Date.now()}))}catch(_){}location.assign(page)}
function local(change,sign=1){
 if(pending)return pending;direction(sign);
 if(native()||reduced()||typeof document.startViewTransition!=='function')return Promise.resolve().then(change);
 let result;const transition=document.startViewTransition(async()=>{result=await change()});
 transition.ready.catch(()=>{});
 pending=transition.finished.catch(()=>{}).finally(()=>{pending=null});
 return transition.updateCallbackDone.then(()=>result);
}
function bindTabs(host,items,selected){
 if(!host||native())return;let start=null,dragging=false,suppress=false,release;
 host.addEventListener('dragstart',e=>e.preventDefault());
 host.addEventListener('click',e=>{if(suppress&&e.detail!==0){e.preventDefault();e.stopImmediatePropagation()}},true);
 host.addEventListener('pointerdown',e=>{if(e.button!==undefined&&e.button!==0)return;start={x:e.clientX,y:e.clientY,id:e.pointerId};dragging=false;suppress=false;clearTimeout(release)});
 host.addEventListener('pointermove',e=>{if(!start||start.id!==e.pointerId)return;const dx=e.clientX-start.x,dy=e.clientY-start.y;if(!dragging&&Math.abs(dy)>12&&Math.abs(dy)>Math.abs(dx)){start=null;return}if(Math.abs(dx)<12&&!dragging)return;dragging=true;suppress=true;host.setPointerCapture?.(e.pointerId);e.preventDefault()});
 function end(e,cancel=false){if(!start||start.id!==e.pointerId)return;const dx=e.clientX-start.x,moved=dragging;start=null;dragging=false;if(moved&&!cancel&&Math.abs(dx)>Math.min(80,host.clientWidth*.16)){const at=selected(),next=Math.max(0,Math.min(items.length-1,at+(dx<0?1:-1)));if(next!==at){suppress=false;try{items[next].activate()}finally{suppress=true}}}}
 host.addEventListener('pointerup',e=>end(e));host.addEventListener('pointercancel',e=>end(e,true));
 window.addEventListener('pageshow',()=>{start=null;dragging=false;suppress=false;clearTimeout(release)});
}
window.addEventListener('pageshow',()=>{leaving=false;pending=null;try{sessionStorage.removeItem('orbit-flow')}catch(_){}});
window.addEventListener('pagereveal',e=>{if((native()||reduced())&&e.viewTransition)e.viewTransition.skipTransition()});
window.OrbitFlow={navigate,local,bindTabs};
})();
