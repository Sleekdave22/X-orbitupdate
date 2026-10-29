# Chat management checkpoint — version 42

The user approved requiring acceptance for new connections on 29 October 2026
and authorized pushing and installing the tested update. Main and the original
X-Orbit repository remain protected. This checkpoint does not complete the full
ecosystem handoff: groups, Show Off, Plaza reactions and four-section gesture
navigation are still separate unfinished stages.

## Implemented behavior

- Shared individual-message pins in private conversations. Either participant can
  pin/unpin through the existing message menu. A compact preview below the peer
  header opens the original message; All pins opens the list. Existing personal
  chat-list pinning remains unchanged.
- Pin previews are generated from currently accessible messages on every poll,
  excluding personally hidden/deleted messages and blocked relationships. Protected
  and view-once content uses generic labels; no private bytes or caption are copied.
- New contact-code additions request acceptance. Existing contacts and established
  histories retain acceptance. Browser, Plaza and opponent-contact actions explain
  pending state instead of falsely opening a connected chat.
- Message request previews, Accept, Decline, Decline & Block and a separate Report
  workflow. Browser My Orbit reuses its existing request tab; Android My Orbit has
  a Message requests action. Optional text introductions can be composed from a
  browser public profile. Native search retains its existing request action.
- Introductions remain outside normal messages/inbox/receipts until acceptance.
  Acceptance materializes original text once. Declines are not disclosed to the
  sender, cannot be undone by retries and do not send a refusal notification.
- Reports enter the existing social_reports moderation queue, with retry keys.
  Reporting alone neither declines nor blocks. Blocked requests cannot bypass the
  rule through contact codes. Existing rate limits remain authoritative.

This version also contains the earlier tested settings, Vibe-to-chat delivery,
emoji/reply presentation, sticky-date and in-session retry corrections. Independent
Play/Plaza introduction-session draft work is preserved and tested; it does not
represent the still-unfinished four-section finger-tracked navigation.

## Modules and contracts

- `message_pins.py`: additive message_pins table; GET /messages/pins?peer=... and
  POST /messages/pin {message_id,pinned}. Ordinary /messages adds safe pins to its
  response, so both clients reuse existing synchronization.
- `message_requests.py`: additive message_request_previews and
  message_request_reports. Existing social_message_requests/contacts/messages and
  moderation tables retain their identifiers.
- POST /contacts retains its contact card and adds accepted/pending state. Clients
  must check that state before opening a newly requested conversation.
- POST /social/message_request accepts optional text/client_id. The recipient
  reads /social/message_requests and decides with existing message_accept/
  message_decline or new message_decline_block. message_report requires a reason
  and stable client_id. None of the preview endpoints acknowledges a read.
- `message-pins.js` and `message-requests.js` own text-only controls; social.js
  mounts the request controls in both its compact and paginated list renderers.
  MainActivity owns the equivalent native views. Asset allowlists are updated.

## Actual verification and limits

- Baseline: 46 server/social tests passed before this stage. Pin-only integration
  and existing message/privacy/navigation checks then passed 71 tests.
- New acceptance/pin/server/social run: 52 passed. Broader Vibe, notifications,
  navigation, source links, marketplace, competition/profile run: 101 passed.
- Full Python run: 418 tests, 404 passed and 14 errors. Thirteen are the documented
  obsolete test_rating.py contracts. The additional Market push fixture tried to
  use an intentionally revoked recipient session for new contact acceptance; its
  unrelated authorization probe now creates an unpaired account. The focused
  rerun result is recorded with the final checkpoint report. No assertion removed.
- 49 JavaScript scripts passed; a subsequent bootstrap regression also passed.
  The browser test caught an initializer using a lexical error callback too early;
  it now defers that callback and the dedicated bootstrap check covers it.
- Android debug build and all 31 JVM tests passed before the final version-number
  rebuild. Native interaction acceptance still requires a physical-device check.
- Actual browser on disposable data: 125 messages/five local dates, two shared
  pins, exact-message navigation/highlight, unchanged polling while reading,
  My Orbit request preview/all four actions and acceptance clearing the list.
  No real account, live database or user conversation was used for these tests.

The environment denied saving a browser screenshot; no saved proof image is
claimed. Device credentials/preferences were not accessed. Failed-send retries
are in-session, not a durable offline outbox. New request introductions are text
only; protected or pending media are not staged in ordinary storage. Expired Vibe
media is not embedded in reaction previews. Groups and Show Off are not yet built.

## Manual checks after deployment

1. Open an existing chat. Long-press a normal message → Pin message; open the
   preview and All pins, then unpin. Check the other participant sees the change.
2. Use two new disposable accounts: request a connection; inspect My Orbit →
   Message requests. Previewing must not add a normal unread/read message.
3. Accept and reopen chat; the introduction appears once. Separately test Decline,
   Decline & Block and Report. Existing accepted chats must still send normally.
4. Check scrolling dates, retry feedback, settings in Chat/Play/Plaza and dark/light
   layout on the S21. Do not mistake a successful build for these physical checks.
