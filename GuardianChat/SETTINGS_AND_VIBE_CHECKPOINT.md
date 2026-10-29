# Settings context and Vibe messaging corrections

## Scope completed in this checkpoint

- Browser settings and menus occupy exactly 50% of the viewport and render above
  module/bottom navigation. Existing menu actions/handlers are preserved.
- Play and Plaza settings stay on their original pages. The common account
  personalization picker remains shared, with the neutral X-Orbit appearance
  title. Plaza tools reuse search/location, shop, Demand and notification controls;
  no speculative product policy controls were invented.
- Native menu/settings widths are 50%; the existing module remains underneath.
- Vibe reactions now create persisted, source-linked private chat messages for
  accepted contacts and use existing message push. Unfamiliar senders go through
  existing recipient acceptance before a normal chat message is materialized.
- Same-reaction retries/concurrent requests do not create duplicate messages.
  Block, expiry and private audience rules remain authoritative. Private media and
  captions never appear in reaction notification/context payloads.
- Vibe reply text reads “Reply to Vibe” on either side, smaller/italic with the
  existing arrow retained. Old stored messages are normalized only for display.
- Emoji-only message bodies use 150% normal text size in browser and native chat.
- The native Private Vibe reaction success toast was removed; the rest of the new
  nonintrusive-feedback requirement remains a later scoped change.

## Root causes

The browser module settings callback explicitly assigned `/?home=settings` and
therefore always recreated Chat. Chat's drawer was nested inside a fixed header
stacking context below the separately body-owned navigation. Increasing only its
child z-index could not put it in front of those tabs.

The Vibe reaction handler previously wrote only `vibe_reactions` and an account
activity notice. It never inserted a message, linked a message to the Vibe or
invoked message push. The new atomic delivery path does all three for accepted
contacts and persists held reactions for unfamiliar accounts until acceptance.

## Database/API changes

Additive `vibe_reaction_deliveries` table, with explicit backward-compatible
visibility migration preserving old rows/message IDs. Existing `/vibe/react`
returns a real delivery state/message ID; existing message JSON gains minimal Vibe
context metadata. Existing routes, contacts, messages and media records remain.

## Actual checks

- 99 targeted Python tests passed in 143.890 seconds: reaction delivery/migration,
  Vibe viewer/activity/privacy, social, message notifications and navigation counts.
- All 45 JavaScript regression scripts passed, including settings context,
  duplicate mounting, focus, text-only rendering, emoji detection and legacy labels.
- Android debug APK assembled and all 29 JVM tests passed after correcting the
  local test temporary-directory permissions. The first failed test attempt was
  five temporary-folder access failures, not application assertions. The existing
  debug signing key was preserved. No phone installation has occurred here.
- Real browser, isolated disposable account/data: Chat menu body ownership and
  hit-testing above tabs; Play/Plaza preserve their path and correct titles;
  640/1280 px drawer width; dark/light themes; 195/390 px phone-width drawer with no
  horizontal overflow. Shared browser viewport restored afterward.
- The prior broader Python regression retains its documented 13 obsolete ranking
  errors; this checkpoint does not hide or repair unrelated ranking contracts.

One existing social-notice background test thread logged a teardown database-write
error despite the 99 passing assertions. No physical Android↔browser reaction or
FCM delivery test was performed; local tests exercise persistence and existing
dispatch integration, not provider delivery to a real offline S21.

## Remaining authorized work

The subsequent local MESSAGING_DATES_AND_RETRY_CHECKPOINT.md covers private-chat
sticky dates and nonintrusive send/connection feedback. Shared message pins, extended
message request previews/report/block actions, groups, Plaza reactions, Show Off
media/classification/feeds/comments, four-section finger-tracked navigation and
related notification preferences remain tracked in ECOSYSTEM_IMPLEMENTATION_PLAN.
Existing personal chat pinning must be reused rather than rebuilt. Phone-contact
linking remains on hold. The current live browser/phone release is not replaced
by these local tests/builds, and the original X-Orbit repository remains untouched.
