'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/invitations.js', 'utf8');

class Element {
 constructor(tag, text = '') { this.tagName = tag.toUpperCase(); this.textContent = text; this.children = []; this.dataset = {}; this.style = {}; this.attributes = {}; this.hidden = false; this.disabled = false; this.parentNode = null; this.value = ''; }
 get isConnected() { return this.attached || !!this.parentNode?.isConnected; }
 append(...nodes) { for (const child of nodes) { child.parentNode = this; this.children.push(child); } }
 remove() { if (this.parentNode) { const siblings = this.parentNode.children; siblings.splice(siblings.indexOf(this), 1); this.parentNode = null; } }
 setAttribute(key, value) { this.attributes[key] = String(value); }
 querySelectorAll(selector) { return this.children.flatMap(child => [...((selector === '[data-signup-invite]' ? child.dataset.signupInvite !== undefined : child.tagName === selector.toUpperCase()) ? [child] : []), ...child.querySelectorAll(selector)]); }
 querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
 focus() { this.focused = true; }
 select() { this.selected = true; }
}
function setup() {
 const host = new Element('div'); host.attached = true;
 const calls = [], copied = [], shared = [], confirmations = [];
 let response = {path: '/join?invite=opaque-token', joined: 0}, failure = null, pending = null, approved = true;
 const context = {URL, Promise, Error, Number, account: {id: 'self'}, location: {origin: 'https://orbit.test'}, document: {createElement: tag => new Element(tag)}, navigator: {clipboard: {writeText: async value => copied.push(value)}, share: async value => shared.push(value)}, confirm: text => { confirmations.push(text); return approved; }, api: async (path, body) => { calls.push([path, body]); if (pending) return pending; if (failure) throw failure; return response; }};
 vm.createContext(context); vm.runInContext(source, context);
 return {context, host, calls, copied, shared, confirmations, setResponse: value => response = value, setFailure: value => failure = value, setPending: value => pending = value, approve: value => approved = value};
}
const find = (section, text) => section.querySelectorAll('button').find(button => button.textContent === text);
const status = section => section.querySelectorAll('p').find(p => p.attributes.role === 'status');
async function basicControls() {
 const f = setup(), section = await f.context.mountSignupInvite(f.host), get = find(section, 'Get invite link');
 assert.equal(f.calls.length, 0, 'mounting a profile must not request an invite link');
 assert.equal(section.querySelector('input').parentNode.parentNode.hidden, true, 'the invite link starts collapsed');
 assert.equal(section.querySelector('input').value, '');
 assert.equal(await f.context.mountSignupInvite(f.host), section, 'repeated profile mounts reuse the same controls');
 assert.equal(f.host.querySelectorAll('[data-signup-invite]').length, 1);
 await get.onclick();
 assert.deepEqual(f.calls, [['/invitations/mine', undefined]]);
 const field = section.querySelector('input');
 assert.equal(field.readOnly, true);
 assert.equal(field.value, 'https://orbit.test/join?invite=opaque-token');
 assert.equal(get.hidden, true);
 assert.equal(field.parentNode.parentNode.hidden, false);
 await find(section, 'Copy link').onclick();
 assert.deepEqual(f.copied, [field.value]);
 assert.match(status(section).textContent, /copied/);
 await find(section, 'Share link').onclick();
 assert.equal(f.shared[0].url, field.value);
 assert.equal(f.shared[0].title, 'Join X ORBIT');
 f.approve(false); const before = f.calls.length;
 await find(section, 'Reset link').onclick();
 assert.equal(f.calls.length, before, 'canceling reset must not invalidate the current link');
 assert.match(f.confirmations[0], /Previous links will stop working/);
 assert.match(f.confirmations[0], /Existing accounts and chats will stay unchanged/);
 f.approve(true); f.setResponse({path: '/join?invite=replacement', joined: 2});
 await find(section, 'Reset link').onclick();
 assert.equal(f.calls.at(-1)[0], '/invitations/reset');
 assert.equal(Object.keys(f.calls.at(-1)[1]).length, 0);
 assert.equal(section.querySelector('input'), field, 'reset must preserve the existing field and controls');
 assert.equal(field.value, 'https://orbit.test/join?invite=replacement');
 assert.match(status(section).textContent, /Previous links no longer work/);
 assert.match(status(section).textContent, /2 people have joined/);
 f.setFailure(Error('Reset unavailable')); await find(section, 'Reset link').onclick();
 assert.equal(field.value, 'https://orbit.test/join?invite=replacement', 'a failed reset must not replace the visible link');
 assert.equal(find(section, 'Reset link').disabled, false); assert.match(status(section).textContent, /Reset unavailable/);
}
async function validationAndRecovery() {
 for (const path of ['https://evil.test/join?invite=bad', '/wallet.html?invite=bad', '/join?invite=', '/join?invite=+++', 'https://user:secret@orbit.test/join?invite=bad', '/join?invite=bad#other', '//evil.test/join?invite=bad', 'javascript:alert(1)']) {
  const f = setup(); f.setResponse({path}); const section = await f.context.mountSignupInvite(f.host); await find(section, 'Get invite link').onclick();
  assert.equal(section.querySelector('input').value, '', 'reject unsafe or invalid invite path: ' + path);
  assert.equal(section.querySelector('input').parentNode.parentNode.hidden, true);
  assert.match(status(section).textContent, /invalid invite link/);
  assert.ok(find(section, 'Retry'));
 }
 const f = setup(); f.setFailure(Error('Connection unavailable')); const section = await f.context.mountSignupInvite(f.host); await find(section, 'Get invite link').onclick();
 assert.match(status(section).textContent, /Connection unavailable/); const retry = find(section, 'Retry'); assert.equal(retry.disabled, false);
 f.setFailure(null); await retry.onclick(); assert.match(section.querySelector('input').value, /opaque-token/); assert.equal(retry.hidden, true);
 f.context.navigator.clipboard.writeText = async () => { throw Error('Clipboard permission denied'); }; await find(section, 'Copy link').onclick(); assert.match(status(section).textContent, /Clipboard permission denied/); assert.equal(find(section, 'Copy link').disabled, false);
 delete f.context.navigator.clipboard; await find(section, 'Copy link').onclick(); assert.equal(section.querySelector('input').selected, true); assert.match(status(section).textContent, /Select and copy/);
}
async function sharingAndNative() {
 const fallback = setup(); delete fallback.context.navigator.share; const section = await fallback.context.mountSignupInvite(fallback.host); await find(section, 'Get invite link').onclick(); await find(section, 'Share link').onclick(); assert.equal(fallback.copied.length, 1); assert.match(status(section).textContent, /Paste it/);
 for (const name of ['GuardianGaming', 'GuardianSocial']) {
  const f = setup(), native = [];
  f.context[name] = {copyInvite: value => native.push(['copy', value]), shareInvite: value => native.push(['share', value])};
  const panel = await f.context.mountSignupInvite(f.host); await find(panel, 'Get invite link').onclick(); await find(panel, 'Copy link').onclick(); await find(panel, 'Share link').onclick();
  assert.deepEqual(native, [['copy', 'https://orbit.test/join?invite=opaque-token'], ['share', 'https://orbit.test/join?invite=opaque-token']]); assert.equal(f.copied.length, 0); assert.equal(f.shared.length, 0);
 }
 const canceled = setup(); canceled.context.navigator.share = async () => { const error = Error('User canceled'); error.name = 'AbortError'; throw error; }; const panel = await canceled.context.mountSignupInvite(canceled.host); await find(panel, 'Get invite link').onclick(); const previous = status(panel).textContent; await find(panel, 'Share link').onclick(); assert.equal(status(panel).textContent, previous, 'canceling the share sheet is not a failure'); assert.equal(find(panel, 'Share link').disabled, false);
}
async function asyncGuards() {
 const f = setup(); let resolve; f.setPending(new Promise(done => resolve = done)); const section = await f.context.mountSignupInvite(f.host), get = find(section, 'Get invite link'); const first = get.onclick(); get.onclick(); assert.equal(f.calls.length, 1, 'double taps must not create duplicate requests'); assert.equal(get.disabled, true);
 assert.equal(await f.context.mountSignupInvite(f.host), section); f.host.attached = false; resolve({path: '/join?invite=late', joined: 0}); await first; assert.equal(section.querySelector('input').value, '', 'departed profiles must ignore late invite data'); assert.equal(section.querySelector('input').parentNode.parentNode.hidden, true); assert.equal(get.disabled, false, 'a detached profile can be opened again without leaving its controls stuck');
 f.host.attached = true; f.setPending(null); await get.onclick(); assert.match(section.querySelector('input').value, /opaque-token/, 'reopening a retained profile lets the user retry normally');
 const changed = setup(); let release; changed.setPending(new Promise(done => release = done)); const panel = await changed.context.mountSignupInvite(changed.host), pending = find(panel, 'Get invite link').onclick(); changed.context.account = {id: 'another-account'}; release({path: '/join?invite=private-old-account'}); await pending; assert.equal(panel.querySelector('input').value, '', 'account changes must not expose the previous account invite');
}
(async () => { await basicControls(); await validationAndRecovery(); await sharingAndNative(); await asyncGuards(); console.log('Sign-up invites: collapsed default, same-origin path validation, idempotent mounts, copy/share/native fallback, reset confirmation, retries and async account/navigation guards passed'); })().catch(error => { console.error(error); process.exitCode = 1; });
