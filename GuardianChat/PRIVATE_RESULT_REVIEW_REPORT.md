# Private result review and camera controls

24 October 2026 — `feature/private-result-review`, X-orbitupdate.

## Scope and preserved release

This branch extends the complete X-Orbit release at
`bf029cea24983f58022736cb44bbb8c2e18d73ff`. It preserves the approved purple/navy/cyan
interface, artwork, Android application identity, accounts and GuardianLab features.
The original X-Orbit checkout and its remote branches are not changed. The shared
local backend is deployed from this branch against the existing data directory;
the browser preview continues to use that same backend. Neither default branch is merged.

## Implemented behavior

- Participants submit private camera captures. Opponents receive receipt/status
  metadata, not originals, OCR text or each other's proposed scores during review.
- Photo/video modes have tap photo, hold video, swipe up to lock, stop, camera flip
  and an unsent local preview. There is no evidence gallery/file input. The phone
  camera films the external PC/TV; evidence capture does not record the phone screen.
- Each original is immutable. Identical retries are idempotent; changed replacements
  and reused evidence from another player/match are rejected. Submission controls
  disappear once accepted for the current stage.
- Both submissions queue review after 60 seconds; maintenance checks every 30 seconds.
  The first submission starts a durable 15-minute response window. Only validated
  evidence can determine a one-sided result after that deadline.
- Unreadable/conflicting photos request video showing navigation, both gaming IDs
  and final details. The first video starts a new 15-minute response window.
  Unresolved video goes to an independent authorized reviewer. Silence alone is
  never enough to accept invalid/unreadable evidence.
- Finalization uses existing authoritative match/fixture paths and transactions.
  Ranked open matches update ratings once; competition fixtures update their
  existing standings/brackets policy. Knockout draws need independent adjudication.
- Livestream controls enumerate physical and virtual cameras without name filtering,
  select a separate microphone or no audio, and offer 480p/720p/1080p preferences.
  Start a virtual camera in its own application before selecting it. Requested
  resolution is a device/browser preference, not a guarantee.
- Android WebView requests camera and microphone permissions only when required,
  for the authorized current HTTPS origin. App version: 26 / `0.26-private-result-review`.

## Architecture, data and contracts

Additive tables: `result_review_jobs`, `result_review_uploads`, `result_review_videos`.
Existing photo tables are retained. Originals from before this policy are marked
legacy and cannot be automatically awarded. Jobs and fixed identity aliases survive
restart. Leases, transactional rechecks and existing award uniqueness prevent
concurrent workers/manual decisions from awarding twice.

Existing evidence endpoints accept `capture_mode: "camera"`, base64 `image`, optional
video `mime`, and the assigned match/room/fixture identifier. Maximum photo: 5 MiB,
24 megapixels, PNG/JPEG. Maximum video: 20 MiB, 1080p, MP4/WebM; record 12–60 seconds
for automatic sampling. Decoding runs in a bounded subprocess. Video is silent.

`/gamebox/result-state`, summaries and studio add `evidence_review` receipt/status
metadata. Final state includes authoritative `final_score`. Existing personal result
comments remain. Old peer evidence signaling rejects with instructions to reopen.
Raw photo endpoints and `/gamebox/review-video?room=…&player=…` require an independent
authorized administrator; participants cannot review their own match even if admin.
Manual decisions require both captures or expiry of the response window with one
capture, and a documented reason. Raw video retention follows the existing match
retention policy after finalization; unresolved evidence is retained for review.

Local RapidOCR reads images; PyAV (`av>=16,<17`) decodes video. No cloud model,
publisher API or real-money operation is introduced. OCR inference is off the HTTP
loop. Readers cannot consume a substituted client OCR answer.

## Verification

- 64 grouped backend tests passed: 18 new review tests plus gaming, Market,
  stream directories, account preferences, message notifications and key match flows.
- 48 additional match-core/server tests passed, including protected media, account
  isolation, calls/history and competition advancement. Two key match cases overlap
  the grouped run. One additional legacy-evidence timeout regression passed.
- All 28 browser test scripts passed, including capture gestures/cleanup, arbitrary
  virtual-camera selection, relay integration, immutable upload UI and existing chat.
- All 20 Android JVM tests passed and debug APK assembled successfully before final
  web-asset activation; final incremental packaging is checked during deployment.
- Offline OCR smoke test read a generated supported final score correctly. Real
  PyAV decoding accepted a generated 12-second clip and sampled three frames.
- An isolated HTTPS synthetic account/match was used to inspect result controls and
  broadcast source choices. No live user evidence or test chat message was submitted.

## Limits and manual acceptance

This is conservative OCR plus rules, not proof that a screenshot/video is authentic.
Automatic extraction currently recognizes clear English final-result layouts for
`efootball` and `fc_mobile`; unsupported/ambiguous layouts defer to video or a human.
Video rules require consistent sampled IDs/scores and navigation text, but cannot
prove that footage is genuine. The camera-only interface and `capture_mode` flag
are not cryptographic hardware attestation. An independent moderator is required
when automatic review cannot decide; no account is promoted automatically.

No production-readiness claim is made. Before a wider launch, test real game screens,
camera focus/reflections, adversarial footage, browser virtual-camera compatibility,
phone gestures and review capacity. Capture permission cancellation and microphone
denial must show feedback without starting a stream.

Manual phone check: open a disputed match → result chat → camera; take an unsent
photo, switch to video, hold and swipe up to lock, stop, inspect preview, then discard.
For a PC broadcast: start the virtual camera application → Live matches → broadcast
controls → Find cameras → select the camera/audio → Start live camera. Verify from
a second viewer before considering real virtual-camera streaming accepted.
