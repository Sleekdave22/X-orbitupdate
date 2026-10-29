/** Section-owned settings: account personalization plus existing module controls.
 * Opening and closing never navigate or recreate a module's current content.
 */
(()=>{
 'use strict';
 let trigger=null;

 /** Create text-only markup. @param {string} tag Element type.
  * @param {string} text Label. @returns {HTMLElement} Node; DOM errors propagate.
  */
 function node(tag,text=''){const element=document.createElement(tag);element.textContent=text;return element}

 /** Escape header stacking contexts without replacing any existing handlers.
  * @returns {void} DOM errors propagate; no route fallback is attempted.
  */
 function portal(){
  for(const id of ['navigationMenu','settingsShade','settingsPanel']){const element=document.getElementById(id);if(element&&element.parentElement!==document.body)document.body.append(element)}
 }

 /** Hide the drawer and restore focus. @returns {void} No navigation side effects.
  * Detached triggers are ignored; unexpected DOM errors propagate.
  */
 function close(){
  const panel=document.getElementById('settingsPanel'),shade=document.getElementById('settingsShade');
  if(panel)panel.hidden=true;if(shade)shade.hidden=true;
  trigger?.setAttribute('aria-expanded','false');if(trigger?.isConnected)trigger.focus();
 }

 /** Open a real existing section control, preserving its original action.
  * @param {string} selector Control selector. @returns {void}
  * Missing controls display an inline explanation instead of simulated success.
  */
 function useControl(selector){
  const target=document.querySelector(selector);
  if(!target){document.getElementById('moduleSettingsStatus').textContent='This control becomes available after the page finishes loading.';return}
  close();if(target.tagName==='DETAILS'){target.open=true;target.querySelector('input,button')?.focus()}else target.click();
 }

 /** Mount a viewport-owned drawer once, reusing the account palette picker.
  * @returns {HTMLElement} Panel. @throws {Error} Unexpected DOM failures.
  * No session credentials or account-private data are placed in the markup.
  */
 function mount(){
  portal();const existing=document.getElementById('settingsPanel');if(existing)return existing;
  const shade=node('div');shade.id='settingsShade';shade.hidden=true;shade.onclick=close;
  const panel=node('aside');panel.id='settingsPanel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-labelledby','moduleSettingsTitle');
  const heading=node('h2');heading.id='moduleSettingsTitle';const dismiss=node('button','Close');dismiss.id='closeSettings';dismiss.type='button';dismiss.onclick=close;
  const explanation=node('p','Appearance and colour choices belong to your account and apply across X-Orbit.');explanation.className='muted';
  const label=node('label','Appearance');label.setAttribute('for','appearance');const appearance=node('select');appearance.id='appearance';
  for(const [value,title] of [['dark','Dark'],['bright','Light']]){const option=node('option',title);option.value=value;appearance.append(option)}
  appearance.onchange=()=>{document.documentElement.dataset.theme=appearance.value;try{localStorage.setItem('guardianchat-theme',appearance.value)}catch(_){/* Current page still changes when storage is unavailable. */}};
  const tools=node('section');tools.id='moduleSettingsTools';const status=node('p');status.id='moduleSettingsStatus';status.setAttribute('role','status');
  const copyright=node('footer','Copyright X ORBIT ©');copyright.className='settings-copyright';
  panel.append(heading,dismiss,explanation,label,appearance,tools,status,copyright);document.body.append(shade,panel);window.OrbitPersonalization?.mount();
  return panel;
 }

 /** Open settings over the current module without going through Chat.
  * @param {'play'|'market'} module Stable internal section name.
  * @param {HTMLElement} opener Settings icon, for keyboard focus restoration.
  * @returns {void} @throws {TypeError} Unknown section; DOM failures propagate.
  */
 function open(module,opener){
  if(!['play','market'].includes(module))throw new TypeError('Choose Play or Plaza settings');
  trigger=opener;const panel=mount();
  document.getElementById('moduleSettingsTitle').textContent=module==='market'?'Orbit Plaza settings':'Orbit Play settings';
  document.getElementById('appearance').value=document.documentElement.dataset.theme==='bright'?'bright':'dark';
  const tools=document.getElementById('moduleSettingsTools');tools.replaceChildren(node('h3',module==='market'?'Plaza tools':'Play tools'));
  const controls=module==='market'?[['Search and location preferences','#marketFilters'],['My shop','#tabShop'],['Requests & Hot Demand','#marketDemand'],['Plaza notifications','#marketActivityBell']]:[['Gaming profile and availability','main>nav button[data-tab="profile"]'],['Matches and results','main>nav button[data-tab="fixtures"]'],['Play notifications','#playActivityBell']];
  for(const [label,selector] of controls){const button=node('button',label);button.type='button';button.onclick=()=>useControl(selector);tools.append(button)}
  document.getElementById('moduleSettingsStatus').textContent='';panel.dataset.section=module;panel.hidden=false;document.getElementById('settingsShade').hidden=false;
  trigger?.setAttribute('aria-expanded','true');document.getElementById('closeSettings').focus();window.OrbitPersonalization?.refresh(true);
 }

 /** Keep keyboard focus within an open module drawer.
  * @param {KeyboardEvent} event Key event. @returns {void}
  * Chat retains its existing handlers; only these module-owned panels are handled.
  */
 function keydown(event){
  const panel=document.getElementById('settingsPanel');if(!panel||panel.hidden||!panel.dataset.section)return;
  if(event.key==='Escape'){event.preventDefault();close();return}
  if(event.key!=='Tab')return;
  const controls=[...panel.querySelectorAll('button:not([disabled]),select,input:not([disabled])')];if(!controls.length)return;
  const first=controls[0],last=controls[controls.length-1];
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
 }
 window.OrbitModuleSettings={open,close,portal};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',portal);else portal();
 document.addEventListener('keydown',keydown);
})();
