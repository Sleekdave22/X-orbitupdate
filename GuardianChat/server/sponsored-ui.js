'use strict';
// Uses the shared account, match lifecycle and results interface. No local scores.
let sponsoredLeagueId=null;
function orbitHome(view){
 view.append(node('h2','Your arena'),node('p','Play free ranked matches, follow your progress, and join published sponsored leagues.','muted'));
 const actions=node('div','','actions');actions.append(button('Find a match',()=>{tab='open';render()}),button('My games / Add Game',openGameIdentities),button('Global rankings',()=>openGlobalRankings()),button('My profile',openGamingProfile));view.append(actions);
 if(!data.profile){view.append(button('Create your gaming profile',openGamingProfile));return}
 for(const r of data.engine.ratings){const c=node('article','','card');c.append(node('h3',data.games[r.game]||r.game),node('strong','Rating '+Math.round(r.rating)),node('p',r.provisional?'Provisional · '+r.verified_placements+'/'+r.placement_required+' placements':r.grade),button('View game profile',()=>openRankProfile(account.id,r.game)));view.append(c)}
 const active=(data.engine.matches||[]).filter(m=>!['verified','cancelled'].includes(m.state));if(active.length){view.append(node('h3','Your current match'));active.forEach(m=>view.append(orbitMatchCard(m)))}
 for(const league of data.sponsored.leagues.filter(l=>['PUBLISHED','REGISTRATION_OPEN','REGISTRATION_CLOSED','ACTIVE','FINALISING'].includes(l.state)))view.append(sponsoredSummary(league));
}
function sponsoredSummary(league){const c=node('article','','card');c.append(node('h3',league.name),node('p',(data.games[league.game]||league.game)+' · '+league.state.replaceAll('_',' ')),node('p','Supported by '+(league.sponsor||'Sponsor to be confirmed')+' · '+league.registered+' registered'),button('View league',()=>{sponsoredLeagueId=league.id;tab='sponsored';render()}));return c}
function orbitMatchCard(m){
 const c=node('article','','card');c.append(node('h3',(m.name_a||m.gid_a)+' vs '+(m.name_b||m.gid_b)),node('small',m.match_type==='SPONSORED_LEAGUE'?'Sponsored league · global rating unchanged':'Global ranked match'),node('p',m.state.replaceAll('_',' ')));
 if(m.state==='verified')c.append(node('strong',m.score_a+' – '+m.score_b));
 const actions=node('div','','actions'),act=async action=>{await api('/gamebox/'+action,{match:m.id});await load()};
 const safe=(label,fn)=>{const b=button(label,async()=>{b.disabled=true;try{await fn()}catch(e){note(e.message)}finally{b.disabled=false}});actions.append(b)};
 if(m.state==='proposed'){
  const accepted=m.a===account.id?m.accepted_a:m.accepted_b;
  if(!accepted)safe('Accept opponent',()=>act('accept'));else c.append(node('p','Accepted · waiting for your opponent','muted'));
  safe('Decline',()=>act('cancel'));
 }
 if(m.state==='awaiting_checkin'){const ready=m.a===account.id?m.ready_a:m.ready_b;if(!ready)safe('Check in · ready',()=>act('checkin'));else c.append(node('p','Ready · waiting for your opponent','muted'))}
 if(['in_progress','awaiting_results','review','disputed','verified'].includes(m.state))safe('Result chat',()=>resultRoom(m.id));
 if(['review','disputed'].includes(m.state))safe('Submit review evidence',()=>evidenceForm(m));
 if(m.state==='cancelled'&&m.match_type==='SPONSORED_LEAGUE')safe('Request independent review',async()=>{const reason=prompt('Explain why this voided match should be reviewed. In-app appeals are available while the league is active or finalising.');if(!reason)return;await api('/leagues/appeal',{league:m.league_id,match:m.id,reason});note('Review request recorded. No points have been awarded.')});
 appendMatchStreamButtons(actions,m,'open');c.append(actions);return c;
}
function orbitMatchHistory(view){
 view.append(node('h2','Match history'),node('p','Each result identifies whether it affected global ratings or league points.','muted'));
 for(const m of data.engine.matches)view.append(orbitMatchCard(m));if(!data.engine.matches.length)view.append(node('p','No matches yet.'));
 view.append(button('Earlier competition history',()=>{tab='leagues';render()}));
}
async function sponsoredView(view){
 const leagues=data.sponsored.leagues.filter(l=>l.state!=='DRAFT');
 if(!sponsoredLeagueId){if(leagues.length===1)sponsoredLeagueId=leagues[0].id;else{view.append(node('h2','Sponsored leagues'));leagues.forEach(l=>view.append(sponsoredSummary(l)));if(!leagues.length)view.append(node('p','No sponsored league has been published. Free global matches remain available.'));return}}
 const host=node('section');view.append(host);let signature='',loading=false;
 async function refresh(){if(tab!=='sponsored'||!host.isConnected||loading)return;loading=true;try{
  let info=await api('/leagues/status?'+new URLSearchParams({league:sponsoredLeagueId}));
  if(info.queue){await api('/leagues/heartbeat',{league:sponsoredLeagueId});info=await api('/leagues/status?'+new URLSearchParams({league:sponsoredLeagueId}))}
  if(!host.isConnected||tab!=='sponsored')return;
  const stamp=JSON.stringify({...info,queue:info.queue?{league:info.queue.league}:null});if(stamp===signature)return;signature=stamp;host.replaceChildren();const l=info.league;
  host.append(button('‹ All leagues',()=>{sponsoredLeagueId=null;signature='';view._livePage=null;view.replaceChildren();view.append(node('h2','Sponsored leagues'));leagues.forEach(x=>view.append(sponsoredSummary(x)))}),node('h2',l.name),node('p',l.description),node('p',l.state.replaceAll('_',' ')+' · '+(data.games[l.game]||l.game)+' · '+l.platform,'muted'));
  if(l.sponsor){host.append(node('strong','Supported by '+l.sponsor));if(l.sponsor_url){const link=node('a','Visit sponsor');link.href=l.sponsor_url;link.target='_blank';link.rel='noopener noreferrer sponsored';host.append(link)}}
  if(l.prize)host.append(node('p',l.prize));
  host.append(node('p','Registration closes '+new Date(l.registration_closes*1000).toLocaleString()),node('p','Play '+new Date(l.starts*1000).toLocaleString()+' — '+new Date(l.ends*1000).toLocaleString()),node('p','Win 3 · draw 1 · loss 0. Each opponent counts once per league. League matches never change your global rating. No daily match cap.','muted'),node('p','Disputes award no points. Unresolved cases are voided 48 hours after their evidence deadline; an independent administrator can review an appeal.','muted'));
  const status=node('p');status.setAttribute('role','status');host.append(status);
  const action=(label,name)=>host.append(phaseBButton(label,status,async()=>{const r=await api('/leagues/'+name,{league:l.id});if(r.message)status.textContent=r.message;signature='';await refresh()}));
  if(!info.joined&&l.state==='REGISTRATION_OPEN')action('Register for this league','register');
  if(info.joined&&l.state==='ACTIVE'&&!info.matches.some(m=>!['verified','cancelled'].includes(m.state)))action(info.queue?'Cancel search':'Find league opponent',info.queue?'queue_leave':'queue');
  if(info.queue)host.append(node('p','Searching the compatible league pool… Keep this page open. Declines continue the search automatically.','muted'));
  host.append(node('p',info.metrics.registered+' registered · '+info.metrics.verified_matches+' verified matches'));
  const standings=node('details');standings.append(node('summary','League standings'));const wrap=node('div','','table-wrap'),table=node('table'),head=node('tr');for(const text of ['#','Player','P','W','D','L','Points'])head.append(node('th',text));table.append(head);for(const p of info.table){const tr=node('tr');for(const v of [p.position,p.name,p.played,p.wins,p.draws,p.losses,p.points])tr.append(node('td',String(v)));table.append(tr)}wrap.append(table);standings.append(wrap,node('p',info.tie_policy,'muted'));host.append(standings);
  for(const m of info.matches)host.append(orbitMatchCard(m));
 }catch(e){if(host.isConnected)note(e.message)}finally{loading=false}}
 view._livePage={tab:'sponsored',admin:data.can_admin,refresh};await refresh();
 api('/leagues/visit',{league:sponsoredLeagueId}).catch(()=>{});
}
async function openSponsoredAdmin(){
 const {d,body,status}=phaseBDialog('Sponsored league controls');
 async function refresh(){const list=await api('/leagues/list');if(!d.open)return;body.replaceChildren();
 body.append(node('p','Published rules stay frozen. One league can be active and one can accept registrations. Statistics and match results are calculated by the server.','muted'));
 const pending=await api('/leagues/appeals');if(!d.open)return;
 if(pending.appeals.length)body.append(node('h3','Independent review requests'));
 for(const appeal of pending.appeals){const c=node('article','','card');c.append(node('strong','Match '+appeal.match),node('p',appeal.reason));for(const decision of ['uphold_void','reopen_review'])c.append(phaseBButton(decision.replaceAll('_',' '),status,async()=>{const reason=prompt('Record your independent evidence review and reason. Reopening holds both players until the review is resolved.');if(!reason)return;await api('/leagues/appeal_decide',{league:appeal.league_id,match:appeal.match,player:appeal.uid,decision,reason});await refresh()}));body.append(c)}
 body.append(form('Create a sponsored league draft',f=>{
  input(f,'League name','name');gameSelect(f);const label=node('label','Gaming platform'),s=node('select');s.name='platform';for(const key of ['mobile','console','pc','crossplay']){const o=node('option',key);o.value=key;s.append(o)}label.append(s);f.append(label);
  input(f,'Description','description');input(f,'Confirmed sponsor','sponsor');input(f,'Sponsor website (HTTPS)','sponsor_url','url');input(f,'Published reward details (only funded commitments)','prize');
  const now=Date.now()/1000;for(const [key,label,offset] of [['registration_opens','Registration opens',60],['registration_closes','Registration closes',86400],['starts','League starts',86460],['ends','League ends',8*86400]])input(f,label,key,'datetime-local',localDatetime(now+offset));input(f,'Participant capacity','capacity','number',100);
 },async f=>{const values=fieldValues(f);for(const key of ['registration_opens','registration_closes','starts','ends'])values[key]=Math.floor(new Date(values[key]).getTime()/1000);values.capacity=Number(values.capacity);try{await api('/leagues/create',values);status.textContent='Draft saved';await refresh()}catch(e){status.textContent=e.message}}));
 for(const league of list.leagues){const c=node('article','','card');c.append(node('h3',league.name),node('p',league.state+' · '+league.registered+' registered'));
  if(league.state!=='DRAFT')c.append(phaseBButton('Open league',status,()=>{d.close();sponsoredLeagueId=league.id;tab='sponsored';render()}));
  const next={DRAFT:['PUBLISHED','CANCELLED'],PUBLISHED:['REGISTRATION_OPEN','REGISTRATION_CLOSED','CANCELLED'],REGISTRATION_OPEN:['REGISTRATION_CLOSED','CANCELLED'],REGISTRATION_CLOSED:['ACTIVE','CANCELLED'],ACTIVE:['FINALISING'],FINALISING:['COMPLETED'],COMPLETED:['ARCHIVED']}[league.state]||[];
  for(const state of next)c.append(phaseBButton(state.replaceAll('_',' '),status,async()=>{const reason=prompt('Explain this lifecycle change. Published deadlines and unresolved matches are checked by the server.');if(!reason)return;await api('/leagues/transition',{league:league.id,version:league.version,state,reason});status.textContent='Lifecycle change recorded';await refresh()}));
  c.append(phaseBButton('League audit',status,async()=>{const r=await api('/leagues/audit?league='+league.id);const log=node('section');for(const e of r.events)log.append(node('p',new Date(e.created*1000).toLocaleString()+' · '+e.action+' · '+e.actor+' · '+e.reason));c.append(log)}));body.append(c);
 }
 }
 try{await refresh()}catch(e){status.textContent=e.message}
}
