# Market version 28 — deployment and acceptance

25 October 2026. Repository: `Sleekdave22/X-orbitupdate`.
Branch: `feature/market-pilot-foundation`.
Runtime implementation: `b8ad89bbf9905d4d31d378fbc1df5237c0d2a90a`.
Android: `com.guardianlab.chat`, versionCode 28, `0.28-market-pilot`.

## Delivered

The Market pilot adds structured listings/photos/categories, lexical typo and
synonym search, location/currency filters, storefronts, saves, product-linked
authorized chat, offers/reservations, persistent Market activity, separate simulated
orders/accounting and role-gated Market administration. Milestone reports 1–5
document routes, additive migrations, permissions, files and individual checkpoints.

Play and Market retain the approved purple interface and now have matching upper
buttons with their icons inside and contained notification markers. Advert cards
show only the item name and italic poster handle; tapping opens full details/actions.
Existing four-tab navigation, Vibe, chat, calls, profiles and gaming remain connected.

## Deployment evidence

- Created a consistent SQLite backup before the restart. No test accounts, listings,
  messages or demo deposits were introduced into the shared live database.
- Both `https://localhost:8766/` and `https://localhost:8768/` serve the same frozen
  implementation. Verified root HTML, Market HTML/JS, navigation CSS and listing-chat
  JS against the release bytes using the trusted local CA. Port 8768 proxies API
  requests to the authoritative 8766 backend; it has no separate accounts/database.
- Database integrity passed after restart. Categories migrated additively, and the
  live Market demo journal remained empty. Real payment features remain disabled.
- Android update installed successfully over Wi-Fi with `install -r`. Package
  metadata confirms version 28. The saved @s21 account and server address
  `https://192.168.1.171:8766` were retained. Using that saved session, authenticated
  profile, Market catalog/activity/demo-wallet and existing league/match APIs passed.
  Credentials were neither displayed nor committed.
- Refreshed the existing browser session at 8768 without clearing account data;
  its chats and four bottom destinations loaded, and Market opened successfully
  with the new categories/actions and purple appearance.
- The user confirmed on the S21: matching Play/Market buttons with contained icons,
  compact advert cards and working full details all look right.
- Original `Sleekdave22/X-Orbit` remains clean at
  `bf029cea24983f58022736cb44bbb8c2e18d73ff`. No default-branch merge was performed.

## Actual verification

- 138 backend regression cases passed across Market, wallet, Vibe, messaging,
  call/push, result review, matchmaking, scheduling and leagues.
- Following the final expired-listing reactivation correction, 30 Market backend
  cases passed. All 30 browser test scripts passed.
- Final Android build succeeded and all 20 JVM cases passed. Verified all 62 web
  manifest hashes and parity of the 45 bundled comparison web assets.
- Isolated two-account browser checks completed save, offer, acceptance/reservation,
  simulated deposit/hold, fulfillment/delivery, exact delivery-notification routing,
  buyer confirmation and seller released balance. Duplicate settlement was unavailable.
- Visually checked matching navigation buttons, compact cards/details, admin controls
  and both light/dark Market themes. Isolated QA data never used the shared live DB.

## Boundaries and remaining checks

This is a private LAN pilot, not a production-readiness declaration. Level 1 lexical
search works; multilingual semantic embeddings and larger-catalog indexing/caching
remain unprovisioned (`semantic_enabled: false`). No real deposit, withdrawal,
payment provider, KYC, bank transfer or CypherX integration is enabled. Demo funds
are separate from the original gaming ledger.

Physical multi-image selection, native share-sheet behavior and background Market
push/tap routing still need device acceptance. Automated notification tests and the
successful installation do not prove those physical behaviors. General mobile
reachability still depends on the Mac server and shared LAN. Existing arbitrary
force-stopped-app restrictions are not represented as solved.

## Manual verification

Open `https://localhost:8766/market.html` (or port 8768) on the Mac. On the S21,
open X_ORBIT and Market. Inspect a card, then open its details; verify both navigation
entries match. Use a draft to check multiple photo selection and the share sheet.
For Market push acceptance, leave the recipient app in the background and generate
an authorized test offer/order event from a second account; confirm the notification
opens that exact item and only the Market unread count changes. Use isolated demo
accounts for the simulated order workflow; no real money is involved.
