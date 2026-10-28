# Demand and Hot Demand — version 41

Status: implemented, tested, pushed as eb165a4 and deployed to both local browser addresses. See DEMAND_V41_DEPLOYMENT.md; the S21 installation and page-open confirmation are now recorded there.
Repository: Sleekdave22/X-orbitupdate, branch feature/vibe-timed-navigation.
Original Sleekdave22/X-Orbit is not modified. Includes the already committed version 40 navigation/Vibe corrections.

## Implemented

- A closed Requests & Hot Demand panel after the existing Plaza content, using its current controls, typography and account palette. Existing navigation and listing controls retain their positions.
- Categorized product, service, skill and job requests, descriptions, request joining and owner-only withdrawal.
- Conservative normalization, configured synonyms and category/type matching. Model numbers must agree. Grouping uses exact signatures first, then token similarity; it does not call a paid AI service.
- Five distinct active accounts initially makes a group Hot Demand. Admin Studio can configure three to five, with a recorded reason.
- Relevant sellers explicitly opt in. Categories come from their selections or active inventory. All opportunities remain available in Plaza even when pushes are capped.
- Hot Demand pushes have a configurable maximum of two per recipient per UTC day (zero disables). Retries reuse the reserved slot. This cap does not suppress the requester's matching-advert notification.
- Requesters receive account-scoped Plaza activity when a matching advert becomes publicly available. Its target includes the exact listing ID; opening it follows the existing listing-details route.
- Drafts, pending moderation, expired listings, unavailable stock/work and expired job applications do not qualify. Withdrawn requesters and accounts blocked from the seller do not receive new matching alerts.
- Repeated edits to the same listing do not repeat its alert. A different matching listing can alert the requester. Seller Hot Demand notices are once per unresolved group.
- Request retries are idempotent and concurrent joining cannot inflate account counts. Limits: three new requests/hour, ten active requests, thirty new retry keys/hour. Requests expire after thirty days.
- Matching work is queued durably in SQLite. Batches contain at most ten jobs, with bounded retry/backoff and isolated failure handling.
- Confirmed existing Plaza push-worker race corrected with a nonblocking server lock around batch ownership. Concurrent dispatch calls no longer send the same batch simultaneously. This is a reliability fix, separate from any future readability cleanup.

## Files and contracts

New:
- server/market_demand.py — additive schema, matching, jobs, notification policy and permissions.
- server/market-demand.js — request panel, submission/retry state, preferences and notification target.
- server/test_market_demand.py and server/test_market_demand_ui.js.
- server/test_active_ratings.py — regression coverage for the current ranking implementation; no ranking logic change.

Integrated:
- server/market.py and server/market_pilot.py — routes and publish/restore job creation.
- server/market_admin.py — policy included in existing admin response.
- server/market_connections.py — push batch ownership and Hot Demand budget.
- server/server.py — static asset allowlist and isolated background maintenance.
- server/market.html and server/market.js — additive panel, existing activity targets/badges and collapsed admin policy.
- chat/build.gradle.kts — version 41 and bundled Demand asset.
- server/phone-interface-manifest.json — matching version and asset hashes.

Authenticated GET:
- /market/demands (category and offset; twenty groups/page, plus own requests)
- /market/demand?id=...
- /market/demand_preferences

Authenticated POST:
- /market/demand_request (title, description, category_id, listing_type, client_id)
- /market/demand_withdraw (id)
- /market/demand_preferences (updates, categories)
- /market/admin_demand (policy, reason; existing admin permission required)

Existing event contract: category market, section demand, target {demand,event,listing?}.
Push event remains market_notice with notice_id/recipient/expiry only. Clients fetch private notification details through their authenticated session; no request text or credentials are sent through FCM.

## Database

New tables: market_demand_policy, market_demand_groups, market_demand_requests,
market_demand_keys, market_demand_preferences, market_demand_notices,
market_demand_push_budget, market_demand_jobs.
Indexes cover group matching/expiry, group members, owners and request/key rate checks.
Existing tables, identifiers and records are preserved. Initialization is additive.
Demand writes and notification creation run in existing explicit SQLite transactions.

## Verification

- 13 Demand backend tests passed, including concurrent retries, five-account grouping, independent model/category checks, policy permissions/audit, seller opt-in, push cap, private notification ownership, exact advert target, publish/review gating, blocked/withdrawn requesters, edit deduplication and worker retry.
- 9 current-ranking regressions passed. An initial new test incorrectly updated a rating row before that row existed; the fixture now inserts its intended starting ratings. Production rating code was not changed.
- 41 JavaScript regression scripts passed.
- Android debug build passed. 24 JVM tests passed; 73 manifest files and 56 bundled assets match the packaged APK.
- Isolated browser account: submit request, see own/group count and withdraw passed; no browser warning/error logged. Failed-submit tests retain draft values and reuse the retry key.
- Full backend: 388 tests in 593.571 seconds; 375 passed and the same 13 legacy rating-contract errors remain. No skipped tests or new failures. Details are in MASTER_ENGINEERING_REVIEW_20261028.md.
- Live-account discovery, end-to-end real FCM delivery for this new feature and S21 physical UI checks are not claimed. The user subsequently authorized installation and confirmed the Demand page opens normally; full device performance and real requester FCM display were not retested.

## Manual check after deployment

1. In Plaza, open Requests & Hot Demand and describe a categorized item.
2. In a second account, register a shop and publish an available matching listing.
3. In the requester's Plaza bell/activity, open the new alert: it should show that exact advert.
4. Save an edit to the same advert: no second alert for that account/group/listing.
5. Join a request from five separate accounts; an opted-in seller in that category gets a Hot Demand notice.
6. Withdraw a request and publish another match: that requester gets no new match alert.

## Limits and retained boundaries

Similarity is lexical and intentionally conservative; some differently worded requests will remain separate. Distinct accounts and rate limits reduce repeated requests but do not prove distinct humans or eliminate coordinated account abuse.
Descriptions are public; the form states this. Requester IDs are not returned in the public group feed.
No phone/contact linking or new phone-verification gate was introduced. That separate work remains on hold.
No real money, provider subscription, public hosting, destructive migration or unrelated redesign was activated.
Push delivery still depends on configured FCM, valid device/session registration and device connectivity; it is not a guaranteed delivery service.
