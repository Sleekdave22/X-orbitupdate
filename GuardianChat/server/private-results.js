'use strict';
// Supersedes the earlier peer-photo result room. Evidence never enters its chat.
/** Open a participant's private result conversation and maintain its receipts.
 * @param {string} id Match/fixture ID, authorized on every backend request.
 * @returns {Promise<void>} Resolves after initial render and polling setup.
 * @throws {Error} Initial load failures; later errors appear in the page.
 */
async function privateResultRoom(id){
 resultCleanup?.();streamCleanup?.();
 const owner=account.id,initial=await api('/gamebox/result-state?room='+encodeURIComponent(id)+'&after=0');
 if(account.id!==owner)return;
 tab='result-room';const view=$('view');view.replaceChildren();
 let closed=false,busy=false,uploading=false,signature='',commentSignature='',selected=null,uploadError='',captureWidget=null;
 const state=node('p','','muted'),area=node('section','','private-result-review'),comments=node('div','','room-comments');
 const returnToMatches=async()=>{resultCleanup?.();tab=initial.kind==='open'?'open':'fixtures';await load()};
 view.append(button('‹ Matches',returnToMatches),node('h2',initial.names[initial.a]+' vs '+initial.names[initial.b]),state,
  node('p','Registered game IDs: '+(initial.game_ids?.[initial.a]||'Unavailable')+' / '+(initial.game_ids?.[initial.b]||'Unavailable'),'muted'),
  node('p','Keep your game result screen open until confirmation. Both gaming IDs and scores must remain visible.','muted'));
 const messages=node('form');messages.dataset.formInline='1';messages.className='result-chat-composer';
 const draft=input(messages,'Message to your opponent','text'),send=node('button','➤');draft.placeholder='Message your opponent…';send.type='submit';send.setAttribute('aria-label','Send result chat message');messages.append(send);view.classList.add('private-result-chat');view.append(comments,area,messages);
 messages.onsubmit=async e=>{e.preventDefault();if(!draft.value.trim()||closed)return;send.disabled=true;try{await api('/gamebox/result_comment',{room:id,text:draft.value.trim()});draft.value='';await poll()}catch(e){state.textContent=e.message}finally{send.disabled=false}};
 /** Render safe receipts without interrupting an unsent camera capture.
  * @param {Object} r Authenticated result packet, never peer evidence.
  * @returns {void} UI errors propagate to the polling handler.
  */
 function render(r){
  const review=r.evidence_review||{state:'not_submitted',submitted:false,received:0};
  const stamp=JSON.stringify([r.state,r.reports,r.can_report,review,r.final_score]);
  const done=['verified','confirmed','void','cancelled','walkover'].includes(r.state);
  if(stamp===signature||uploading||((selected||captureWidget?.active())&&!review.submitted&&!done))return;signature=stamp;captureWidget?.destroy();captureWidget=null;area.replaceChildren();selected=null;
  state.textContent=done?'Result: '+r.state.replaceAll('_',' '):review.submitted?'Waiting for review':'Result: '+r.state.replaceAll('_',' ');
  messages.hidden=done;
  if(done){
   if(['verified','confirmed'].includes(r.state)&&typeof offerGamingVibe==='function'){vibePromptChecked=false;offerGamingVibe()}
   if(r.final_score)area.append(node('strong',r.final_score[0]+' – '+r.final_score[1],'score'));
   area.append(node('p',r.final_score?'Final result saved. Relevant rankings, standings and match history have updated.':'This match is closed; no new evidence can be submitted.'),
    button('View standings / rankings',async()=>{resultCleanup?.();tab=r.kind==='fixture'?'table':'open';await load()}));
   appendResultAppeal(area,r,async()=>{signature='';await poll()});return;
  }
  const own=r.reports.find(x=>x.uid===owner);
  if(own&&Number.isInteger(own.score_a)&&Number.isInteger(own.score_b))area.append(node('p','Your independent score: '+own.score_a+' – '+own.score_b));
  if(review.state!=='not_submitted'){
   area.append(node('h3',review.state==='needs_human'?'Independent review required':review.stage==='video'?'Video evidence required':'Private evidence review'),
    node('p',review.received+' of 2 '+(review.stage==='video'?'recordings':'photos')+' received.','muted'));
   if(review.deadline)area.append(node('p','Respond by '+new Date(review.deadline*1000).toLocaleTimeString()+'. After 15 minutes, validated proof can decide the result if the other player is silent.','muted'));
   if(review.state==='waiting_other')area.append(node('p',review.submitted?'Your capture was received privately. Waiting for the other player or the response deadline.':review.stage==='video'?'Record navigation on the PC/TV to match details and final scores. Keep both gaming IDs visible.':'The other player has submitted privately. Take your own camera photo to begin review.'));
   else if(['queued','processing'].includes(review.state))area.append(node('p','Waiting for review—clear results are normally processed within a few minutes. Unclear or conflicting photo evidence will require video.'));
   else if(review.state==='needs_human')area.append(node('p','The evidence needs an independent reviewer. No ranking or league points change until a decision is recorded.'));
   if(review.submitted){area.append(node('p','Upload complete. Your original is locked; it is not shown to the other player.','muted'));return;}
   if(!review.can_upload){area.append(node('p','The response window has closed. Await the evidence decision.'));return;}
  }
  if(r.kind==='open'&&r.state==='in_progress'){
   area.append(button('Match finished · enter scores',async()=>{await api('/gamebox/complete',{match:id});signature='';await poll()}));return;
  }
  const disputed=['disputed','review'].includes(r.state)||review.state!=='not_submitted';
  if(!disputed&&r.verification!=='legacy'){
   area.append(node('p','Enter scores independently in the fixed player order. Matching reports count automatically.','muted'));
   if(!own&&r.can_report){
    const f=node('form'),a=input(f,r.names[r.a]+' score','a','number'),b=input(f,r.names[r.b]+' score','b','number');
    a.min=b.min=0;a.max=b.max=99;a.required=b.required=true;
    const submit=node('button','Submit my independent score');submit.type='submit';f.append(submit);
    f.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{
     if(r.kind==='open')await api('/gamebox/report',{match:id,a:Number(a.value),b:Number(b.value)});
     else await api('/gaming/report',{league:data.league.id,fixture:id,score_a:Number(a.value),score_b:Number(b.value)});
     signature='';await poll();
    }catch(e){state.textContent=e.message;submit.disabled=false}};area.append(f);
   }else if(!own)area.append(node('p','Finish the match and both check-ins before submitting results.'));
   return;
  }
  if(!(disputed||r.can_report)){area.append(node('p','Complete both check-ins before submitting a result.'));return;}
  area.append(node('p','Use your phone camera to capture the PC/TV. Photo and video evidence goes privately to the review backend.','muted'));
  const form=node('form'),detail=node('p',uploadError,'muted'),submit=node('button','Submit privately for review');submit.type='submit';submit.disabled=true;submit.hidden=true;
  form.dataset.formInline='1';
  captureWidget=OrbitEvidenceCamera.mount({container:form,videoRequired:review.stage==='video',onCapture:blob=>{selected=blob;uploadError='';submit.disabled=!blob;submit.hidden=!blob;detail.textContent=blob?'Camera capture ready for private submission.':''}});
  form.append(detail,submit);
  form.onsubmit=async e=>{e.preventDefault();if(!selected||uploading||closed)return;uploading=true;submit.disabled=true;detail.textContent='Uploading privately…';
   try{const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('Could not read this file'));reader.readAsDataURL(selected)});
    if(closed||account.id!==owner)return;
    await api('/gamebox/result_evidence',{room:id,image:encoded,mime:selected.type,capture_mode:'camera'});selected=null;uploadError='';signature='';captureWidget?.destroy();captureWidget=null;
   }catch(e){uploadError=e.message;detail.textContent=e.message;submit.disabled=false}
   finally{uploading=false;await poll()}
  };area.append(form);
 }
 async function poll(){if(closed||busy||account.id!==owner)return;busy=true;try{
  const r=await api('/gamebox/result-state?room='+encodeURIComponent(id)+'&after=0');
  if(closed||account.id!==owner)return;render(r);
  const stamp=JSON.stringify(r.comments);if(stamp!==commentSignature){commentSignature=stamp;comments.replaceChildren(...r.comments.map(c=>node('p',c.name+': '+c.text)));comments.scrollTop=comments.scrollHeight}
 }catch(e){if(!closed)state.textContent=e.message}finally{busy=false}}
 const timer=setInterval(poll,2000),leaving=()=>resultCleanup?.();
 resultCleanup=()=>{closed=true;view.classList.remove('private-result-chat');clearInterval(timer);selected=null;captureWidget?.destroy();captureWidget=null;window.removeEventListener('pagehide',leaving);resultCleanup=null};
 window.addEventListener('pagehide',leaving);render(initial);await poll();
}
resultRoom=privateResultRoom;
evidenceForm=m=>privateResultRoom(m.id);
report=f=>privateResultRoom(f.id);

function privateVideoTools(match){
 const panel=node('section');
 for(const evidence of match.video_evidence||[]){
  panel.append(button('View private video · '+evidence.uid,async()=>{try{
   const r=await fetch('/gamebox/review-video?room='+encodeURIComponent(match.id)+'&player='+encodeURIComponent(evidence.uid),{headers:{Authorization:'Bearer '+account.token}});
   if(!r.ok)throw Error('Video evidence is unavailable');
   const clip=node('video'),url=URL.createObjectURL(await r.blob());clip.controls=true;clip.playsInline=true;clip.src=url;clip.style.maxWidth='100%';clip.onended=clip.onerror=()=>URL.revokeObjectURL(url);window.addEventListener('pagehide',()=>URL.revokeObjectURL(url),{once:true});panel.append(clip);
  }catch(e){note(e.message)}}));
 }
 return panel;
}
const originalOpenReview=reviewOpen;
/** Extend existing review with private findings; preserve its decision action.
 * @param {Object} m Authorized Studio match.
 * @returns {Promise<void>} Rejects on initial review failures; summary errors show inline.
 */
reviewOpen=async m=>{if(m.state==='verified')$('view').replaceChildren(button('‹ Studio',()=>{tab='studio';render()}),node('h2','Final result appeal'));else await originalOpenReview(m);$('view').append(privateVideoTools(m));await appendReviewSummary($('view'),m);};
const originalFixtureReview=review;
/** Retain fixture review and add its independent findings.
 * @param {Object} f Authorized fixture. @returns {void} Summary errors show inline.
 * @throws {Error} Existing fixture rendering failures retain their caller's handling.
 */
review=f=>{originalFixtureReview(f);$('view').append(privateVideoTools(f));void appendReviewSummary($('view'),f);};

/** Add an appeal action after finalization without exposing either player's proof.
 * @param {HTMLElement} panel Result container.
 * @param {Object} result Participant-safe result-state packet.
 * @param {function(): Promise<void>} refresh Reload receipts after submission.
 * @returns {void} Submission failures stay visible; scores are never edited here.
 */
function appendResultAppeal(panel,result,refresh){
 const receipt=result.evidence_review||{};
 if(receipt.appeal_state)panel.append(node('p','Appeal: '+receipt.appeal_state.replaceAll('_',' ')+'. Evidence is retained while review or correction is pending.','muted'));
 if(!receipt.can_appeal)return;
 panel.append(node('p','Request independent review by '+new Date(receipt.appeal_until*1000).toLocaleString()+'.','muted'));
 const launch=button('Request review / appeal',()=>{
  launch.disabled=true;const form=node('form'),reason=input(form,'Explain what needs reviewing','reason'),message=node('p','','muted'),send=node('button','Submit appeal');
  form.dataset.formInline='1';reason.required=true;reason.minLength=10;reason.maxLength=1000;send.type='submit';form.append(send,message);panel.append(form);
  form.onsubmit=async event=>{event.preventDefault();if(send.disabled)return;send.disabled=true;try{await api('/gamebox/evidence_appeal',{room:result.id,reason:reason.value.trim()});await refresh()}catch(error){message.textContent=error.message;send.disabled=false}};
 });panel.append(launch);
}

/** Fetch and display evidence findings only through the independent-review API.
 * @param {HTMLElement} view Existing authorized review page.
 * @param {Object} match Match/fixture with id; backend checks roles again.
 * @returns {Promise<void>} Network/permission errors remain visible without proof.
 */
async function appendReviewSummary(view,match){
 const section=node('section','','card');section.append(node('h3','Automated findings and appeal review'));view.append(section);
 try{
  const summary=await api('/gamebox/review-summary?room='+encodeURIComponent(match.id));
  section.append(node('p',summary.limitation,'muted'));
  if(summary.review)section.append(node('p','Review: '+summary.review.state+' · '+summary.review.stage+' · '+summary.review.policy),node('p',summary.review.reason||'No escalation reason recorded.','muted'));
  for(const report of summary.reports)section.append(node('p','Independent report · '+report.uid+': '+report.score_a+' – '+report.score_b));
  for(const finding of summary.findings){
   const analysis=finding.analysis;section.append(node('h4',finding.uid+' · '+finding.stage),node('p',analysis?.score?'Read score: '+analysis.score.join(' – '):'Inconclusive / not yet analyzed'),node('p',analysis?.reason||'Awaiting analysis.','muted'));
   if(analysis?.text){const text=node('pre',analysis.text);text.style.whiteSpace='pre-wrap';section.append(text)}
  }
  for(const appeal of summary.appeals){
   section.append(node('h4','Appeal · '+appeal.uid),node('p',appeal.reason),node('p','Status: '+appeal.state,'muted'));
   if(appeal.decision)section.append(node('p','Decision: '+appeal.decision));
   if(appeal.state!=='open')continue;
   const form=node('form'),reason=input(form,'Independent decision reason','reason'),select=node('select'),message=node('p','','muted'),send=node('button','Record appeal decision');
   form.dataset.formInline='1';reason.required=true;reason.minLength=10;reason.maxLength=1000;select.setAttribute('aria-label','Appeal outcome');
   for(const [value,label] of [['upheld','Uphold recorded result'],['correction_required','Require audited correction · retain evidence']]){const option=node('option',label);option.value=value;select.append(option)}
   select.value='upheld';send.type='submit';form.append(select,send,message);section.append(form);
   form.onsubmit=async event=>{event.preventDefault();if(send.disabled)return;send.disabled=true;try{await api('/gamebox/evidence_appeal_decide',{room:match.id,player:appeal.uid,outcome:select.value,reason:reason.value.trim()});message.textContent='Decision recorded. Final scores were not silently changed.'}catch(error){message.textContent=error.message;send.disabled=false}};
  }
  if(summary.retention.evidence_held)section.append(node('p','Evidence cleanup is paused for an open appeal or required correction.','muted'));
 }catch(error){section.append(node('p','Review summary unavailable: '+error.message,'muted'))}
}
