/** Recipient-owned message requests. Pending previews never mark messages read. */
(()=>{
 'use strict';
 /** Build a text-only button using established styling.
  * @param {string} label Button text. @param {Function} action Click callback.
  * @returns {HTMLButtonElement} Detached button. DOM errors propagate.
  */
 function button(label,action){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=action;return b}
 /** Show the optional introduction before requesting a new conversation.
  * @param {string} target Public account ID.
  * @param {Object} services Existing api/current/onResult callbacks.
  * @returns {HTMLDialogElement} Composer; errors stay inline, no chat opens pending.
  */
 function compose(target,{api,current,onResult}){
  const owner=current(),d=document.createElement('dialog'),heading=document.createElement('h2'),input=document.createElement('textarea'),status=document.createElement('p');
  heading.textContent='Request to message';input.placeholder='Introduction (optional)';input.maxLength=4000;input.setAttribute('aria-label','Introduction');status.setAttribute('role','status');
  let client='',original=null;
  const send=button('Send request',async()=>{
   if(current()!==owner||send.disabled)return;send.disabled=true;
   const text=input.value.trim();if(text!==original){original=text;client=crypto.randomUUID()}
   try{const result=await api('/social/message_request',{target,text,client_id:client});if(current()===owner){status.textContent=result.state==='accepted'?'Connected':'Request sent · awaiting acceptance';onResult?.(result);input.disabled=true;send.hidden=true}}catch(error){if(current()===owner)status.textContent=error.message}finally{send.disabled=false}
  });
  d.append(heading,input,status,button('Close',()=>d.close()),send);d.addEventListener('close',()=>d.remove(),{once:true});document.body.append(d);d.showModal();input.focus();return d;
 }
 /** Mount preview and four existing-architecture request actions on a profile row.
  * @param {HTMLElement} row Existing sender row. @param {Object} user Safe request card.
  * @param {Object} services Existing api/current/refresh/error callbacks.
  * @returns {void} Errors remain inline. Report never silently blocks or declines.
  */
 function mount(row,user,{api,current,refresh,error}){
  const owner=current(),preview=document.createElement('div'),actions=document.createElement('div');preview.className='message-request-preview';actions.className='message-request-actions';
  for(const value of user.previews||[]){const p=document.createElement('p');p.textContent=value.text;preview.append(p)}
  if(!preview.childElementCount)preview.textContent='Wants to start a conversation';row.append(preview,actions);
  /** Commit a request decision; only the matching account refreshes the list.
   * @param {string} action Existing social endpoint suffix.
   * @returns {Promise<void>} Failures are displayed; repeated clicks ignored.
   */
  async function decide(action){
   if(current()!==owner||actions._busy)return;actions._busy=true;
   try{await api('/social/'+action,{target:user.id});if(current()===owner)await refresh()}catch(failure){if(current()===owner)error(failure.message)}finally{actions._busy=false}
  }
  for(const [label,action] of [['Accept','message_accept'],['Decline','message_decline'],['Decline & Block','message_decline_block']])actions.append(button(label,()=>decide(action)));
  actions.append(button('Report',()=>{
   if(current()!==owner)return;const field=document.createElement('textarea'),status=document.createElement('p'),client=crypto.randomUUID();field.placeholder='Explain the report';field.maxLength=1000;field.setAttribute('aria-label','Report reason');status.setAttribute('role','status');
   const submit=button('Submit report',async()=>{
    if(current()!==owner||submit.disabled)return;submit.disabled=true;
    try{await api('/social/message_report',{target:user.id,reason:field.value,client_id:client});if(current()===owner){status.textContent='Report submitted for review';field.disabled=true;submit.hidden=true}}catch(failure){if(current()===owner)status.textContent=failure.message}finally{submit.disabled=false}
   });row.append(field,status,submit);
  }));
 }
 window.OrbitMessageRequests={compose,mount};
})();
