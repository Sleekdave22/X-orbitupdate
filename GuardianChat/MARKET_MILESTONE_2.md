# Market milestone 2 — lexical discovery and requested compact cards

Extends foundation `f79e037`; no unrelated routes or app theme assets are changed.

Added `server/market_search.py`, `test_market_search.py`. Modified Market route
delegation, listing search/catalog and existing Market UI to expose persisted
Near Me (same locality), My Country, Worldwide, currency/price and condition filters.
Added tables: `market_discovery`, `market_synonyms`, `market_search_metrics` (reserved
for aggregate performance data, no private query history recorded).

Search normalizes case/diacritics, ignores word order, indexes structured attributes
in its lexical document, expands configured synonyms and tolerates high-similarity
word typos. It never fuzzes numeric/alphanumeric model, year or storage tokens.
Corrections are disclosed with Search original wording; related results are separated
and labelled. Stable paging preserves relevance and price priority for budget intent.
Prices are filtered only within an explicitly selected currency. Worldwide discovery
does not imply shipping availability. Country/locality preferences are account scoped.

17 backend cases passed (search3 + foundation6 + original Market8), including typo
Samsung, reordered storage/colour, handset synonym, numeric safeguards, related-only
results, location isolation, price units/currency, stable 45-item pagination and budget
ranking. Existing browser/native seller routing test passed.

As requested during this work, listing cards now contain only title and the poster's
italic handle at the lower right; details retain photographs, price and actions.
Play/Market upper controls share the same shape, type size and purple background.
Both icons are inside their hit targets. Native badges are rounded and contained
inside those targets instead of wrapping/repositioning buttons with a red rectangle.
The supplied Market SVG is rendered directly and remains unchanged.

The current lexical engine builds a weighted document set from eligible SQLite
listings for each request. This is appropriate for the bounded pilot and is not a
claim of large-catalog capacity. Persistent FTS/caching/performance thresholds should
be measured before scale. No new search cluster is introduced. Multilingual semantic
embeddings require a selected/provisioned model and index; that external dependency
is not present and semantic support is explicitly false in responses. No remote AI
call or model substitution is hidden behind the UI.

Android foundation compilation/assembly and 20 JVM tests passed; the updated matching
home controls are included in the following final packaging verification. Physical
multi-image picker and browser light/dark acceptance remain release checks.
