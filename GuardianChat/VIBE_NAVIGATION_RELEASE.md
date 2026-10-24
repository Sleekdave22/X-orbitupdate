# Orbit Vibe, navigation and activity release

24 October 2026. Repository: `Sleekdave22/X-orbitupdate` (the user's selected main
project). Branch: `feature/vibe-navigation-and-notices`. Previous tested release:
`fbaf55a9c1b041ee5f4f0fa995fb26acddefd524`; navigation checkpoint: `1c78c7f`.

## Requested changes

- Four bottom destinations, in order: icon-only Vibe, Chat, Calls, Profile. The
  five supplied SVGs are copied unchanged into web and native assets. Android
  renders those SVG sources directly in small script-disabled WebViews and releases
  them when leaving the screen. Profile remains the existing account destination.
- Orbit Play and Orbit Market retain their upper locations and actions. Market
  uses its supplied icon and name. The original X-Orbit checkout is not changed.
- Evidence is a result conversation with one camera launcher. Tap the shutter for
  photo, hold for video, slide upward to lock. Video-only escalation uses the same
  control. Back cancels an unsent capture and stops tracks; submission appears only
  after capture. The old peer-photo/file-picker implementations are removed from
  participant result entry points. Existing moderator evidence viewing remains.
- Game identities, seasons and joined competitions indicate Registered and expose
  edit/availability actions instead of inviting duplicate registration. New game
  registration remains available for another supported game.
- OrbitPlay has a bell beside its profile button. Separate Play, Market and Vibe
  activity scopes, section counts and top-right badges use persistent seen receipts.
  Seeing/opening an activity or engaging its section clears unread status without
  accepting an invitation or deleting its underlying match. Open notification cards
  remain actionable in the current view after being seen. Newer arrivals are not
  accidentally marked by an older receipt.
- Private review requests and decisions have authenticated links to the exact result
  room. Android game push taps carry the verified notice identifier to that route.

## Vibe implementation

`vibes.py` adds `vibe_settings`, `vibe_items`, `vibe_audience`, `vibe_views` and
`vibe_reactions`. Public and Private expiry defaults are independently 12/24/48 hours;
each upload stores its own absolute expiry. Settings changes affect future uploads.
Multiple selected files publish independently, with retry keys preventing duplicates.
Captions, PNG/JPEG (5 MiB) and MP4/WebM (20 MiB, bounded decoding) are validated.

Private audiences are explicit existing contacts, frozen on publication, with
current contact/block checks on every read/action. Author-only viewer records include
identities, unique count, first/last viewed time and repeat opens. Reactions are
account scoped. Chat/reply opens the existing authorized conversation; other public
accounts use the existing message request flow. Publishing grants no chat permission.

Expired media is denied immediately and its bytes purged by maintenance. Expired
metadata remains seven days for retry/history, then is removed with audience/views.
Server backups may retain older bytes under their separate backup retention policy.
No live user Vibe, test message or real payment was created during automated testing.

New routes: `/vibe/feed`, `/vibe/media`, `/vibe/status`, `/vibe/viewers`,
`/vibe/preferences`, `/vibe/publish`, `/vibe/view`, `/vibe/react`, `/vibe/remove`;
`/notifications` and `/notifications/seen`. Additive activity tables:
`account_activity`, `gb_activity_targets`. No existing table or account is renamed.

## Protection boundaries

Private content's normal browser UI directs users to the protected Android viewer.
Android enables FLAG_SECURE, initializes the existing GuardianLab shielding/detection
before display, stops on backgrounding, rechecks authorization, and clears temporary
video on exit/expiry/startup. The existing GuardianLab modules and protected chat
keys are unchanged. Device/extra-face detection is best effort and cannot identify
every external camera. Browser screenshot blocking is not guaranteed.

The protected-view API flag is a client capability declaration, not cryptographic
device attestation or DRM. Account/audience authorization is enforced independently.
No claim of leak-proof private content or production readiness is made. Physical
screen-recording prevention, detector behavior, capture gestures and actual background
push deep links need the two-account/manual phone acceptance pass. Market-to-Public
Vibe sharing remains a future integration; no misleading Share action is added.

## Verification evidence

- 60 backend tests passed for private reviews, Market, match core, scheduling and
  sponsored leagues, including a once-only result decision notification and its route.
- Six new Vibe/activity tests passed: independent expiry, private audience/block,
  viewers/reactions, immediate expiration and purge, immutable retries/bad media,
  account/category/snapshot-scoped seen receipts. A run importing the existing ChatTest
  also passed its 33 chat/server cases (39 total).
- All 29 browser scripts passed, including camera cancellation/hold/swipe behavior,
  private upload receipts, original chat/calls and exact SVG navigation structure.
- Android debug compilation, assembly and all existing 20 JVM tests passed during
  integration; the final packaging check is recorded with deployment evidence.
- Isolated HTTPS browser accounts verified Public Vibe media, existing Chat and Calls,
  own Profile/Settings, purple and light themes, camera-only dispute conversation and
  the bell/badge layout. The bottom bar remains visible on long Profile content.
- Remaining physical acceptance is explicitly pending; tests use synthetic media.

The main implementation is in `server/vibes.py`, `server/vibe.*`,
`server/account_notifications.py`, `server/activity-ui.js`, `server/orbit-navigation.js`,
`server/navigation.css`, `server/evidence-camera.js`, `server/private-results.js` and
`chat/src/main/java/com/guardianlab/chat/MainActivity.kt`. The release manifest records
61 web assets and their hashes. No default branch is merged.
