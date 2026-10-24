# Phone and browser interface alignment

## Cause and selected design

The X-orbitupdate `orbit-market` browser preview served its older oxblood interface while the installed Android version 25 retained the newer purple, navy and cyan interface. Both already used the current shared X-Orbit backend. This change aligns the browser with that installed phone design rather than reinstalling an older Android interface.

The web interface snapshot comes from `Sleekdave22/X-Orbit` commit `bf029cea24983f58022736cb44bbb8c2e18d73ff`, the source used for installed Android version `0.25-x-orbit-market`. Its typography, wallpapers, light/dark icons, navigation, chat composer, message styling, personalisation, OrbitPlay and Market integration are retained together. `server/phone-interface-manifest.json` records all 47 copied runtime assets and font licences with SHA-256 hashes so that partial copies can be detected.

## Scope and compatibility

All changes are isolated to the X-orbitupdate branch `style/phone-purple-parity`, based on `orbit-market`. Neither repository's default branch is changed. The source X-Orbit repository remains at its existing commit with a clean working tree. Its Android installation, backend process, database, accounts, messages, wallet records, matches and Market adverts are unchanged by this alignment.

This is a web interface snapshot, not a replacement Android build or backend migration. The browser continues to use the existing shared backend, including its newer authenticated preferences, social, scheduling, wallet, invitation, streaming and competition contracts. Running these web files against the older backend bundled on the original `orbit-market` branch is not a substitute for that configured shared backend and has not been validated here. Internal table names, endpoints, authentication and GuardianLab security are not rewritten.

The local shared preview serves these updated web assets from this checkout, with its existing same-origin forwarding to the current backend. No account reset or data migration is needed for this interface alignment, and the shared backend was not restarted.

## Verification on 24 October 2026

- All 25 browser regression scripts pass. `test_profile_presentation.js` runs from the GuardianChat directory as its header requires; the other scripts run from the server directory.
- All 47 manifest entries match the selected phone-source snapshot exactly.
- All 44 publicly served interface assets match byte-for-byte between the browser preview and the phone's backend, allowing only the preview's existing one-time session-migration script in the home HTML. The two font licence files and unused compatibility script are local assets rather than public routes.
- Authenticated profile, contacts, match and gaming summaries match through the shared preview; invalid sessions remain rejected.
- Browser home and OrbitPlay were opened and visually checked: purple actions, navy surfaces, cyan headings, current icons and wallpaper are present. Market Browse/My shop were also checked without changing live shop or advert data.
- The installed S21 app was left unchanged; version 25 and Market navigation were verified in the preceding deployment. No new physical-phone installation or device UI check was needed for this browser-only alignment.

## Manual check

Open the shared browser preview, refresh an older tab and check Chats, Calls, OrbitPlay and Market. The layout adapts to the browser width while using the same approved palette and artwork as the phone. Existing account personalisation remains in force; this change does not force a new account preference.
