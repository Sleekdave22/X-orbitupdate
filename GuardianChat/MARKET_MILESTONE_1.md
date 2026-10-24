# Market milestone 1 — foundation

Built on audit checkpoint `782a7c8`. Existing Market is extended in place; existing
legacy advert routes, account IDs, Chat/Play/Vibe/Profile destinations and approved
theme assets remain intact. This milestone is isolated from the live server until
its release is tested and deployed.

Added `server/market_pilot.py` and `server/test_market_pilot.py`; modified
`server/market.py`, `market.html`, `market.js`, `market.css`. Android's existing
WebView document picker now honors multiple image selection (and accepted Vibe
video MIME types) rather than discarding the HTML multiple-selection request.

Additive tables: categories (twelve stable IDs, subcategories and attribute schemas),
seller metadata/restrictions and seller reports, listing metadata/revisions/audit,
listing-bound images and retry keys. Existing adverts retain their IDs and text
prices; no assumed currency or amount is invented for old records.

Authenticated APIs: catalog, listings, listing, image, store, mine; save_listing,
listing_state, report_seller. Backend enforces ownership, revisions, validated image
decoding/normalization, bounded sizes, transactional idempotency, expiry, moderation
and legal owner state transitions. Drafts and their photographs are owner-only.
Published listing details/storefronts are cross-account persistent. Seller identity
is explicitly unverified; reviews are shown as unavailable, never fabricated.

The existing Market page now contains a compact category grid and listing cards,
details, image gallery, storefront, full editor, draft/publish/pause/reactivate/sold/
confirmed removal actions. Existing Shop activation/edit, seller Chat and reports
remain connected. The Market bell uses a real bell and routes listing events to
their listing. Legacy admin moderation updates new metadata coherently.

Verification: 20 backend tests passed (six new foundation tests, eight original
Market tests and six Vibe/activity tests); browser seller-routing regression passed.
An isolated HTTPS seller account opened Browse → details → Edit, saved an edited
title and retained its image/price/attributes; no live user listing was created.
Tests cover two-account visibility, draft/media authorization, money/input validation,
stale revisions, state changes, legacy prices/migration, moderation synchronization
and concurrent create retries. Native multi-picker packaging is checked with the
combined release build; physical selection remains a manual acceptance item.

Next: stronger lexical/location search; saved items, negotiations and targeted
notification history; listing context Chat cards; separately simulated order ledger
and administration. Those are not claimed complete by this foundation milestone.
No real payment provider or semantic embedding infrastructure is enabled.
