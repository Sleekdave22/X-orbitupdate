/** Display-only message formatting. Stored text and message/attachment IDs stay intact. */
(()=>{
 'use strict';
 const pictograph='\\p{Extended_Pictographic}(?:\\uFE0F|\\p{Emoji_Modifier})?(?:\\u200D\\p{Extended_Pictographic}(?:\\uFE0F|\\p{Emoji_Modifier})?)*(?:[\\u{E0020}-\\u{E007E}]+\\u{E007F})?';
 const emojis=new RegExp('^(?:\\p{Regional_Indicator}{2}|[0-9#*]\\uFE0F?\\u20E3|'+pictograph+')+$','u');

 /** Detect full emoji sequences without treating digits or mixed text as emojis.
  * @param {string} text Original message text. @returns {boolean} Emoji-only result.
  * Invalid/non-string values return false; no message content is modified.
  */
 function emojiOnly(text){return typeof text==='string'&&emojis.test(text.replace(/\s/gu,''))}

 /** Normalize only a recognized Vibe context line for either conversation side.
  * @param {string} text Original text. @returns {{label:string|null,body:string}}
  * No errors expected; legacy message bytes remain unchanged in storage.
  */
 function parts(text){const match=/^↪ Reply to(?: your)?(?: Private)? Vibe\n/.exec(text);return {label:match?'Reply to Vibe':null,body:match?text.slice(match[0].length):text}}

 /** Append safe readable text with an unchanged arrow and smaller italic label.
  * @param {HTMLElement} container Existing bubble, retaining its alignment/colours.
  * @param {string} text Original text. @returns {void} DOM errors propagate.
  * Context never embeds a private Vibe thumbnail or unrestricted source URL.
  */
 function append(container,text){
  const value=parts(text);
  if(value.label){const context=document.createElement('div'),arrow=document.createElement('span'),label=document.createElement('span');context.className='vibe-reply-context';arrow.textContent='↪ ';label.textContent=value.label;label.className='vibe-reply-label';context.append(arrow,label);container.append(context)}
  const body=document.createElement('div');body.textContent=value.body;if(emojiOnly(value.body))body.className='emoji-only-message';container.append(body);
 }
 window.OrbitMessageText={emojiOnly,parts,append};
})();
