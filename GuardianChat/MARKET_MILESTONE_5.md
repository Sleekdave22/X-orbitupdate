# Market milestone 5 — administration, trust and notification delivery

25 October 2026. Extends the separate demo-commerce checkpoint `437a75e`.

Added `server/market_admin.py`, `test_market_admin.py`, `test_market_push.py` and
`test_market_pilot_ui.js`. Modified the existing Market modules/UI, Studio hub,
shared static allowlist, native push handling/settings and version/asset manifest.
No original X-Orbit checkout or default branch is changed.

## Administration and migration

The existing Admin Studio gains a Market destination; the Market page also exposes
the same role-gated controls. Panels edit stable categories/subcategories/attributes,
limits, review requirements, moderation terms, notification settings, seller
restrictions/restoration, featured listings and search synonyms. Reports, system-
generated demo metrics/receipts, dispute decisions and audit history are inspectable.
Balances are never editable. Decisions require a reason and use controlled order
transitions. Existing legacy moderation remains available and now records an audit.

Additive `market_configuration`, `market_admin_audit`, `market_push_delivery` tables;
additive `delivery_regions` metadata column. Existing IDs, legacy text prices,
messages, wallet rows and user records remain unchanged. Listing publication and
legacy posting respect configured review/rate limits; reactivation renews an expired
listing. Shipping country codes are explicit and independent of discovery scope.

## Notifications and controls

Market history includes read/unread state, exact offer/order/inquiry/listing targets,
Mark all as read and snapshot-safe receipts. New `/market/activity_item` is account-
and category-scoped. Data-only FCM delivery uses active authenticated sessions,
retry/outbox receipts and expiry; payloads contain only an identifier and recipient.
Android fetches/authorizes the notice before displaying its text and uses a separate
Market channel/account-bound tap identity. Market alerts can be muted separately;
existing chat/call/Play notification contracts remain intact. Physical background
Market delivery still needs acceptance on the updated device; mock-gateway tests
do not establish physical delivery or force-stopped Android behavior.

Both upper Play/Market entries use identical purple geometry/type size, with each
icon inside its hit target. Rounded notification markers remain within the button.
Advert cards contain only the item title and italic poster handle at the lower right;
photos, price, description and connection actions remain in the detail destination.
Native listing share uses the existing Android share sheet; web uses standard share
or copy. Supplied icons, wallpapers, fonts and approved colours are preserved.

## Verification

- 138 backend regression cases passed across chat, calls/push, Vibe, private result
  reviews, matchmaking/scheduling/leagues, original wallet and all Market modules.
- After the expired-reactivation correction, all 30 Market backend cases passed.
- All 30 browser scripts passed, including the compact-card click-to-detail check.
- Android debug builds and all 20 JVM cases passed during integration; the final
  packaged build is recorded in the release/deployment report.
- Isolated seller/buyer browser sessions verified typo correction, compact cards,
  details, save, offer submission and seller acceptance, reservation, demo deposit,
  secure hold, seller fulfillment/delivery, delivery-notification routing, buyer
  confirmation and the seller's released demo balance. No real user funds, listings
  or messages were created. The two accounts used separate local browser origins.
- Browser inspection verified matching Play/Market colour/radius/font/icon placement
  and contained badges, the Market admin panels, and preserved light/dark themes.

## Remaining boundaries

This is a private LAN pilot, not a public production launch. Share links require
access to its server. No real provider, banking details, paid settlement, KYC or
CypherX API is enabled. Existing gaming finance remains separate.

Mandatory Level 1 lexical search is implemented. Multilingual semantic embeddings
and larger-catalog index/caching require a separately provisioned model/runtime and
performance validation; responses explicitly report `semantic_enabled: false`.
No hidden AI call or substitute mock is used. Reviews are unavailable rather than
fabricated, and sellers remain unverified. Physical multi-image selection, share
sheet and Market background-notification tap acceptance remain manual release checks.
