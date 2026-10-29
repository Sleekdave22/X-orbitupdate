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

## Additional authorized handoffs and settings correction

The user added the Vibe reaction/engagement handoff and the consolidated messaging
handoff, plus section-owned settings corrections. These extend the approved scope;
they do not cancel the ecosystem work above or authorize moving unrelated controls.

- Fix existing settings: half-width panels above navigation; Play/Plaza stay in
  their own modules. Reuse account appearance and existing section tools.
- Fix Vibe reactions reaching private conversations, backend acceptance before UI
  success, offline persistence and request consent. Normalize the display label to
  “Reply to Vibe”, smaller/italic while keeping the existing arrow. Emoji-only
  text becomes 150% size without changing stored messages.
- Complete nonintrusive delivery/connection feedback and sticky local-date
  dividers in private/group history; do not suppress real failures or retry state.
- Reuse existing personal chat pins; add shared message pins with permissions and
  safe previews. Expand existing message requests with previews, Accept, Decline,
  Decline & Block and Report; preserve accepted history and no pending read receipts.
- Add group creation/messaging, attachments/replies, membership/admin succession,
  configurable sending/detail/pin permissions, notifications and protected access.
- Add persistent Plaza reactions across four listing types. Build Show Off first
  before connecting its reactions/comments; comments default ON, can be disabled
  by owner/moderator, and old comments remain when disabled.

Native/browser checks must be reported separately from physical S21 checks. A
working capture/editor or WebView does not establish cross-device acceptance of
new messaging/group features. No phone-contact linking or SMS work is resumed.
