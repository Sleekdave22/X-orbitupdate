# Ecosystem implementation checkpoints

The user authorized the audited handoff on 28 October 2026. The integrated
X-orbitupdate feature branch remains authoritative; the original X-Orbit checkout,
live database, GuardianLab and existing unrelated features are protected.

1. Harden private results: enforce new 3–10 second evidence captures, sample short
   clips proportionally, retain compatibility with already-submitted recordings,
   show independent reviewers structured findings, and protect appeal evidence.
   Keep the existing three-day retention default; an open appeal pauses cleanup.
2. Add durable, authorized media references and explicit per-post Social/Business
   classification and destinations. Preserve legacy media and independent expiry.
3. Build Show Off with 24-hour eligibility, Following/For You filters and existing
   account, messaging, listing and universal-follow services.
4. Extend top navigation to Play / Chat / Show Off / Plaza. Preserve Chat's bottom
   bar and existing gestures; report any unavoidable handler replacement first.
   Implement independent directly typeable searches and committed-entry intros.
5. Add opt-in followed-publication alerts, cross-post deduplication, performance
   checks and controlled rollout. Phone-contact integration remains on hold.

Each checkpoint requires a focused commit, developer-guide updates and recorded
tests. Synthetic OCR tests must never be described as measured recognition
accuracy. Existing 13 obsolete test_rating.py errors remain visible. Do not deploy
an incomplete checkpoint or enable paid services/real money. Introduction-screen
draft changes predating this plan are separate and must not enter result commits.

Rollback: disable new feature entry points while retaining additive records. Do
not restore an old database over intervening user activity. Review source and
schema compatibility before deployment; use isolated test data throughout.
