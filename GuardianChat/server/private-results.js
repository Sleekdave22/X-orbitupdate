'use strict';
// Supersedes the earlier peer-photo result room. Evidence never enters its chat.
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
  node('p','Do not close the game result screen until confirmation. Keep both gaming IDs and scores visible in case camera photo or video proof is needed.','card'),area);
 const messages=node('form');messages.dataset.formInline='1';
 const draft=input(messages,'Message to your opponent','text'),send=node('button','➤');send.type='submit';messages.append(send);view.append(comments,messages);
 messages.onsubmit=async e=>{e.preventDefault();if(!draft.value.trim()||closed)return;send.disabled=true;try{await api('/gamebox/result_comment',{room:id,text:draft.value.trim()});draft.value='';await poll()}catch(e){state.textContent=e.message}finally{send.disabled=false}};
 function render(r){
  const review=r.evidence_review||{state:'not_submitted',submitted:false,received:0};
  const stamp=JSON.stringify([r.state,r.reports,r.can_report,review,r.final_score]);
  const done=['verified','confirmed','void','cancelled','walkover'].includes(r.state);
  if(stamp===signature||uploading||((selected||captureWidget?.active())&&!review.submitted&&!done))return;signature=stamp;captureWidget?.destroy();captureWidget=null;area.replaceChildren();selected=null;
  state.textContent=done?'Result: '+r.state.replaceAll('_',' '):review.submitted?'Waiting for review':'Result: '+r.state.replaceAll('_',' ');
  messages.hidden=done;
  if(done){
   if(r.final_score)area.append(node('strong',r.final_score[0]+' – '+r.final_score[1],'score'));
   area.append(node('p',r.final_score?'Final result saved. Relevant rankings, standings and match history have updated.':'This match is closed; no new evidence can be submitted.'),
    button('View standings / rankings',async()=>{resultCleanup?.();tab=r.kind==='fixture'?'table':'open';await load()}));return;
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
  const form=node('form'),detail=node('p',uploadError,'muted'),submit=node('button','Submit privately for review');submit.type='submit';submit.disabled=true;
  form.dataset.formInline='1';
  captureWidget=OrbitEvidenceCamera.mount({container:form,videoRequired:review.stage==='video',onCapture:blob=>{selected=blob;uploadError='';submit.disabled=false;detail.textContent='Camera capture ready for private submission.'}});
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
 resultCleanup=()=>{closed=true;clearInterval(timer);selected=null;captureWidget?.destroy();captureWidget=null;window.removeEventListener('pagehide',leaving);resultCleanup=null};
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
reviewOpen=async m=>{await originalOpenReview(m);$('view').append(privateVideoTools(m));};
const originalFixtureReview=review;
review=f=>{originalFixtureReview(f);$('view').append(privateVideoTools(f));};
