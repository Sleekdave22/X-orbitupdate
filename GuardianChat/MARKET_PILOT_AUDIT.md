# Orbit Market pilot — audit and integration plan

24 October 2026. The user selected `Sleekdave22/X-orbitupdate` as the main project.
The repository name in the pasted handoff is superseded by that instruction.
The original `Sleekdave22/X-Orbit` checkout remains clean at
`bf029cea24983f58022736cb44bbb8c2e18d73ff` and is excluded from this change.

## Baseline and gate

Implementation starts from tested commit `e1ee1f2` on dedicated branch
`feature/market-pilot-foundation`. Navigation checkpoint `1c78c7f` and the previous
private-review release `fbaf55a` remain recoverable. Remote default `main` was
`3b1209ef0ffc554981f3e8035a444a39d6014a37`; `orbit-market` was
`55ab5e6c010749a79941973bbbb47bb682aadbaf`. No merge into either is authorized here.

The baseline Android debug build succeeded, including all 20 JVM tests. All 29
browser test scripts passed. The latest focused backend run passed 31 tests
(`test_market`, `test_wallet`, six Vibe/activity tests); a broader run passed 60
result-review, Market, match, scheduling and league tests. No baseline compile or
test failure was observed. Physical device acceptance of the new Vibe/capture
gestures is pending and is not represented as verified.

The integration map below was completed before Market feature implementation.

| Component | Actual implementation and status | Market connection | Risk |
|---|---|---|---|
| Authentication | Working Python sessions; generated account IDs, PBKDF login; native persisted account | Existing bearer session and immutable user ID; no second login | Never expose tokens/public private account fields |
| Profiles | Existing `users`, avatar and social/contact access checks | Storefront seller name/avatar, explicitly unverified | Do not bypass contact privacy or invent reviews |
| Chat | Working native MainActivity and browser index; `/contacts`, `/messages`, message requests/block rules | Reuse authorized seller conversation, add listing context | Preserve attachments/calls/GuardianLab; no unsolicited messages |
| Notifications | Shared Play notices plus new persistent `account_activity`, category-scoped receipts/badges | Extend Market scope, event targets, history/read receipts | Keep Play separate; background Market push unverified |
| Backend | Python stdlib ThreadingHTTPServer, authenticated route dispatch in `server.py` | Extend existing `/market/*` contracts, modular helpers | LAN pilot, not public production deployment |
| Database | SQLite durable DB; existing `market_accounts`, `market_ads`, `market_reports` | Additive listing metadata/media/offers/saves/order tables | Preserve legacy categories, prices, IDs, records |
| Navigation | Four bottom tabs Vibe/Chat/Calls/Profile; Play and Market above | Keep Market entry and existing routes | No displacement or second marketplace |
| Administration | Existing role-gated Admin Studio; Market report hold/restore/remove | Extend existing studio with Market configuration and moderation | Explicit permissions and audit, no financial edits |
| Wallet | Working test-only NGN `fin_*` double-entry ledger; real payments disabled | Separate `market_demo_*` ledger/orders only | No gaming funds or real provider calls |
| Media | Chat files, private result camera and bounded PIL/PyAV validation | Listing-bound product image validation/storage | No reuse of private chat evidence; bounded upload sizes |
| Android | chat/guardianlab/guardianlab-ui, min SDK29 target36, WebRTC/FCM/CameraX | Existing authenticated Market WebView bridge | Preserve package, stored account, call/push configuration |
| Themes | Approved purple/navy/cyan; shared fonts, wallpapers, light/dark tokens | Existing Market CSS/card/button conventions | No global redesign or replacement artwork |

## Actual Market inventory

Working: one shop per account, unique shop name, text adverts, 30-day expiry,
owner renewal/removal, authenticated cross-account discovery, basic token search,
shop filtering, existing seller Chat route, reporting and administrator restoration.
Eight Market backend baseline tests verify these contracts, including migration
preservation and blocked contact rejection. Market is not an empty interface.

Partial: search is SQL LIKE with six terms, returning grouped sellers; notification
scope exists but only moderation events and a generic shop destination. Admin
moderation lives in My shop. No verified Market background push.

Missing: structured editor and state machine, twelve stable category IDs and
subcategories/attributes, product photos/details, locations and explicit currencies,
typo/synonym search, saves, persistent negotiations and reservations, listing context
cards, simulated commerce/order ledger, broader Market admin configuration.

## Architecture and compatibility decisions

- Extend legacy `market_ads` with separate additive metadata/media/config tables.
  Keep `/market/ads`, `/market/account`, `post_ad`, renew/remove and existing IDs.
  New clients use `/market/listings` and `/market/listing`; legacy text prices remain
  visible and are never silently converted to monetary values.
- New listing status is explicit and separate from order/payment state. Map legacy
  active/held/removed at the boundary without renaming existing tables or data.
- Use server-side transactions for edits, reservations, negotiations and demo money;
  idempotency keys/revision checks prevent repeated or conflicting mutations.
- Product media receives its own listing access checks, MIME decoding and size limits.
- Level 1 search uses normalized token/attribute matching, bounded typo expansion,
  exact model/year/storage checks, ranked pagination and saved search settings.
  SQLite is retained; no OpenSearch/PostgreSQL migration is necessary for the pilot.
- Semantic multilingual embeddings require a selected local model/runtime and an
  index lifecycle. They follow a verified lexical release; no ordinary query will
  incur an external language-model call and unavailable semantics will be disclosed.
- Near Me requires a saved/explicit locality or coordinates; worldwide discovery
  never implies worldwide shipping. Standard country codes and currency are explicit.
- Demo accounting is independently named and always labelled simulated. CypherX
  remains deferred behind a provider-independent contract, with no API credentials
  or money movement.

## Incremental implementation order and acceptance

1. Foundation: categories, additive listing editor/media/status/storefront, responsive
   existing-theme UI. Verify owner/other-account visibility, validation, migration,
   image access, edits and status transitions; commit/report.
2. Lexical search: typo/synonym/attribute ranking, filters/location, pagination and
   labelled alternatives. Verify handoff examples and exact model safeguards.
3. Connections and activity: detail links, saves/share/report, authorized listing Chat
   context, offers/history/reservations; separate targeted Market notifications and
   seen receipts. Verify concurrency, blocked/self inquiry, restart persistence.
4. Demo commerce: separate immutable ledger, hold/fulfillment/delivery/buyer release,
   refunds/disputes and adapter boundary. Verify idempotency/reconciliation and that
   seller delivery cannot release funds or alter any gaming balance.
5. Administration/trust: category/subcategory/attributes, synonyms, moderation,
   restrictions/featured/config/notification settings and demo inspection in Studio.
6. Regression/two-account acceptance: web and Android light/dark; Chat/Play/Vibe/
   Profile/calls/security remain functional. Report actual evidence and limitations.

Each stage is tested and committed independently. Real user listings, unsolicited
messages, paid transactions and unverifiable production-readiness claims are excluded
from automated acceptance data. Synthetic two-account testing uses an isolated DB.
