# Unified Vibe — Stage A audit and integration plan

25 October 2026. User-selected main project: `Sleekdave22/X-orbitupdate`.
Inspected before feature implementation; the pasted handoff's generic X-Orbit name
does not replace the explicitly selected Marketplace repository.

## Repository and baseline

- Remote default `main`: `3b1209ef0ffc554981f3e8035a444a39d6014a37`.
- Remote `orbit-market`: `55ab5e6c010749a79941973bbbb47bb682aadbaf`.
- Tested starting commit: `c754f7fcb938c29a14d26b6da83ee82ecd9fd9b2` on new
  `feature/unified-vibe-sharing`, extending the pushed Market/Vibe release branch.
- Running frozen implementation: `d98469b3847f45a0b6ca7760b843e89cd4f0ae62`,
  Android version 30. Browser 8766/8768 shares the original account database.
- Original `Sleekdave22/X-Orbit` remains excluded and unchanged. No main merge.
- Baseline: 25 Vibe/viewer, Market listing and sponsored-league backend cases passed;
  all 31 browser scripts passed; Android assemble and all 20 JVM cases passed.
  An initial runner used a nonexistent sponsored test class; the correct eight-case
  class passed. This was a runner-selection error, not an application failure.

## Actual reusable implementation

| Area | Existing implementation | Reuse / missing work |
|---|---|---|
| Identity/auth | `users`, bearer sessions, shared web/native account | Reuse UID and author linkage; no additional account or login |
| Vibe | `vibes.py`, `vibe_items/settings/audience/views/reactions/replies`; authenticated media and previews; individual expiry; protected native Private viewer | Extend this system with stable source references, not a second feed/storage implementation |
| Private audience | Explicit frozen list of existing contacts; publish rejects empty or unauthorized audience | Reuse for personal and linked shares; improve chooser visibility without broadening access |
| Viewer/replies | Full-screen public viewer, protected native viewer, inline emoji/private replies; idempotent messages labelled as Vibe replies | Add minimal source actions, shared Follow and validated return context |
| Market | Existing structured and legacy listings, ordered `market_images`, states/revision, validated listing access, expiry and seller restriction checks | Resolve primary photo/current product details dynamically; source-owned publication prompt; no image re-upload |
| Seller chat | `market_connections` inquiry and product context; consent/message requests; existing conversations | Reuse inquiry and authorized chat routes. Sharing must not auto-add contacts or send unsolicited messages |
| Following | `social_follows`, public/private requests, blocks and existing notifications | Reuse across every Vibe type, native and browser |
| Gaming profiles/ranks | Immutable UID/game ownership, `gb_game_ids` and `gb_identity_meta`; privacy, claims and commitment locks; versioned Elo/placement history | Share read-only authorized profile references. Label verification honestly; do not change identity/ranking rules |
| Trophies | Legacy `leagues.champion` with finished state/confirmed fixtures; sponsored completed/archived league standings and final snapshot | Reuse permanent competition records; only verified terminal outcomes qualify; reflect changed/withdrawn outcomes on read |
| Rank milestones | Existing verified `gb_rank_history/awards`; no reusable milestone achievement records found | Add only source-linked milestone recognition/configuration, deduped per player/game/threshold; no duplicate trophy database |
| Result corrections | No separate finalized-result reversal/recalculation API found in this checkout | Do not build an unrelated correction engine; revalidate original state/winner/score references so withdrawn or corrected sources cannot retain misleading representations |
| Navigation | Existing four bottom tabs, native WebView bridges, seller/profile handlers | Keep positions/destinations; add localized account-scoped return metadata and validate every source destination |

## Styling preservation and requested exceptions

Observed the running browser before editing. It uses Orbit Inter/Orbit Sora and
the approved violet/navy/cyan theme, supplied SVGs, 56×56 preview circles, 72px
preview rows and 54px bottom tab buttons. The four tabs are Vibe, Chat, Calls,
Profile. Existing Play/Market entries and wallpapers stay in place.

Only the explicitly requested exceptions move/change existing controls: Vibe settings
becomes a top-right icon; active upload count becomes a red circle at the preview's
lower right; the preview uses the newest active upload. Same-second uploads currently
sort by random ID, so ordering needs an insertion-order tie-breaker. Own thumbnail
and count share a corner today; use the latest post as the circle preview and reserve
the corner for the count. Empty own Vibe retains the profile fallback.

No new palettes, typography, icon library, navigation tabs or generic card redesign.
Take after measurements/screens to compare unchanged circles, rows and bottom tabs.

## Expiry / privacy conflict resolved before implementation

The handoff specifies 24 hours, while existing personal Vibes support independently
selected 12/24/48 hours. Preserve those functioning personal preferences. New linked
Market/gaming shares expire after 24 hours, independently of their source record.
Require explicit Public/Private selection before publication; Private requires a
selected contact list. Neither option can bypass original listing/profile access.
Private media/thumbnail protection remains enforced outside GuardianLab's viewer.

## Additive architecture / contracts

- Add a registry of source adapters for listing, gaming profile, competition trophy
  and verified rank milestone. Each stores stable references and validates the
  authenticated publisher/reader against its original service on every read.
- Extend existing `/vibe/*` with source publication/options, source navigation,
  shareable recognition prompts and controlled sharing-policy routes. Keep personal
  upload, reactions, views, reply and expiration contracts compatible.
- Store source links, request deduplication and explicit prompt acknowledgements
  additively. Render linked cards from existing media/details; never duplicate
  product uploads or replace authoritative achievement/financial/result records.
- Persist only validated Vibe return IDs/visibility bound to the current account.
  Restore after listing/profile/chat navigation and restart; show expiry/unavailable
  feedback when restoration is no longer authorized.
- Recheck source status on viewing and while open. Sold/unavailable/restricted
  products and withdrawn/overturned achievements cannot masquerade as current offers
  or verified accomplishments. Deleting/expiring a Vibe never deletes its source.

## Implementation sequence and acceptance

1. **B:** shared source infrastructure, current-preview count/settings enhancements,
   transaction/idempotency/privacy tests. Commit and report.
2. **C:** optional Market publication prompt and retained own-listing action;
   primary-photo/text fallback, public/private chooser, seller inquiry/context and
   product navigation. Test listing→share→viewer→listing/chat→return.
3. **D:** manual gaming profile sharing, terminal verified trophy sources and
   configurable verified ranking milestones; meaningful opt-in prompts only.
4. **E:** existing shared Follow state and account-scoped web/native return context,
   preserving all current navigation. Test pending/accepted/self/blocked cases.
5. **F:** expiration, source edits/removal/restriction/correction, concurrent retries,
   missing images, restart and private-audience boundaries.
6. **G/H:** full scripted integration/regression/build, before/after layout inspection,
   frozen deployment, physical acceptance where available and final report.

The user authorized the coordinated assignment to continue through these stages;
no new approval gate is inferred. A stage report must distinguish actual execution
from pending checks. The physical S21 connection is currently unavailable; version
30 was installed/migrated earlier, but new physical acceptance is not assumed.
