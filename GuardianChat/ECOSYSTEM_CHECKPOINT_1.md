# Checkpoint 1 — private result evidence and appeal holds

Authorized by the user's 28 October 2026 instruction to implement the audited
ecosystem handoff. This checkpoint changes result evidence only. Show Off, shared
public media and four-module navigation remain later checkpoints.

## Implemented

- New camera evidence stops at 10 seconds; server validation accepts 3–10 seconds
  and at most 20 MB. Ordinary Vibe capture/export limits are unchanged.
- Real MP4 and phone WebM decoding measures timestamps, checks dimensions and
  bounds, and selects proportional first/middle/final frames. Previously accepted
  12–60 second recordings remain reviewable; new uploads cannot use that bypass.
- Independent authorized reviewers can read a structured private summary of
  original reports, automated findings, policy, escalation reason, decision actor,
  appeals and audit records. Existing authorized private media viewers remain.
- Participants can file an appeal within the frozen match retention window
  (normally three days). Exact retries are idempotent. The original reason stays
  immutable, and neither participant gains access to the other's proof.
- An open appeal or required correction protects the evidence from cleanup.
  Finalized due unheld evidence and raw OCR text expire; score/reason/policy,
  submission digest and decision/audit records remain.
- An independent reviewer may uphold the result or flag an audited correction.
  Scores, standings and ratings are never silently overwritten by an appeal.

## Data and contracts

Additive tables: `result_evidence_retention`, `result_evidence_appeals`.
New authenticated contracts: GET `/gamebox/review-summary?room=...`, POST
`/gamebox/evidence_appeal`, POST `/gamebox/evidence_appeal_decide`.
Existing `result-state` gains safe appeal receipt fields. Existing routes, match
IDs, result reports, ranking awards and private evidence tables remain compatible.

## Actual verification

- Before edits: 28 result-review/current-rating tests passed; existing evidence
  camera browser script passed. Initial environment permission failures were
  resolved before recording the passing baseline.
- Broad Python run during implementation: 404 tests in 583.372 seconds, 391 passed
  and the same 13 obsolete `test_rating.py` contract errors remained. No new errors.
- Final focused run after cleanup/sample refinements: 71 tests passed in 167.074
  seconds across result reviews, hardening, active ratings, Gamebox and fixtures.
- The subsequently added fixture-specific appeal/cleanup test passed separately
  (1 test, 2.203 seconds). Current hardening file contains 11 new tests in total.
- All 43 JavaScript regression scripts passed, including new appeal UI, capture
  limits, duplicate-click handling and text-only rendering of untrusted OCR.
- `git diff --check` passed.

The broad run predates the final two added cases/refinements; those affected paths
were verified by the final focused run and separate fixture test. No fresh Android
APK/device check, human-labeled OCR accuracy study or live deployment was performed.
Test data was isolated; the original repository and live account data were untouched.

## Limits and next work

This remains conservative local OCR/selected-frame consistency, not authenticated
publisher results or general manipulation detection. Unsupported/unclear captures
continue to escalate. A score correction requires a separate audited reversal and
recalculation workflow; `correction_required` keeps proof rather than pretending
that such a workflow already exists. Older final results are not retroactively
assigned a new appeal window. Unresolved cases intentionally retain proof pending
review and require operational monitoring to prevent an indefinite backlog.

Next: shared authorized public-media references, per-post classification and
explicit cross-post destinations, followed by Show Off. Earlier introduction and
navigation drafts are preserved separately and excluded from this checkpoint.

## Rollback

Disable new appeal actions/routes in a coordinated client/server rollback. Keep
the additive tables and any open hold records; do not roll back to cleanup that
ignores them. Do not overwrite the live database with an older backup. Deployment
must include the backend and matching JS as one tested snapshot.
