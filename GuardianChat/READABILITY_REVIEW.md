# Human readability review and prioritized plan

Baseline: version 41 implementation eb165a4; deployment record f7fc5ad.
This pass preserves behavior. Bugs, features and ranking-policy decisions stay separate.

## Review findings

- The Android entry point (MainActivity.kt), HTTP handler (server.py), embedded browser chat code (index.html) and several domain modules mix navigation, validation, persistence and presentation. Short physical line counts hide multiple statements and responsibilities.
- Internal Gamebox/Market names remain part of persisted tables and API contracts. Renaming them to match product labels would create compatibility risk and is not a readability shortcut.
- Small modules already provide useful seams: navigation counters, coarse location filtering, private evidence review, media jobs and notification services. Use those seams before splitting controllers.
- Runtime dispatch uses dynamic imports in several places; a text search alone cannot prove a function unused. No removal is proposed in this pass.
- README notes accumulated over multiple prototype versions and contain superseded behavior descriptions. A current developer entry point should clearly distinguish current implementation from historical notes.
- Current baseline is not fully green: 375/388 Python tests pass, with thirteen pre-existing legacy rating-contract errors. The affected readability areas passed before modification. Do not delete failing tests or change ranking math to conceal the mismatch.

## Priority and implementation sequence

1. Record project-wide change rules and a concise current developer guide with feature-to-file/API/table/test mappings.
2. First focused refactor: navigation_state.py. Separate unread, missed-call and Vibe summaries; explain read versus acknowledgment behavior, transactions, privacy filtering and latest-item ordering. Preserve SQL predicates, endpoints, response shape and call expiry side effect.
3. Second focused refactor: market_location.py. Make validation/distance/filtering readable; explain coordinate precision, units, missing-location handling and copy semantics. Preserve ranges, rounding, errors and result order.
4. Verify both changes using the existing HTTP/security/location tests, then focused characterization tests for empty/duplicate acknowledgments, hidden-chat boundaries and input immutability. Run broader callers after refactoring. No visual or dependency changes.
5. Next passes, separately: Plaza lexical search stages and notification worker ownership, then smaller extractions from the HTTP and Android controllers. Understand dynamic callers and add behavior coverage before each extraction.
6. Resolve the legacy/current rating contract in a separate reviewed issue; this is a policy/test compatibility decision, not readability work.

## Boundaries and reporting

No public identifier, route, table, schema, palette, UI placement, file upload, privacy/GuardianLab policy or money behavior changes.
No code removal, broad renaming, new dependency or whole-controller rewrite.
Commit documentation and each focused refactor separately. Record exact checks and gaps; phone UI testing does not establish backend equivalence.

## First pass outcome

Documentation/standards and the two focused refactors are complete. All seven new characterization cases passed before code changes; all 25 focused checks and 118 broader caller checks pass afterward. No SQL predicates, location results or public signatures changed. See READABILITY_VALIDATION.md for exact scope, checks and remaining confusing areas.
