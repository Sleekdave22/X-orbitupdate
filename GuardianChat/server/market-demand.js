/* Additive Plaza requests panel; existing listing/navigation controls stay intact. */
(()=>{'use strict';
const $=id=>document.getElementById(id),node=(tag,text='')=>{const n=document.createElement(tag);n.textContent=text;return n};
let ctx,ticket=0,offset=0,sending=false,saving=false,attempt=null;
const status=text=>$('demandStatus').textContent=text;
function button(label,action){const b=node('button',label);b.type='button';b.onclick=action;return b}
function selectedCategories(){return [...$('demandSellerCategories').querySelectorAll('input:checked')].map(x=>x.value)}
function categories(catalog,prefs){
 if(!$('demandCategory').children.length)for(const c of catalog.categories){const o=node('option',c.name);o.value=c.id;$('demandCategory').append(o)}
 const choices=$('demandSellerCategories');choices.replaceChildren();
 for(const c of catalog.categories){const l=node('label'),input=node('input');input.type='checkbox';input.value=c.id;input.checked=prefs.categories.includes(c.id);l.append(input,node('span',c.name));choices.append(l)}
 $('demandSellerUpdates').checked=prefs.updates;$('demandSellerSettings').hidden=!ctx.seller();
}
function row(demand,own=false){
 const card=node('article');card.className='mcard';card.dataset.demand=demand.id;
 card.append(node('strong',demand.title),node('p',demand.description),node('small',(demand.hot?'Hot Demand · ':'')+demand.requesters+' distinct accounts requesting'));
 const action=button(own||demand.mine?'Withdraw my request':'Request this too',async()=>{
  action.disabled=true;
  try{
   if(own||demand.mine)await ctx.api('/market/demand_withdraw',{id:demand.id});
   else await ctx.api('/market/demand_request',{title:demand.title,description:demand.description,category_id:demand.category,listing_type:demand.kind,client_id:crypto.randomUUID()});
   await load();status(own||demand.mine?'Request withdrawn':'Added to your requests');
  }catch(e){status(e.message);action.disabled=false}
 });
 card.append(action);return card;
}
async function load(append=false){
 const gen=++ticket;status('Loading requests…');
 try{
  const [result,catalog]=await Promise.all([ctx.api('/market/demands?offset='+(append?offset:0)),ctx.catalog()||ctx.api('/market/catalog')]);
  if(gen!==ticket)return;
  if(!append){offset=0;$('demandList').replaceChildren();$('demandMine').replaceChildren(node('h3','My requests'));for(const d of result.mine)$('demandMine').append(row(d,true));categories(catalog,result.preferences)}
  for(const d of result.demands)$('demandList').append(row(d));
  if(!append&&!result.demands.length)$('demandList').append(node('p','No requests yet. Describe what you need.'));
  offset+=result.demands.length;$('moreDemands').hidden=!result.more;
  if($('marketDemand').open&&!document.hidden)await ctx.onVisible?.(result.demands.map(d=>d.id));
  status('Hot Demand starts at '+result.policy.threshold+' distinct accounts. Extra opportunities stay here; Hot Demand pushes are limited to '+result.policy.daily_push_limit+' per day.');
 }catch(e){status(e.message)}
}
function mount(options){
 ctx=options;const panel=$('marketDemand');panel.hidden=!ctx.account;if(!ctx.account)return;
 panel.addEventListener('toggle',()=>{if(panel.open)load()});
 $('refreshDemands').onclick=()=>load();$('moreDemands').onclick=()=>load(true);
 $('demandRequest').onsubmit=async e=>{
  e.preventDefault();if(sending)return;
  const body={title:$('demandTitle').value.trim(),description:$('demandDescription').value.trim(),category_id:$('demandCategory').value,listing_type:$('demandKind').value},signature=JSON.stringify(body);
  if(attempt?.signature!==signature)attempt={signature,id:crypto.randomUUID()};
  sending=true;$('sendDemand').disabled=true;
  try{const r=await ctx.api('/market/demand_request',{...body,client_id:attempt.id});$('demandRequest').reset();attempt=null;await load();status(r.already_requested?'Already in your requests':'Request added')}catch(error){status(error.message)}finally{sending=false;$('sendDemand').disabled=false}
 };
 $('demandSellerPreferences').onsubmit=async e=>{
  e.preventDefault();if(saving)return;saving=true;$('saveDemandPreferences').disabled=true;
  try{await ctx.api('/market/demand_preferences',{updates:$('demandSellerUpdates').checked,categories:selectedCategories()});status('Demand notification preferences saved')}catch(error){status(error.message)}finally{saving=false;$('saveDemandPreferences').disabled=false}
 };
}
async function open(id){
 if(!ctx)return;const panel=$('marketDemand');panel.open=true;
 try{const r=await ctx.api('/market/demand?id='+encodeURIComponent(id));$('demandFocus').replaceChildren(node('h3','Requested opportunity'),row(r.demand));panel.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})}catch(e){status(e.message)}
}
window.OrbitDemand={mount,open};
})();
