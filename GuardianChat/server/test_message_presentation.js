'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Element,walk,content}=require('./browser-test-dom.cjs');
const context={window:{},document:{createElement:tag=>new Element(tag)}};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/message-presentation.js','utf8'),context);
const format=context.window.OrbitMessageText;
for(const text of ['❤️','😂😂','🔥🔥🔥',' 😍 🙌 🎉 ','👍🏾','👨‍👩‍👧‍👦','🇳🇬','1️⃣'])assert.equal(format.emojiOnly(text),true,text);
for(const text of ['','   ','Hi 😂','123','#','plain text','\u200D','🏽','✓','1️⃣hello'])assert.equal(format.emojiOnly(text),false,text);
for(const heading of ['↪ Reply to Vibe\n','↪ Reply to your Vibe\n','↪ Reply to your Private Vibe\n']){const root=new Element(),raw=heading+'🔥';format.append(root,raw);assert.match(content(root),/Reply to Vibe/);assert(!content(root).includes('your'));assert(walk(root).some(n=>n.textContent==='↪ '));assert(walk(root).some(n=>n.className==='emoji-only-message'))}
const mixed=new Element();format.append(mixed,'Hello 🔥');assert(!walk(mixed).some(n=>n.className==='emoji-only-message'));
console.log('Emoji sequences, mixed text, legacy Vibe label normalization and unchanged reply arrow passed.');
