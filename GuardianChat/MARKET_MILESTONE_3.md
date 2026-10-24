# Market milestone 3 — connections, offers and activity

Added `market_connections.py`, `market-chat.js`, `test_market_connections.py`;
extended existing Market routes/UI, native conversation reference/header and
static asset allowlists. Existing messaging data and handlers remain intact.

New tables: saves, offer records/history, single-listing reservations, immutable
operation retry receipts and listing inquiries. APIs: saved/save_item, offers/offer,
offer_create/offer_action, inquiry/chat_context, activity/activity_seen.

Buyers/sellers negotiate, counter, cancel, reject and accept with turn/revision checks.
Concurrent acceptance reserves a listing exactly once; accepting an offer never
transfers money or marks it paid/sold. Reservations and unanswered offers expire.
Legacy owner/admin removal cannot bypass a live reservation. Retry keys prevent
duplicate offers/events and reject changed payload reuse. Blocked interactions fail.

Chat Seller preserves existing contact authorization. Noncontacts create the existing
social message request; the seller accepts through that service before chat opens.
A listing reference (photo, title, price, reference, current availability) is added
inside the authorized conversation, linking back to details. It does not silently
send a personal message or modify chat encryption/media/calling behavior.

Market activity is persistent and separate from Play: offers, inquiries, publication,
owner state changes and saved-item updates route to their exact destination. History
includes read state/time and paging; Mark all uses an ID snapshot so newer events
are not cleared. The existing shared category service still provides home badges.
Removed/unavailable destinations display an explanatory state rather than failing
navigation. New Market background push is not yet physically verified.

22 backend tests passed (five connections + three search + six foundation + eight
original Market), including concurrent double acceptance, idempotency, negotiation
history, no gaming ledger entry, block/ownership rules, private message request
acceptance, save dedupe and account-scoped seen receipts. Browser seller-routing
regression passed. Native context rendering/packaging and full browser interaction
are included in final release checks; they are not claimed physically verified here.

Next: separately simulated Market accounting/orders and controlled administration.
