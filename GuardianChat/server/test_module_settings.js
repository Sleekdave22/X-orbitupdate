'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {Element,walk,content}=require('./browser-test-dom.cjs');

/** Tiny DOM fixture with real reparenting/focus semantics for drawer ownership.
 * @returns {void} DOM assertions fail the script; this does not emulate CSS layout.
 */
class Node extends Element{
 get parentElement(){return this.parent||null}
 get isConnected(){return walk(body).includes(this)}
 append(...nodes){for(const node of nodes){if(node.parent)node.remove();super.append(node)}}
 focus(){document.activeElement=this}
 click(){this.onclick?.()}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null}
 querySelectorAll(selector){return walk(this).slice(1).filter(node=>selector.split(',').some(part=>part.startsWith('#')?node.id===part.slice(1):part.startsWith('label')?node.tagName==='LABEL':node.tagName===part.replace(/:.*/,'').toUpperCase()&&!node.disabled))}
}
const body=new Node('body'),html=new Node('html'),handlers={},storage=new Map();let mounted=0,refreshed=0,shopClicks=0;
const document={body,documentElement:html,readyState:'complete',activeElement:null,createElement:tag=>new Node(tag),getElementById:id=>walk(body).find(n=>n.id===id)||null,querySelector:selector=>body.querySelector(selector),addEventListener:(name,fn)=>handlers[name]=fn};
const context={window:{OrbitPersonalization:{mount:()=>mounted++,refresh:()=>refreshed++}},document,localStorage:{setItem:(key,value)=>storage.set(key,value)},TypeError};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/module-settings.js','utf8'),context);
const settings=context.window.OrbitModuleSettings,trigger=new Node('button'),original=new Node('main');original.append(new Node('article','Current listing / unsent draft'));body.append(trigger,original);
settings.open('market',trigger);assert.equal(content(original),' Current listing / unsent draft');assert.match(content(document.getElementById('settingsPanel')),/Orbit Plaza settings/);assert.equal(mounted,1);
const panel=document.getElementById('settingsPanel');assert.equal(panel.parentElement,body);assert(!panel.hidden);assert.equal(trigger.attributes['aria-expanded'],'true');
const appearance=document.getElementById('appearance');appearance.value='bright';appearance.onchange();assert.equal(html.dataset.theme,'bright');assert.equal(storage.get('guardianchat-theme'),'bright');
const shop=new Node('button');shop.id='tabShop';shop.onclick=()=>shopClicks++;body.append(shop);walk(panel).find(n=>n.textContent==='My shop').click();assert.equal(shopClicks,1);assert(panel.hidden);
settings.open('play',trigger);assert.equal(mounted,1,'No duplicate picker');assert.equal(refreshed,2);assert.match(content(panel),/Orbit Play settings/);assert(!content(panel).includes('My shop'));
handlers.keydown({key:'Escape',preventDefault(){}});assert(panel.hidden);assert.equal(document.activeElement,trigger);
assert.throws(()=>settings.open('wallet',trigger),/Choose Play or Plaza/);
const header=new Node('header'),menu=new Node('aside');menu.id='navigationMenu';header.append(menu);body.append(header);settings.portal();assert.equal(menu.parentElement,body,'Chat menu escapes the lower header stacking context');assert(!header.children.includes(menu));
const css=fs.readFileSync(__dirname+'/navigation.css','utf8');assert.match(css,/#navigationMenu,#settingsPanel\{width:50vw!important/);assert.match(css,/z-index:12020!important/);
for(const file of ['index.html','gaming.html','market.html']){const source=fs.readFileSync(__dirname+'/'+file,'utf8');assert(source.indexOf('/module-settings.js')<source.indexOf('/module-navigation.js'),file+' loads settings before its trigger')}
console.log('Module-owned settings, account appearance, current-page preservation, portal stacking, 50% geometry and Escape/focus checks passed.');
