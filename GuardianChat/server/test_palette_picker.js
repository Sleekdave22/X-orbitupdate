const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ids=new Map(),store=new Map(),styles={},requests=[];
class Element{
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.dataset={};this.children=[];this.attributes={};this.style={setProperty:(k,v)=>{this.style[k]=v}};this.disabled=false;this.open=false;this.listeners={}}
 set id(id){this._id=id;ids.set(id,this)}get id(){return this._id}
 set innerHTML(html){for(const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"/g)){const e=new Element(m[1]);e.id=m[2];this.children.push(e)}}
 append(...nodes){this.children.push(...nodes)}replaceChildren(...nodes){this.children=nodes}
 setAttribute(k,v){this.attributes[k]=v}addEventListener(k,f){this.listeners[k]=f}
 querySelector(){return null}insertBefore(e){this.children.push(e)}
 showModal(){this.open=true}close(){this.open=false;this.onclose?.()}focus(){this.focused=true}
}
const settings=new Element();settings.id='settingsPanel';
store.set('guardianchat-account',JSON.stringify({id:'alpha',token:'alpha-session'}));
const context={console,JSON,Date,localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},document:{readyState:'complete',body:new Element(),documentElement:{dataset:{theme:'dark'},style:{setProperty:(k,v)=>styles[k]=v}},createElement:t=>new Element(t),getElementById:id=>ids.get(id)||null,addEventListener(){}},window:{addEventListener(){}},setInterval(){},fetch:(path,opts)=>new Promise(resolve=>requests.push({path,opts,resolve}))};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/personalization.js','utf8'),context);
const choices=JSON.parse(fs.readFileSync(__dirname+'/personalization.json','utf8'));
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const reply=(n,palette='orbit-cyan-navy',ok=true)=>requests[n].resolve({ok,json:async()=>({palette,choices})});
const el=id=>ids.get(id),option=id=>el('paletteOptions').children.find(e=>e.dataset.palette===id);
(async()=>{
 reply(0);await settle();
 el('openPersonalization').onclick();reply(1);await settle();
 assert.equal(el('paletteOptions').children.length,choices.length);
 assert.equal(el('savePalette').disabled,true,'Saved pair needs no second confirmation');
 option('blue-gold').onclick();
 assert.equal(option('blue-gold').attributes['aria-checked'],'true');
 assert.equal(styles['--personal-bubble'],'#7C3AED','Choosing a card is a preview only');
 assert.equal(requests.length,2,'Preview does not submit preferences');
 el('paletteLight').onclick();
 assert.equal(el('paletteScene').dataset.mode,'bright');
 assert.equal(context.document.documentElement.dataset.theme,'dark','Preview mode never changes the account appearance');
 assert.equal(el('paletteScene').style['--preview-tint'],'linear-gradient(180deg,#b9caea,#f5e1b3 56%,#fbf2de)');
 el('closePalette').onclick();assert.equal(styles['--personal-bubble'],'#7C3AED');
 el('openPersonalization').onclick();reply(2);await settle();option('blue-gold').onclick();
 const save=el('savePalette').onclick();el('savePalette').onclick();
 assert.equal(requests.length,4,'Double select has one POST');
 assert.equal(requests[3].opts.method,'POST');
 assert.deepEqual(JSON.parse(requests[3].opts.body),{palette:'blue-gold'});
 reply(3,'blue-gold');await save;
 assert.equal(styles['--personal-bubble'],'#2458bc');
 assert.equal(styles['--personal-wallpaper-dark'],'linear-gradient(180deg,#1a3f87,#977830 56%,#2e250f)');
 assert.equal(el('savePalette').disabled,true);
 option('green-pink').onclick();const failure=el('savePalette').onclick();reply(4,'green-pink',false);await failure;
 assert.equal(styles['--personal-bubble'],'#2458bc','Failed saves retain the confirmed pair');
 assert.match(el('paletteStatus').textContent,/unchanged/);assert.equal(el('savePalette').disabled,false);
 const retry=el('savePalette').onclick();reply(5,'green-pink');await retry;assert.equal(styles['--personal-bubble'],'#1d7148');
 option('pink-matte-black').onclick();const stale=el('savePalette').onclick();
 store.set('guardianchat-account',JSON.stringify({id:'beta',token:'beta-session'}));
 const next=context.window.OrbitPersonalization.refresh(true);
 assert.equal(el('personalizationDialog').open,false,'Account changes dismiss the previous account preview');
 reply(6,'pink-matte-black');await stale;
 assert.equal(styles['--personal-bubble'],'#7C3AED','Old saves cannot repaint the new account');
 reply(7,'blue-gold');await next;
 assert.equal(styles['--personal-bubble'],'#2458bc');
 store.delete('guardianchat-account');await context.window.OrbitPersonalization.refresh(true);
 assert.equal(styles['--personal-wallpaper-dark'],'linear-gradient(transparent,transparent)','Logout clears the previous account wallpaper');
 assert.equal(styles['--personal-accent'],undefined,'Other application chrome is not personalized');
 console.log('Picker preview/cancel, explicit selection, duplicate select, failure/retry, mode isolation and stale-account saves passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
