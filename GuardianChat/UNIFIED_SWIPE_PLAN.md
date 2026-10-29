# Unified module navigation — implementation plan

Baseline: 04a554c, active X-orbitupdate feature/vibe-timed-navigation. This is the user's approved navigation feature, separate from behavior-preserving readability work.

## Existing behavior and conflict inventory

- Native Chat's ScrollView owns a rightward gesture beginning within its first 28 dp. It reveals a text placeholder and commits at 50% of screen width.
- Native Play's WebView owns a leftward gesture from its last 28 dp, also with placeholder/50% behavior. It is present throughout Play content.
- Browser/native three-module strips have their own indicator-only distance/velocity handlers.
- Chat-row delete/pin gestures, message reply/delete gestures, Vibe swipes, galleries, crop/trim tools and Android system back have independent ownership.
- Native root() currently tears down WebViews and other surface state. Preparing a destination through the normal entry function would trigger unwanted side effects before commitment.
- Play's browser welcome uses tab storage; native welcome state is Activity-scoped rather than process-scoped. Plaza has no matching intro.

The user asked to inspect older gestures before any removal. Replacement versus coexistence is awaiting the user's choice; do not remove either older content gesture while that choice is pending.

## Focused sequence

1. Establish browser and JVM baseline checks.
2. Add independent process/session intro tracking and a Plaza intro matching Play's established component. Keep existing bridge methods compatible. Document every added/changed function's parameters, return value, side effects and errors (JSDoc/KDoc/docstrings).
3. Add a pure release-threshold model: 35% of viewport width at release; a retreat below threshold cancels. No velocity-only shortcut, premature route or intro mark.
4. Add owned swipe-start regions outside Chat's list with only minimal symmetrical margins. Keep existing row/message/gallery/editor controls untouched.
5. Prepare/retain real destination surfaces without activating entry actions. Drag destination content proportionally; settle/restore on completion, cancel, interruption and resize. Activate/mark an intro only after committed entry.
6. Add reverse module gestures only in safe owned areas. Resolve the older-handler choice explicitly before consolidation.
7. Test threshold/retreat/cancellation, intro lifetimes, touch ownership, route integrity, themes and browser/native widths. Run build/regressions; record physical-device checks separately.
8. Commit focused stages, update developer guide/asset lists and deploy only a concrete tested build.

No backend business policy, database schema, account, money, GuardianLab, icon or existing bottom-tab arrangement change.
