# Vibe viewer and transparent-icon update — version 29

25 October 2026. Main project: `Sleekdave22/X-orbitupdate`, branch
`feature/market-pilot-foundation`. Original `Sleekdave22/X-Orbit` is unchanged.

## Account diagnosis

`Owner @e8847db091d1` exists in the isolated `vibe-qa-1792862268` test database,
not in the shared live database containing @s21. It cannot add an account from a
different database. No demo account, credential or contact was copied to live data.
The existing browser session on 8768 was Mainfirst (@sleekdavemain). Both 8766 and
8768 use the shared backend. Exact-account public profile controls now expose the
existing Add to chats contract; message requests remain a separate option. Block
checks remain enforced on the backend.

## Delivered behavior

- Compact Vibes heading with the supplied SVG. Own profile and latest public-post
  thumbnail appear first, followed by a divider and contact preview/name rows.
  The former cards, separate chat buttons and visible “unviewed” wording are gone.
  Segmented rings retain the distinction between new and already-opened posts.
- Public preview thumbnails are authenticated and do not create view receipts.
  Clicking opens a full-screen viewer. The backend view is recorded after image
  load or video loaded-data, with generation/visibility guards. Navigation between
  uploads and Back/Close remain available, with independent expiry enforcement.
- Emoji reactions sit at the lower left above an inline private-reply composer.
  Sending stays in the viewer. The existing chat receives a server-labelled
  “Reply to your Vibe” or “Reply to your Private Vibe” message. Author-only viewer
  identities/times/reactions open through the eye control at the lower right.
- The protected native Private Vibe viewer also has inline replies and reactions.
  GuardianLab shielding, screenshot restrictions, expiry/block checks and camera
  monitoring remain in place. Private thumbnails are deliberately not exposed in
  the unprotected browser/feed. No private media is copied into a chat reply.
- Added `/vibe/preview` and `/vibe/reply`; additive `vibe_replies` associates a normal
  chat message with its originating post. Replies require existing contact access,
  reject blocked/unauthorized/expired/self targets, and use atomic idempotency keys.
  Retry after successful delivery returns the original message; changed retry
  contents are rejected. Existing messaging push dispatch is reused.
- Transparent artwork is used for Play, web entry/intro and native launch/app icon.
  Original supplied raster files remain intact. Android splash configuration removes
  the icon backing; upper Play/Market geometry and unrelated themes are preserved.

## Files and assets

Changed the Vibe HTML/CSS/JS/backend, shared route dispatch, exact-account profile
action, native MainActivity protected viewer, manifest/theme/icon configuration,
asset policy, package version, web asset hashes and affected navigation test.

New project assets: `server/branding/orbit-icon-plain.png` and
`chat/src/main/res/drawable-nodpi/orbit_plain.png`. They are identical transparent
RGBA copies produced with the built-in image-generation skill/tool, not an API-key
fallback. Original PNGs were preserved. The final extraction prompt was:

> Make a clean transparent cutout of ONLY the colorful foreground logo in this
> reference, with exact icon structure and original two oval rings, speech bubble,
> and trophy. Reconstruct clean vector-style smooth filled surfaces rather than
> noisy photographic masking. Entire empty background and all negative spaces are
> fully transparent, zero isolated pixels. Purple-magenta-cyan-blue gradient
> foreground. No rounded square, black or white background, no glow or shadows.
> Preserve exact arrangement and proportions. Crisp professional tiny app navigation
> icon. Square 1024 image, logo centered with 10% empty transparent margin.

## Validation and limits

- 30 focused Vibe/social backend tests passed. A broader 57-case Vibe/chat/social
  run passed 56 cases and hit one five-second receipt timeout under build load;
  that unchanged receipt test passed when rerun separately. No code change was used
  to hide the timeout. New cases cover previews without views, private media denial,
  labelled replies, expiry, block/contact/audience access and concurrent deduplication.
- All 31 browser test scripts passed, including new interaction tests for display-
  before-view, compact contact filtering, in-viewer send/retry and Back. These are
  scripted DOM tests, not a claim of physical-device visual acceptance.
- Android compilation succeeded; all 20 JVM tests passed after directing temporary
  files to the permitted test directory. Initial temporary-directory permission
  failures were environmental and were not application assertions.
- Transparent alpha and the 63 web manifest entries were checked. Final packaged
  asset parity and live deployment results are recorded below when completed.
- An isolated HTTPS review server was prepared with synthetic contacts and posts.
  Browser automation disconnected during sign-in, so the full-screen layout and
  keyboard behavior still require browser/S21 visual acceptance. No synthetic
  posts or messages were sent through the live accounts.

## Deployment

Pending final frozen-package deployment and S21 installation verification.
