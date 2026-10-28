# X-Orbit engineering integration review — 28 October 2026

This is an implementation-stage report, not a production certification or a claim that every historical handoff is finished.

## Repository and preservation

| Copy | Inspected state | Use |
| --- | --- | --- |
| Sleekdave22/X-orbitupdate | feature/vibe-timed-navigation; baseline a5142c78bc9c458e2037846c108fae2b412ecd10 | User-selected active project; includes Plaza and all integrated work |
| X-orbitupdate default main | 3b1209ef0ffc554981f3e8035a444a39d6014a37 | Audited/fetched; not merged or reset |
| Sleekdave22/X-Orbit default main | 3b1209ef0ffc554981f3e8035a444a39d6014a37 | Reference only; original repository untouched |
| Original local XOrbitStandalone | bf029cea24983f58022736cb44bbb8c2e18d73ff, clean at inspection | Preserved |

The attachment names X-Orbit, but the human instruction selected X-orbitupdate as the main project. No source was copied over the original repository. Existing PNGs, icons, theme rules, application ID, account records and GuardianLab implementation are not changed by this stage.

## Inventory and integration findings

| Area | Actual implementation | Assessment / limits |
| --- | --- | --- |
| Identity/auth | server.py, account_invites.py, account_preferences.py, social.py | Persistent shared Guardian IDs, sessions, password hashing and account-scoped preferences exist. Automated authorization tests exist. A read-only existing browser-session search found the real @s21 account; no new-account enrollment/recovery test was performed. |
| Chat/calls | server.py, message_notifications.py, MainActivity.kt, ChatApi.kt, calls.js, WebRTC integration | Messaging, receipt/attachment authorization and call flows exist. Synthetic HTTP tests are not a new physical interruption/notification test. |
| Vibe/privacy | vibes.py, vibe_privacy.py, vibe_sources.py, vibe.js, ProtectionMonitor.kt | Timed public/private media, contact audiences, replies, reactions, viewer state and platform protection paths exist. Physical protection effectiveness is experimental and not certified. |
| Media editor | media_editor.py, media_processing.py, media-editor.js | Real crop/trim processing, bounded worker slot and source retention exist. Media regressions are included; no new device orientation claim. |
| Play | game_identities.py, gamebox_core.py, match_scheduling.py, competition_context.py | Gaming identities, availability, matching and server-authoritative result flow exist. No phone-verification provider is configured; no new eligibility gates were imposed. |
| Results/disputes | result_reviews.py, gaming_ocr.py, private-results.js, evidence-camera.js | Private evidence jobs, conservative local OCR, video escalation, fifteen-minute response logic and moderator path exist. OCR is not publisher authentication and ambiguous captures can defer. |
| Rankings | rankings.py plus existing gb_ratings tables | Verified open-match awards, per-game records, versioned policy, history and provisional placements exist. New nine-test current-engine coverage added. Legacy test contracts conflict, described below. |
| Competitions | gaming.py, sponsored_leagues.py | Fixtures, deadlines, controlled states, standings and appeals exist with backend tests. No real-money competition readiness claim. |
| Streaming | match_streams.py, stream_lifecycle.py, stream_relay.py | Authorized match rooms, virtual-camera source choices and in-memory LAN fan-out exist. No fixed spectator cap is not unlimited infrastructure capacity. |
| Plaza | market.py, market_pilot.py, market_listing_types.py, market_search.py, market_connections.py, market_admin.py | Four listing types, conditional fields/pricing, media, discovery, inquiries/offers, moderation and activity exist. Broad browse currently materializes candidate listings before lexical pagination. |
| Demand | market_demand.py, market-demand.js | Missing at baseline; implemented in version 41 with categorized grouping, requester alerts and controlled seller pushes. See DEMAND_HOT_DEMAND_V41.md. |
| Wallet | wallet.py and market_demo.py | Simulated balances/ledgers and demo transactions only. No real provider deposits, custody, escrow or prize payouts activated. |
| Admin | studio.js plus module admin endpoints/audit tables | Existing role checks preserved; Demand threshold/push cap added with audit reason. Operational data are not manually rewritten. |

## Confirmed issue fixed

Plaza notification dispatch previously tested a busy flag before selecting and starting its worker. Two callers could both select the same undelivered batch before either set the flag.
A server-local nonblocking lock now owns the batch from selection through worker completion and releases on early return/failure. A regression launches sixteen calls across eight threads and observes a single send. The existing session-scoped, metadata-only push contract remains intact.

Demand's new implementation additionally checks actual listing availability, review status, expiry and participant block/withdrawal state before creating requester alerts. A direct-link notification is generated below the Hot Demand threshold too: an individual requester need not wait for five people.

## Verification ledger

Baseline frozen at a5142c7: 366 Python tests ran in 543.729 seconds. 353 passed; 13 errored in test_rating.py because it calls removed gamebox_core rating functions/settings.
The legacy suite references apply_rating, rating_change, rating_tier, tier_bounds, old K/start-rating keys and pair-pattern flags. These are not the active rankings.py contracts.

No legacy tests were deleted/skipped and no obsolete rating functions were restored to make the report green. Current-engine regressions independently verify equal win/loss/draw, favorite/underdog rating movement, game separation, verified-only awards, exactly-once history, competition/global separation and current placement defaults. Those nine tests pass.

Version 41: 388 Python tests in 593.571 seconds; 375 passed, the same 13 legacy test errors remain, no skipped tests and no new failures. Error test names match the baseline exactly. All 41 JavaScript regression scripts passed.
Browser: isolated Demand submit/count/withdraw and error-console check passed. The existing live browser session also searched for s21 and returned the real @s21 account marked In your chats; no contact/message was added. This read-only discovery check used the still-running version 39 backend. Earlier version 40 browser checks are documented separately.
Android: debug build passed; 24 JVM tests passed with zero failures/errors/skips. All 73 interface hashes and 56 bundled assets match the APK.
Physical S21 installation/testing deferred explicitly by the user. The real-account search above does not verify new enrollment, every privacy case or physical push delivery.

## Database, performance and failure isolation

The backend remains a modular Python ThreadingHTTPServer with SQLite. Connection timeout is fifteen seconds; sensitive write paths use BEGIN IMMEDIATE. Existing service maintenance isolates Plaza/Demand exceptions so their failure does not inherently stop ordinary chat requests. This does not eliminate shared CPU, disk or SQLite contention.

Demand has additive indexes, twenty-group pagination, exact signatures before bounded candidate similarity, deduplicated transactions and durable jobs with bounded retries. EXPLAIN QUERY PLAN in the regression suite confirms the member-count query uses market_demand_members. No throughput/latency improvement percentage is claimed.

Remaining measured-work candidates:
- Plaza broad listing discovery creates full view objects before in-memory lexical filtering/pagination; benchmark candidate counts, query counts and p95/p99 latency before changing behavior.
- Navigation summary scans active Vibes and checks per-item privacy/connection state; profile it at realistic retained-media counts.
- Threaded requests, synchronous SQLite and relay encoding share one machine. Load tests and admission limits are needed before promising launch capacity.
- Media processing already limits one concurrent process and four pending jobs, but production disk/CPU/memory exhaustion and restart recovery need controlled load/fault tests.
- A local lock only coordinates one server process. Multiple authoritative app processes need transactional job claiming before deployment.
- FCM send acknowledgment is not a device display receipt. Existing retries may repeat after a process failure between provider send and database receipt; per-notice client dedupe remains important.

No destructive migration, database-engine replacement, general rewrite or unmeasured performance optimization was made.

## Security and policy gaps kept explicit

- Authorization, admin roles, private media access, result/rating idempotency, simulated ledger integrity and block handling have automated tests; this is not a penetration test or whole-codebase security guarantee.
- Optional phone linking/contact discovery remains on hold. The handoff's future phone-verified participation rule cannot honestly be marked complete without a provider, enrollment/recovery design and approved rollout. Existing users were not suddenly locked out.
- Hot Demand counts unique authenticated accounts, not verified humans; coordinated account abuse remains a limitation.
- Legacy rating anti-pairing/tier policy requires product/engineering reconciliation. Do not silently restore old formulas or penalties.
- Private Vibe cache authorization, shielding and external-camera detection stay platform-constrained. No promise to prevent all physical recording.
- Public hosting needs production HTTP serving/proxy hardening, secrets management, TLS lifecycle, monitoring, backup restoration tests, access review and abuse controls.

## Hosting preparation, not deployment

Recommendation: keep the existing modular application for an initial controlled pilot. Separate media storage and real-time media delivery as usage justifies it; do not introduce microservices simply because the app has several products. Migration to PostgreSQL/object storage/SFU requires adapter work, compatibility tests and approval, not just purchasing accounts.

Illustrative monthly USD costs checked against official pricing on 28 October 2026:
- A regular 2-vCPU / 4-GiB DigitalOcean VM with 80-GiB disk is $24; daily percentage-based backups add 30% ($7.20). [VM and backup pricing](https://www.digitalocean.com/pricing/droplets)
- R2 Standard storage is $0.015/GB-month with 10 GB-month free; Class A/B operations have separate free allowances and direct egress is free. A 50-GB-month pilot with 50,000 writes and 500,000 reads would be about $0.60 storage, within free operation allowances. [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- Cloudflare Realtime SFU/TURN share a 1,000-GB/month allowance, then $0.05/GB egress. At 2 Mbps, one hour/day for thirty days, ten viewers use about 270 GB; one hundred use about 2,700 GB, or $85 above the allowance. This arithmetic excludes protocol overhead, calls and other shared traffic. [Realtime pricing](https://developers.cloudflare.com/realtime/sfu/platform/pricing/)
- Managed PostgreSQL lists a 1-GiB / 1-vCPU entry at $15.15/month and storage at $0.215/GiB/month; confirm selected storage and final total before approval. It is not a drop-in replacement for this SQLite application. [Database pricing](https://www.digitalocean.com/pricing/managed-databases)

The small VM + daily backup + illustrative R2 storage subtotal is $31.80/month, before tax, domain, SMS, monitoring, engineering and any media overage. This is a usage-cost scenario, not a capacity guarantee. No provider was provisioned or paid.

## Priorities after this stage

1. Version 41 local browser deployment is complete (DEMAND_V41_DEPLOYMENT.md). Exercise requester alerts with consenting real accounts; phone installation stays deferred.
2. Resolve the legacy/current rating test and policy mismatch explicitly, preserving authoritative result math.
3. Follow the separately requested behavior-preserving readability review, with a prioritized plan and developer guide, after the pending feature work is complete.
4. Benchmark real browse/navigation workloads, then choose limited optimizations with output parity and concurrency tests.
5. Agree verification/eligibility rollout and production infrastructure before enabling those external dependencies.
