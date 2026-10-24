/* Presentation checks; run from GuardianChat with Node. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync('server/index.html', 'utf8');
for (const [, code] of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
  if (code.trim()) new vm.Script(code);
}

class Element {
  constructor() { this.style = {}; this.children = []; this.attributes = {}; }
  setAttribute(name, value) { this.attributes[name] = value; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
}
const document = {createElement: () => new Element(), createTextNode: text => text};
let output;
const context = {Date, document, el: () => ({replaceChildren: (...nodes) => output = nodes})};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function renderProfilePresence'), html.indexOf('async function showProfile')), context);
const social = fs.readFileSync('server/social.js', 'utf8');
vm.runInContext(social.slice(social.indexOf('function compactProfileHeader'), social.indexOf('async function mountSocial')), context);
const now = Date.now() / 1000;
for (const [p, color] of [
  [{online: true, last_seen: now}, '#27b45f'],
  [{online: false, last_seen: now - 60}, '#e1b739'],
  [{online: false, last_seen: now - 8 * 86400}, '#e34450'],
  [{online: false, last_seen: now - 7 * 86400}, '#e34450'],
  [{online: false, last_seen: 0}, '#e1b739']
]) {
  context.p = p;
  vm.runInContext('renderProfilePresence(p)', context);
  assert.equal(output[0].style.background, color);
  assert.match(output[1], /Last seen/);
  const header = vm.runInContext('compactProfileHeader({...p, name:"Layout Test",nickname:"layout_test",id:"test-account"})', context);
  assert.equal(header.children[0].children[1].children[0].style.background, color);
  assert.equal(header.children[1].children[1].textContent, '@layout_test');
  assert.equal(header.children[1].children[2].textContent, 'Invitation code: test-account');
}
const unknown = vm.runInContext('compactProfileHeader({name:"Unknown presence"})', context);
assert.deepEqual(unknown.children[0].children[1].children, ['Last seen unavailable']);
vm.runInNewContext(fs.readFileSync('server/orbit-theme.js', 'utf8') + `
for (const legacy of ['#921b37','#b72b51','#e64570','#651426']) {
  if (OrbitTheme.color(legacy) !== legacy) throw Error('A custom published colour must be preserved');
}
if (OrbitTheme.tokens.lightAction !== '#0E7490') throw Error('Wrong light action shade');
`);
console.log('Presence boundaries, compact identity, unknown presence, theme migration and browser script syntax passed');
