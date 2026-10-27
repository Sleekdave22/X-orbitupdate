# Header, Search and saved appearance — version 37

The approved header layout is shared by Chat, Play and Plaza: Back immediately before the title, the navigation menu at the far right, and the existing Play / Chat / Plaza strip at its version 36 coordinates. Chat now has a collapsed Search panel below the strip, matching Plaza's arrangement. The original account search form and handlers remain intact. Conversation search remains available inside individual chats.

Saved account colours and dark/light mode are applied synchronously before stylesheets and page content paint. Android supplies its persisted account palette directly to embedded pages; transparent page backgrounds reveal the already themed native background. No preference request is needed for the first paint. Account changes continue to use account-scoped caches.

## Changes and compatibility

- Updated native header/search presentation, page headers, shared navigation styles and appearance bootstrap.
- Preserved existing routes, forms, captions, authentication, data and GuardianLab protection.
- Kept profile and notification controls. No database migration or backend contract changes.
- Phone contacts, verified phone linking and a Contacts tab remain on hold.
- Original X-Orbit checkout remains clean and unchanged.

## Actual validation

- Android debug build succeeded; 23 JVM tests passed.
- All 38 JavaScript regression scripts passed, including new pre-paint browser/native palette checks, account isolation, HTML script ordering and Search wrapper checks.
- All 70 interface manifest hashes verified; all 53 bundled comparison-web assets match source bytes.
- Browser checks used isolated synthetic accounts: saved Green/Pink colours, collapsed/expanded Chat Search, exact account search, Back, Plaza and Play navigation. Existing form drafts survived search and Back. Header positions and far-right menus were visually checked.
- No live messages, posts or uploads were created. Existing backend regression results from version 36 remain recorded; no backend code changed here.
- Physical S21 first-paint and header confirmation remains pending the user’s manual check.

## Manual check

Reopen X_ORBIT, switch between Chat, Play and Plaza, and confirm the selected appearance is visible immediately. In Chat, open Search below the three module tabs and check Back/menu placement. Search within an individual conversation should still work.

## Deployment

- Implementation commit: 8d05b81a5a66542dfd0bffcbfad13bfcb1163c32; pushed to feature/vibe-timed-navigation in Sleekdave22/X-orbitupdate.
- Both https://localhost:8766/ and https://localhost:8768/ serve the same frozen version 37 source; changed appearance, header and search assets were byte-verified on both.
- Consistent private backup completed before restart. Database integrity passed; all 5 accounts, 12 contact records and 203 messages retained. No active call or stream was interrupted.
- S21 installation completed successfully: versionCode 37, versionName 0.37-header-theme. Authenticated checks confirmed @s21, its saved server, navigation, Vibe, Plaza, match and editor-policy endpoints.
- Deployed browser Chat visually checked with its restored account. S21 visual confirmation remains pending.
