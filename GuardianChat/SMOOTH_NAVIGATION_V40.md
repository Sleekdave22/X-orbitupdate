# Smooth browser navigation and Vibe controls — version 40

The remaining navigation defects had three causes: transforms on a page container also moved its fixed navigation; Vibe had an additional independent entrance animation; and decorative button sweeps were visible outside navigation buttons after badge overflow was enabled. Native image dragging also interfered with gestures starting on tab artwork.

Changes:
- Shared browser transitions for Vibe / Chat / Calls / My Orbit and Play / Chat / Plaza. Fixed navigation keeps its own snapshot/position. Removed the overlapping whole-main animations and stale navigation lock on browser history restoration.
- Navigation sweeps and press scaling removed only from the two navigation strips. Artwork native dragging/text selection disabled. Gesture handling preserves existing destinations, keyboard actions and reduced-motion fallback.
- Removed the unwanted Vibe overlay from account avatars in browser and Android. Vibe previews, segmented rings, upload counts and unread counters remain.
- Caption moved to the bottom left, immediately above the reply line, in public and protected private viewing.
- Previous/next taps at list boundaries restart the current post and its display timer without a new media download. Automatic end-of-list behavior is retained.
- Native video-start overlays suppressed in the public viewer; video is revealed on playback rather than showing an initial play symbol.
- Existing public cache, privacy authorization, reply/reaction handling and GuardianLab shielding remain intact.

Validation:
- 40 JavaScript regression scripts passed.
- Android debug build passed; 24 JVM tests passed, including private replay timer reset.
- Browser isolated accounts: Vibe ↔ Chat gesture entry/return, Calls selection, Play → Plaza → browser Back → Chat, zero avatar overlays, no console warnings/errors during checked transitions, and removal of the diagonal sweep artifact visually checked.
- Browser application reports its native transition mode active. Supported APIs follow [WebKit](https://webkit.org/blog/16301/webkit-features-in-safari-18-2/) and [Chrome documentation](https://developer.chrome.com/docs/web-platform/view-transitions/cross-document).
- No live messages or posts were created. Physical S21 visual verification and installation are deferred at the user's request.
- Existing 87 related backend test results from version 39 remain recorded; this stage changes no authoritative scoring, wallet or marketplace APIs.

New master development handoff was read in full. Continue on the user-selected Sleekdave22/X-orbitupdate repository; preserve Sleekdave22/X-Orbit. Demand / Hot Demand is a verified missing feature in the active checkout and is the next implementation stage. Broader integration, scalability and hosting review remain underway, not complete.

Verified interface hashes: 72; bundled assets: 55; JVM tests: 24.
