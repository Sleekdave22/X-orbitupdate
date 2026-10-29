# Messaging dates and delivery feedback — local checkpoint

This was originally verified locally after the settings/Vibe correction checkpoint.
The user subsequently authorized pushing and installing the tested work on
29 October. These changes are included in the version 42 chat-management package;
build checks and deployment/device acceptance are reported separately.

## Changes

- Browser and native private chats group ordinary messages and call events by
  local calendar date. Today/Yesterday use calendar arithmetic, including daylight
  saving transitions. Browser date dividers stick inside the conversation;
  Android also keeps the visible date beneath the peer header.
- Date reconciliation preserves flat message rows, existing message IDs, gestures,
  media handlers and notification destinations. Unchanged polls avoid rebuilding
  dividers. Reading history stays anchored; entry and sending still reveal latest.
- Native Chat uses an inline connection/status line instead of routine bottom
  toasts. Delivery receipts still indicate success; unrelated screens retain their
  existing feedback. GuardianLab protection status is not overwritten by a
  transport failure.
- Failed ordinary sends retain an identifiable pending message with Retry and
  Remove unsent preview. Retry reuses the original recipient, caption, reply,
  view-once setting and backend client ID. Repeated taps cannot duplicate an
  in-flight attempt. Success does not erase a newer draft/reply selection.
- Native attachment retry rechecks source bytes and preserves the existing
  acknowledgement-dependent sent-attachment cache. Source captures are removed
  only after success or an explicit preview discard. Protected/view-once media
  are not copied into an ordinary persistent outbox.

## Verification

- Android debug build succeeded; 31 JVM tests passed, zero failures/errors/skips.
  Includes local year rollover/DST and the earlier text-presentation/cache tests.
- 47 browser regression scripts passed when run from their supported directories.
  An initial full run invoked `test_profile_presentation.js` from `server/`, but
  that script expects the app root; it failed to locate `server/index.html`.
  Rerunning that script from the app root passed. No assertion was bypassed.
- New browser retry checks execute the actual send handler: failure visibility,
  identical retry body/client ID/attachment bytes, duplicate taps, account/chat
  changes, preserving new drafts/replies, success and preview discard.
- Date checks cover local dates, DST, mixed call rows, unchanged polling and
  reading-anchor preservation. These are focused synthetic DOM/JVM checks.

The browser-control connection was unavailable for a fresh visual check in this
pass. The earlier real-browser settings checks remain documented separately.
No physical S21 test, keyboard/scroll gesture check or real provider notification
test was performed for these new dates/retry changes. The prior 13 obsolete
ranking-test errors remain recorded; this UI checkpoint did not alter ranking.

## Limits and next work

Failed-send previews/retries are in-session, not a durable offline outbox. Leaving
the conversation or restarting does not restore them; original draft/source may
need to be attached again. A transport error can mean that the server committed
but its response was lost: the original retry key handles this safely. Removing
an unsent preview is not a server-side recall or cancellation.

Shared message pinning, expanded message requests and group conversations remain
separate unfinished stages. Group date support must reuse the local calendar
helpers when groups are implemented. Plaza/Show Off engagement and ecosystem
navigation/media work remain tracked in ECOSYSTEM_IMPLEMENTATION_PLAN.md.
