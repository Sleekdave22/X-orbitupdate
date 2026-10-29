/** Session introduction contracts; no browser credentials or external requests. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/module-intro.js', 'utf8');

/**
 * Build an isolated entry-page context with optional shared session storage.
 * @param {Map<string,string>} storage Existing tab state, or a fresh Map.
 * @param {object|null} native Optional process-state bridge.
 * @returns {object} Intro controller, rendered panels, timers and shared storage.
 * @throws {Error} Script installation fails, which must fail the test.
 */
function setup(storage = new Map(), native = null) {
    const panels = {
        welcome: {hidden: true}, continue: {},
        plazaWelcome: {hidden: true}, plazaContinue: {}
    };
    const timers = [];
    const context = {
        window: {}, account: {id: 'fixture'}, Set, TypeError,
        document: {getElementById: id => panels[id]},
        sessionStorage: {
            getItem: key => storage.get(key) || null,
            setItem: (key, value) => storage.set(key, value)
        },
        setTimeout: fn => (timers.push(fn), timers.length),
        clearTimeout() {}
    };
    if (native) context.GuardianGaming = native;
    vm.createContext(context);
    vm.runInContext(source, context);
    return {intro: context.window.OrbitModuleIntro, panels, storage, context, timers};
}

const first = setup();
first.intro.show('play');
assert.equal(first.panels.welcome.hidden, false);
assert.equal(first.intro.hasSeen('play'), true);
assert.equal(first.intro.hasSeen('plaza'), false);
first.panels.continue.onclick();
assert.equal(first.panels.welcome.hidden, true);
first.intro.show('play');
assert.equal(first.panels.welcome.hidden, true);
first.intro.show('plaza');
assert.equal(first.panels.plazaWelcome.hidden, false);
assert.equal(first.intro.hasSeen('plaza'), true);
const reload = setup(first.storage);
reload.intro.show('plaza');
assert.equal(reload.panels.plazaWelcome.hidden, true);
assert.equal(setup().intro.hasSeen('play'), false);

const preview = setup();
preview.intro.setActive(false);
preview.intro.show('play');
assert.equal(preview.panels.welcome.hidden, true);
assert.equal(preview.intro.hasSeen('play'), false, 'A canceled preview cannot consume entry');
assert.equal(preview.storage.size, 0);
preview.intro.setActive(true);
assert.equal(preview.panels.welcome.hidden, false);
assert.equal(preview.intro.hasSeen('play'), true);
assert.throws(() => preview.intro.show('wallet'), /Choose Play or Plaza/);
assert.throws(() => preview.intro.setActive('yes'), /boolean/);

const processFlags = new Set();
const native = setup(new Map(), {
    moduleIntroSeen: section => processFlags.has(section),
    markModuleIntro: section => processFlags.add(section)
});
native.intro.show('play');
assert.deepEqual([...processFlags], ['play']);
const recreatedActivity = setup(new Map(), {
    moduleIntroSeen: section => processFlags.has(section),
    markModuleIntro: section => processFlags.add(section)
});
recreatedActivity.intro.show('play');
assert.equal(recreatedActivity.panels.welcome.hidden, true);
assert.equal(recreatedActivity.intro.hasSeen('plaza'), false);

const restricted = setup();
restricted.context.sessionStorage.getItem = () => {throw Error('Storage unavailable')};
restricted.context.sessionStorage.setItem = () => {throw Error('Storage unavailable')};
restricted.intro.show('play');
restricted.intro.dismiss();
restricted.intro.show('play');
assert.equal(restricted.panels.welcome.hidden, true);

const signedOut = setup();
signedOut.context.account = null;
signedOut.intro.show('plaza');
assert.equal(signedOut.intro.hasSeen('plaza'), false);
console.log('Independent process/tab intros, cancellation, reload, signed-out and storage-failure contracts passed.');
