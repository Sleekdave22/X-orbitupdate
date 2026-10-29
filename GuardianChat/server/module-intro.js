/**
 * Session-scoped introductions for the existing Play and Plaza entry screens.
 * Preview surfaces may request an intro, but only activation can display/mark it.
 * Native state belongs to the app process; browser state belongs to the tab session.
 * @returns {void} Installs window.OrbitModuleIntro; no credentials are stored.
 * @throws {Error} No errors are deliberately thrown during module installation.
 */
(function installModuleIntro() {
    'use strict';

    const sessionKey = 'orbit-module-intros-v1';
    const seenInMemory = new Set();
    let active = true;
    let requested = null;
    let dismissTimer = null;

    /**
     * Reject unsupported section names before accessing native or browser state.
     * @param {string} section Module identifier: play or plaza.
     * @returns {void} Returns normally for a supported section.
     * @throws {TypeError} The section is not a supported introductory destination.
     */
    function validate(section) {
        if (section !== 'play' && section !== 'plaza') {
            throw new TypeError('Choose Play or Plaza for a module introduction');
        }
    }

    /**
     * Read a section's viewed flag without consuming it.
     * @param {'play'|'plaza'} section Section whose session flag is queried.
     * @returns {boolean} Whether this process/tab session has displayed the intro.
     * @throws {TypeError} The section is unsupported. Storage failures use memory.
     */
    function hasSeen(section) {
        validate(section);
        if (typeof GuardianGaming !== 'undefined' && typeof GuardianGaming.moduleIntroSeen === 'function') {
            return GuardianGaming.moduleIntroSeen(section);
        }
        if (seenInMemory.has(section)) return true;
        try {
            const flags = JSON.parse(sessionStorage.getItem(sessionKey) || '[]');
            // Preserve the existing tab's Play flag during a browser update.
            return Array.isArray(flags) && flags.includes(section)
                || section === 'play' && sessionStorage.getItem('clutch-welcomed') === '1';
        } catch (_) {
            return false;
        }
    }

    /**
     * Record an introduction only as it becomes visible on a committed surface.
     * @param {'play'|'plaza'} section Section actually entering the foreground.
     * @returns {void} Updates process/tab state; never permanent preferences.
     * @throws {TypeError} The section is unsupported. Storage failures are contained.
     */
    function markSeen(section) {
        validate(section);
        if (typeof GuardianGaming !== 'undefined' && typeof GuardianGaming.markModuleIntro === 'function') {
            GuardianGaming.markModuleIntro(section);
            return;
        }
        seenInMemory.add(section);
        try {
            const saved = JSON.parse(sessionStorage.getItem(sessionKey) || '[]');
            const flags = new Set(Array.isArray(saved) ? saved : []);
            flags.add(section);
            sessionStorage.setItem(sessionKey, JSON.stringify([...flags]));
            if (section === 'play') sessionStorage.setItem('clutch-welcomed', '1');
        } catch (_) {
            // Restricted tab storage must not block navigation.
        }
    }

    /**
     * Hide the current introduction without changing destination or session state.
     * @returns {void} The existing page beneath the introduction remains active.
     * @throws {Error} No errors are deliberately thrown.
     */
    function dismiss() {
        clearTimeout(dismissTimer);
        const panel = document.getElementById(requested === 'plaza' ? 'plazaWelcome' : 'welcome');
        if (panel) panel.hidden = true;
    }

    /**
     * Display the requested intro only after committed entry and authentication.
     * @returns {void} Does nothing for previews, absent panels or signed-out users.
     * @throws {TypeError} Propagates an invalid requested section (internal misuse).
     */
    function display() {
        if (!active || !requested) return;
        const panel = document.getElementById(requested === 'plaza' ? 'plazaWelcome' : 'welcome');
        if (!panel) return;
        if (typeof account === 'undefined' || !account || hasSeen(requested)) {
            panel.hidden = true;
            return;
        }
        panel.hidden = false;
        markSeen(requested);
        const continueButton = document.getElementById(requested === 'plaza' ? 'plazaContinue' : 'continue');
        if (continueButton) continueButton.onclick = dismiss;
        clearTimeout(dismissTimer);
        dismissTimer = setTimeout(dismiss, 5000);
    }

    /**
     * Request the matching branded intro using the established five-second timing.
     * @param {'play'|'plaza'} section Section whose existing entry panel should open.
     * @returns {void} Displays immediately only on an active, authenticated surface.
     * @throws {TypeError} The section is unsupported.
     */
    function show(section) {
        validate(section);
        requested = section;
        display();
    }

    /**
     * Gate entry side effects while a destination is merely following a drag.
     * @param {boolean} value Whether navigation has committed to this surface.
     * @returns {void} Activation displays a pending intro; suspension consumes none.
     * @throws {TypeError} value is not a boolean.
     */
    function setActive(value) {
        if (typeof value !== 'boolean') throw new TypeError('Module activation must be a boolean');
        active = value;
        if (active) display();
        else dismiss();
    }

    window.OrbitModuleIntro = {show, hasSeen, setActive, dismiss};
}());
