# Market milestone 4 — demo accounting and protected orders

Added `market_demo.py`, `test_market_demo.py`; extended existing Market routes,
offer linkage and UI. New independent tables: `market_demo_orders`, order events,
journals and postings. No gaming `fin_*` row or bank/provider integration is used.

Explicit simulation state machine: CREATED → SECURED → FULFILLING → DELIVERED →
RELEASED, with CANCELLED/REFUNDED/DISPUTED branches. Accepted offers create an order,
buyer demo credits enter hold, seller reports fulfillment/delivery, and only buyer
confirmation releases credits. A reasoned administrator dispute resolution or seller
refund uses the same controlled ledger path. Seller delivery alone cannot release.
Authorizations, revisions and transaction-scoped retry receipts prevent duplicates.

Double-entry journals seal only when balanced; sealed journal/posting updates/deletes
and later posting insertion are rejected by SQLite triggers. Available balance checks
and holds occur within BEGIN IMMEDIATE. These are application/database invariants,
not a claim that a database administrator cannot alter the database schema.

APIs: demo_wallet, demo_orders, demo_order; demo_deposit, demo_withdraw,
demo_order_create, demo_order_action. All responses and screens identify simulation;
funds are unspendable. Wallet shows per-currency available, held, pending sales and
receipt/history details. Order event notifications remain Market scoped. A deferred
provider interface names initiation/confirmation/hold/release/settlement/refund/
dispute/webhook/reconciliation; every real operation is disabled. No CypherX calls.

Four new financial integration/concurrency tests pass after correcting a test-helper
argument name collision. They verify full delivery/buyer release, balanced journals,
unchanged gaming wallet rows, duplicate deposits, concurrent hold attempts, insufficient
funds, immutable postings, private order access and audited dispute refund. The earlier
combined run passed its 17 existing wallet and five connection cases; final regression
re-runs all together with the corrected helper. No real account was funded in QA.

Native packaging and complete synthetic seller/buyer UI acceptance follow the admin
milestone. Physical multi-image selection and Market background push remain unverified.
