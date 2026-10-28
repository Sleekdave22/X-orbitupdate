# Readability pass 1 — validation and remaining work

Behavioral baseline: version 41, eb165a4. Review/priority plan and project standards were committed before refactoring (4b27278).

## Changes

- e02cf19: navigation_state.py now separates message, missed-call and Vibe summaries. Comments explain read/acknowledgment separation, call-expiry side effects, atomic authorization, privacy checks and oldest-first/latest-reference ordering.
- e9bb044: market_location.py now uses readable statements/local names. Comments explain approximate units/precision, numeric validation, missing coordinates, spherical distance and per-search row copies.
- Public function signatures, routes, JSON keys, error messages, SQL predicates and ordering remain unchanged.
- No schema, UI, dependency, business policy, data retention, ranking logic or GuardianLab change. No allegedly unused code was removed.
- AGENTS.md establishes the same human-readable standard for future changes, helpful comments, test discipline and focused commits.
- DEVELOPER_GUIDE.md maps features to files/data/tests, traces advert-to-alert and result-to-ranking flows, and describes isolated run/build/test procedures.
- Root and app READMEs now direct engineers to that current guide while retaining historical prototype notes.

## Before/after checks

- Existing affected tests before modification: 18 passed in 23.984 seconds.
- Seven additional characterization tests passed against the original implementation, making 25 tests in 27.476 seconds. They cover duplicate/empty call receipts, hidden-chat boundaries, coordinate validation, copy semantics, unknown distances, radius behavior and error contracts.
- The same 25 tests passed after refactoring, in 19.123 seconds. Timing differences are not claimed as a performance improvement.
- Broader caller suite after refactoring: 118 tests passed in 122.073 seconds, no failures/errors/skips. Modules: test_navigation_state, test_market_location, test_market_refinement, test_market_search, test_market_pilot, test_market_listing_types, test_market_demand, test_vibe_privacy, test_vibes_activity, test_vibe_sources, test_account_search, test_message_notifications, test_market_push, test_market_admin.
- Navigation SQL strings match the deployed version after whitespace normalization. Location public signatures match; 1,000 seeded coordinate/distance/filter comparisons produce the same results.
- git diff --check passed.

The earlier feature-stage full run remains 388 tests: 375 pass and thirteen legacy rating-contract errors. That is the baseline, not a claim that the entire suite was rerun after this small refactor. Current focused and caller checks are listed above.
The 41 JavaScript scripts, 24 Android JVM tests and Android build passed for version 41. This readability pass changes only two Python modules, their tests and documentation; Android/browser assets and the APK are unchanged.

## Risks and next passes

This is the first focused pass, not a claim that every generated file is now easy to maintain. MainActivity.kt, server.py, embedded browser chat logic, market_search.py and some notification/state handlers still contain dense multi-responsibility code. Refactor them incrementally after tracing dynamic imports, bridge callers, transaction ownership and current behavior.

Legacy rating tests/policy require a separate decision; changing formulas/tiers to satisfy obsolete tests is not part of this cleanup.
Connection lifetime/SQLite contention, large-feed query cost and multi-process job coordination remain engineering work, not solved by formatting or comments.
The guide is an entry point, not a substitute for reviewing code and security boundaries. Future changes must keep comments accurate and update the map when ownership/data flow changes.
