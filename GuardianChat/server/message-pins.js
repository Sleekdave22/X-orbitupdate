/** Shared private-message pin UI. The server owns visibility and pin permissions. */
(()=>{
 'use strict';
 /** Mount once below a peer header, retaining the existing message DOM and gestures.
  * @param {Object} options Existing api/current/jump/error callbacks and bar element.
  * @returns {Object} render/reset/toggle/has methods for the conversation owner.
  * Network failures remain inline; DOM/invalid integration errors propagate.
  */
 function create({api,current,jump,error,bar}){
  let pins=[],signature='',dialog=null;const changing=new Set();
  /** Compare captured account/conversation, preventing late responses crossing chats.
   * @param {Object|null} context Captured identity, peer and conversation version.
   * @returns {boolean} Whether this exact conversation is still on screen.
   */
  function same(context){const now=current();return !!context&&!!now&&context.owner===now.owner&&context.peer===now.peer&&context.version===now.version}
  /** Build an ordinary accessible button without interpreting preview text as HTML.
   * @param {string} text Label. @param {Function} action Existing action callback.
   * @returns {HTMLButtonElement} Detached button; DOM errors propagate.
   */
  function button(text,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=action;return b}
  /** Close only our pin list. @returns {void} DOM errors propagate. */
  function close(){if(dialog){dialog.close();dialog.remove();dialog=null}}
  /** Reveal an already loaded message, never fetching protected content.
   * @param {Object} pin Safe server preview. @param {Object} context Captured chat.
   * @returns {void} Stale navigation is ignored; jump failure is explained inline.
   */
  function visit(pin,context){if(!same(context))return;close();jump(pin.id)}
  /** Open the dedicated list of all authorized pinned messages.
   * @returns {void} No API side effects; native dialog errors propagate.
   */
  function open(){
   close();const context=current();if(!context||!pins.length)return;
   const d=document.createElement('dialog');dialog=d;d.className='pinned-message-list';d.setAttribute('aria-label','Pinned messages');
   const title=document.createElement('h2');title.textContent='Pinned messages';d.append(title,button('Close',close));
   for(const pin of pins){const row=document.createElement('div');row.className='pinned-message-row';row.append(button(pin.name+' · '+pin.preview,()=>visit(pin,context)),button('Unpin',()=>toggle({id:pin.id})));d.append(row)}
   d.addEventListener('close',()=>{d.remove();if(dialog===d)dialog=null},{once:true});document.body.append(d);d.showModal();
  }
  /** Clear transient pin state on conversation changes.
   * @returns {void} Does not unpin anything on the backend; DOM errors propagate.
   */
  function reset(){close();pins=[];signature='';bar.replaceChildren();bar.hidden=true}
  /** Render safe previews returned with ordinary message polling.
   * @param {Array<Object>} values Authorized server pin previews.
   * @param {Object} context Captured owner/peer/version.
   * @returns {void} Stale responses ignored; unchanged polls retain focus/layout.
   */
  function render(values,context){
   if(!same(context))return;const next=JSON.stringify(values||[]);if(next===signature)return;
   signature=next;pins=values||[];close();bar.replaceChildren();bar.hidden=!pins.length;if(!pins.length)return;
   bar.append(button('Pinned · '+pins[0].preview,()=>visit(pins[0],context)),button('All pins ('+pins.length+')',open));
  }
  /** Set the opposite of the current shared state; success requires backend commit.
   * @param {Object} message Existing message with numeric id.
   * @returns {Promise<void>} Failures use inline error; stale responses are ignored.
   */
  async function toggle(message){
   const context=current(),id=Number(message.id);if(!context||changing.has(id))return;changing.add(id);
   try{const data=await api('/messages/pin',{message_id:id,pinned:!has(id)});if(same(context)){render(data.pins,context);error('')}}catch(failure){if(same(context))error(failure.message)}finally{changing.delete(id)}
  }
  /** @param {number} id Message ID. @returns {boolean} Current authorized pin state; no errors. */
  function has(id){return pins.some(pin=>pin.id===Number(id))}
  reset();return {render,reset,toggle,has};
 }
 window.OrbitMessagePins={create};
})();
