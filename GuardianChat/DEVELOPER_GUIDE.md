# X-Orbit developer guide

Start here for the current integrated app. The repository also contains GuardianLab SDK/demo modules; their entry points are different. Project change rules live in ../AGENTS.md. Current review scope and priorities are in READABILITY_REVIEW.md.

## System map

One shared Python backend owns identities, SQLite data and feature decisions. Browser pages and the Android app are clients of that backend. Android uses native chat/protected viewers plus WebViews for Play, Plaza, Vibe and some shared flows. Product labels have changed over time: internal gamebox/gb and market names intentionally remain stable.

| Change area | Start with | Data / useful tests |
| --- | --- | --- |
| HTTP routing, auth, messages, attachments, calls | server/server.py; server/index.html; chat/.../MainActivity.kt and ChatApi.kt | users, sessions, contacts, messages, call_history; test_server.py, test_message_notifications.py |
| Identity, profiles, account search/preferences | server/social.py, account_invites.py, account_preferences.py; account-search.js, personalization.js | social_* and account_*; test_social.py, test_account_search.py, test_account_preferences.py |
| Bottom-tab counts and seen receipts | server/navigation_state.py; orbit-navigation.js; MainActivity.kt | navigation_call_views, messages, vibe_views; test_navigation_state.py |
| Module-owned settings and overlay layers | server/module-settings.js, module-navigation.js, navigation.css; MainActivity.kt showNavigationMenu/showSettings | Existing preferences and module tools; test_module_settings.js |
| Vibe feed, privacy, reactions/replies | server/vibes.py, vibe_privacy.py, vibe_sources.py; vibe.js, vibe-cache.js | vibe_*; test_vibes_activity.py, test_vibe_privacy.py, test_vibe_sources.py |
| Crop/trim processing | server/media_editor.py, media_processing.py; media-editor.js | media_editor_*; test_media_editor.py, test_media_processing.py |
| Gaming IDs, matching and scheduling | server/game_identities.py, gamebox_core.py, match_scheduling.py | gb_*, game_*; test_phase_b.py, test_gamebox_core.py, test_match_scheduling.py |
| Results, disputes and rankings | server/result_reviews.py, gaming_ocr.py, rankings.py, competition_context.py | result_review_*, gb_rank_*; test_result_reviews.py, test_active_ratings.py |
| Short result videos, review summaries and appeal evidence holds | server/result_video.py, result_retention.py; private-results.js | result_evidence_retention, result_evidence_appeals; test_result_review_hardening.py, test_result_appeal_ui.js |
| Leagues and sponsored competitions | server/gaming.py, sponsored_leagues.py; sponsored-ui.js | leagues, fixtures, sl_*; test_gaming.py, test_sponsored_leagues.py |
| Streams/camera sources | server/match_streams.py, stream_lifecycle.py, stream_relay.py; camera-sources.js | game_stream_* and in-memory relay peers; test_match_streams.py, test_stream_relay.py |
| Plaza listing lifecycle | server/market.py dispatches to market_pilot.py and market_listing_types.py; market.js | market_ads, market_listing_meta; test_market_pilot.py, test_market_listing_types.py |
| Plaza search/location | server/market_search.py, market_location.py | market_discovery, market_synonyms; test_market_search.py, test_market_refinement.py, test_market_location.py |
| Demand/requester alerts | server/market_demand.py; market-demand.js | market_demand_*; test_market_demand.py, test_market_demand_ui.js |
| Offers/activity/moderation | server/market_connections.py, market_admin.py; market.js | market_offers, account_activity, market_admin_audit; test_market_connections.py, test_market_push.py, test_market_admin.py |
| Simulated finance | server/wallet.py, market_demo.py | fin_* and market_demo_*; test_wallet.py, test_market_demo.py |
| GuardianLab protection | guardianlab/, guardianlab-ui/; chat/.../ProtectionMonitor.kt, ProtectedStore.kt | On-device monitoring/protection, not ordinary message transport; module and device tests |

Android files abbreviated chat/... above live in chat/src/main/java/com/guardianlab/chat/. Browser HTML/CSS/JS live beside the Python modules in server/. A source folder's short filename does not imply a simple component: several files contain long compound statements.

## Trace a feature end to end

**Publish advert → requester alert**

1. market.js validates the form for usability, then posts /market/save_listing with a retry key.
2. server.py authenticates the session and market.py delegates to market_pilot.post. Backend validation, seller permissions, revision checks and transaction rules are authoritative.
3. The listing write enqueues a Demand job in the same SQLite transaction. Draft/reviewed content is not publicly available yet.
4. ChatServer._gamebox_service_actions invokes market_demand.maintenance periodically. It checks current publication/availability, category/type/model compatibility and requester block/withdrawal state, then records account_activity and deduplication rows.
5. market_connections.dispatch owns a batch with a local lock. Hot Demand daily budgets are reserved in a transaction. Push carries IDs only; an authenticated client fetches the notification and opens the exact listing.
6. The UI marks the displayed/engaged notification seen through the existing receipt endpoint. Reading a list is not authorization to change someone else's state.

**Verified result → ranking**

Result evidence enters result_reviews.py, which stores private evidence and review jobs. OCR extracts possible data; rules decide whether it is sufficient or needs video/moderation. The result-finalization path calls rankings.award inside its write transaction. Unique source/award records prevent duplicate rating updates. Do not call award from a UI action or update ratings/standings directly. Competition origins and policy bindings affect eligibility/math; read competition_context.py before changing that path.

**Navigation badge → acknowledgment**

GET /navigation/state computes counts but does not mark messages, calls or Vibes seen. It first expires stale calls under the existing call lock. Message reads, displayed-call receipts and Vibe view actions have separate authenticated endpoints. Hiding a chat suppresses only its stored message snapshot; later arrivals can still badge. Private Vibes must pass both audience/privacy checks and feed-connection rules before contributing.

**Result finalization → appeal → cleanup**

New camera evidence is limited to 3–10 seconds and 20 MB. `result_video.inspect`
measures decoded frame timestamps, including phone WebM without a duration header.
It samples proportionally rather than every five seconds. Existing stored clips
remain reviewable under their old 60-second limit; this compatibility is not an
upload bypass. Vibe's independent 60-second policy is unchanged. Frame/OCR
consistency is not publisher authentication or a measured fraud-detection model.

Finalization calls `result_retention.schedule` in the same transaction. The frozen
match/competition `retention_seconds` supplies both evidence expiry and the appeal
window (normally three days). Duplicate finalization does not restart the clock.
Only the match participants may file `/gamebox/evidence_appeal`, before that window
closes. Filing is idempotent and retains the original reason. The opponent sees a
receipt/notification, not private evidence or the other player's appeal text.

Independent authorized reviewers fetch `/gamebox/review-summary?room=...` for
reports, OCR findings, policy, reasons, decision actor, appeals and audit records.
Existing no-store photo/video routes remain separately authorized. Reviewers use
`/gamebox/evidence_appeal_decide` to uphold a result or flag `correction_required`.
Neither action edits scores or ratings. A required correction deliberately keeps
the evidence hold: an actual score change needs an audited reversal/recalculation
workflow, which is not supplied by this evidence-retention checkpoint.

`result_retention.purge` is the sole ordinary match-evidence cleanup path. The tick
and review dispatcher invoke it under `BEGIN IMMEDIATE`, sharing the write lock
with appeal filing. Unresolved cases and open/correction appeals are preserved;
due, unheld final evidence bytes and raw OCR text are removed while score,
reason, policy, submission digest and decision/audit records remain.
Older finalized matches without the new deadline record keep their existing
expiry; initialization does not invent a new appeal deadline for old results.

For focused checks from `server/`, run `python -m unittest -q
test_result_reviews test_result_review_hardening test_active_ratings`. The new
decode tests use actual encoded MP4/WebM, but decision tests still inject OCR;
real-game recognition accuracy requires a labeled capture set and device checks.

## Run a separate local development instance

Use a separate data directory and port. Do not start another authoritative server on the existing shared database to experiment.

From GuardianChat/:

~~~sh
python3.12 -m venv server/.venv
server/.venv/bin/python -m pip install -r server/requirements-gaming.txt -r server/requirements-push.txt -r server/requirements-streaming.txt
server/.venv/bin/python server/server.py --host 127.0.0.1 --port 8786 --data .local-dev-data
~~~

These are existing optional dependency manifests, not a new dependency change. QR support is vendored. The gaming manifest supplies image/video/OCR dependencies; streaming uses aiortc; push uses Firebase Admin and a server-side credential file only when configured. Basic startup can run without every optional service, but the complete media/streaming test suite needs its dependencies.

Default server CLI port is 8765. The user's configured HTTPS deployment currently uses 8766 with a mirror on 8768. Runtime launch/backup receipts are local operational files outside Git. Use its existing startup procedure for that environment, not the isolated command above.

Camera/microphone features need a secure browser context. HTTPS startup additionally accepts --cert and --key together. Use a trusted local certificate and the existing Android trust configuration; do not disable TLS verification. Network address changes can make the saved phone server unreachable without any account-data problem.

The data directory contains chat.sqlite, files, invite.txt and optional push credentials. Keep it private and out of Git. Back up the database consistently (SQLite backup API) and media before migrations; copying a live database file blindly is unsafe. Initialization performs additive migrations at startup.

## Build and test

From GuardianChat/, using Android Studio's bundled JDK and the configured SDK:

~~~sh
./gradlew :chat:assembleDebug :chat:testDebugUnitTest
~~~

The normal package remains com.guardianlab.chat. -PorbitComparison=true creates the separate comparison package; do not use that flag accidentally. chat/build.gradle.kts packages selected static assets, while ComparisonWebAssets/ComparisonAssetPolicy control interception. API requests must keep using the authenticated configured server. New browser assets may need both the server static allowlist and the Gradle bundle list.

From GuardianChat/server/, with the project virtualenv active:

~~~sh
python -m unittest -q test_navigation_state test_market_refinement test_market_search test_market_location
python -m unittest -q test_market_demand test_market_push test_market_admin
python -m unittest -q test_phase_b test_active_ratings test_result_reviews
python -m unittest discover -q
~~~

Browser regression scripts use Node directly; from GuardianChat/:

~~~sh
for test_file in server/test_*.js; do node "$test_file" || break; done
~~~

A script stopping early is not a full-suite pass. Most scripts use the small browser-test-dom.cjs harness; they do not replace real browser/device checks. Run affected UI routes in both themes. Keep test accounts/media in isolated data directories; synthetic tests do not prove real-account enrollment, real push delivery or physical camera-protection effectiveness.

At the version 41 baseline, 388 Python tests ran: 375 passed and thirteen errors remained in legacy test_rating.py, which calls removed ranking contracts. Do not skip/delete those tests or silently restore obsolete math. Read MASTER_ENGINEERING_REVIEW_20261028.md. Report the exact before/after suite, unavailable checks and any changed failure set.

## Safe changes and common traps

- Public contracts include routes, JSON keys/error messages, SQL identifiers, retry keys, native bridge method names and static asset paths. Preserve them during refactoring.
- Follow server.db() connection/transaction ownership. An exception in a BEGIN IMMEDIATE context must roll back the entire operation; partial acknowledgments or partial awards are unsafe.
- Dynamic imports and WebView bridges are callers. Search __import__, JavaScriptInterface, script tags, static allowlists and Gradle packaging before removing or moving code.
- Polling, push and notification receipts differ. A provider acknowledgment does not mean the phone displayed/read the alert. Batch locks are process-local; do not assume they coordinate multiple app servers.
- Normal public media caches and protected private content have different authorization/retention rules. Never optimize a protected path by reusing an unrestricted cache.
- Result-evidence capture and the ordinary media editor are separate flows; the editor must not make result proof trusted.
- Wallets/Plaza payment examples remain simulations. No real-money feature follows automatically from a UI or ledger table.
- Phone contact discovery/linking remains on hold; no provider-backed verification rollout has been approved.
- server.py/MainActivity.kt are still dense. Extract one tested responsibility at a time rather than rewriting either controller.

For future work, update this guide when file ownership or data flow changes, explain non-obvious decisions near the code, and keep behavior fixes separate from readability commits.

## Section settings

Play/Plaza browser settings are rendered by `module-settings.js` over the current
page. Never route their icons to `/?home=settings`: that recreates Chat and loses
the current module context. Account colours still use `OrbitPersonalization.mount`
and `/preferences`; appearance is the existing browser setting. The additional
section tools invoke existing controls, not new settings APIs. Chat's existing
menu/panel nodes are reparented to the body without replacing handlers because a
child z-index cannot escape the fixed header's lower stacking context. Drawers use
50% viewport width; keyboard Escape and focus remain within the owned drawer.
Native account/settings overlays likewise use half the viewport.

