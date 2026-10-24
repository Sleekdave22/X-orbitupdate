class Element{
 constructor(tag='div',text=''){this.tagName=tag.toUpperCase();this.textContent=text;this.children=[];this.style={};this.dataset={};this.attributes={};this.value='';this.hidden=false;this.disabled=false;this.videoWidth=640;this.videoHeight=360;this.srcObject=null;const names=new Set();this.classList={add:x=>names.add(x),remove:x=>names.delete(x),contains:x=>names.has(x)}}
 append(...nodes){for(const n of nodes){this.children.push(n);if(n&&typeof n==='object')n.parent=this}}
 replaceChildren(...nodes){for(const n of this.children)if(n&&typeof n==='object')n.parent=null;this.children=[];this.append(...nodes)}
 setAttribute(k,v){this.attributes[k]=String(v)}
 removeAttribute(k){delete this.attributes[k];if(k==='src')this.src=''}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null}
 async play(){}
 setPointerCapture(){}
 getContext(){return {drawImage(){}}}
 toBlob(done){done(new Blob(['synthetic captured photo'],{type:'image/jpeg'}))}
}
const walk=root=>[root,...(root.children||[]).flatMap(n=>n&&typeof n==='object'?walk(n):[])];
const content=root=>[root.textContent||'',...(root.children||[]).map(n=>typeof n==='string'?n:content(n))].join(' ');
module.exports={Element,walk,content};
