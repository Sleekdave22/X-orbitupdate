/** Local-calendar conversation dividers. No timestamps or stored messages change. */
(()=>{
 'use strict';
 /** Obtain a stable key in the reader's local timezone, not UTC.
  * @param {number} milliseconds Message Unix milliseconds.
  * @returns {string|null} Local date key, or null for an invalid timestamp.
  */
 function key(milliseconds){const date=new Date(milliseconds);return Number.isFinite(milliseconds)&&milliseconds>0&&!Number.isNaN(date.getTime())?[date.getFullYear(),date.getMonth()+1,date.getDate()].join('-'):null}

 /** Label a local calendar day without assuming every day is 24 hours long.
  * @param {number} milliseconds Message Unix milliseconds.
  * @param {number} now Current Unix milliseconds, injectable in tests.
  * @returns {string} Today, Yesterday or a locale date; empty for invalid input.
  */
 function label(milliseconds,now=Date.now()){
  const day=key(milliseconds);if(!day)return '';
  if(day===key(now))return 'Today';const yesterday=new Date(now);yesterday.setDate(yesterday.getDate()-1);
  if(day===key(yesterday.getTime()))return 'Yesterday';
  return new Date(milliseconds).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'});
 }

 /** Reconcile date markers after a message batch, retaining the reading anchor.
  * @param {HTMLElement} container Existing scrolling messages list.
  * @param {number} now Injectable clock for Today/Yesterday rollover.
  * @returns {void} DOM errors propagate; markers never acquire message actions.
  * Flat rows stay flat so search, reply gestures, media and call ordering survive.
  */
 function sync(container,now=Date.now()){
  const rows=[...container.children].filter(row=>row.matches('.message,.call-event')&&key(Number(row.dataset.time)));
  const signature=key(now)+'|'+rows.map(row=>(row.dataset.messageId||row.dataset.time)+':'+row.dataset.time).join('|');
  if(container._orbitDateSignature===signature)return;container._orbitDateSignature=signature;
  const top=container.getBoundingClientRect().top;
  const anchor=rows.find(row=>row.getBoundingClientRect().bottom>top);
  const offset=anchor?anchor.getBoundingClientRect().top-top:0;
  const atBottom=container.scrollHeight-container.clientHeight-container.scrollTop<36;
  container.querySelectorAll('.chat-date-divider').forEach(marker=>marker.remove());
  let previous=null;
  for(const row of rows){const time=Number(row.dataset.time),day=key(time);if(day===previous)continue;previous=day;const marker=document.createElement('div');marker.className='chat-date-divider';marker.dataset.date=day;marker.textContent=label(time,now);marker.setAttribute('role','separator');marker.setAttribute('aria-label',marker.textContent);container.insertBefore(marker,row)}
  if(anchor?.isConnected&&!atBottom)container.scrollTop+=anchor.getBoundingClientRect().top-top-offset;
 }
 window.OrbitChatDates={key,label,sync};
})();
