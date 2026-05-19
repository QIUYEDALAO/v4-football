# V2 DAILY_POOL Readonly Safety — Closure
Phase: INTEL-OPS-0.2

**0.1 gap**: replay only looped current window checker → misleading SKIPPED_NO_ACTIVE_WINDOW.
**0.2 fix**: historical file/ledger/marker/log scan. 05/17 → DAILY_POOL_FOUND, 05/18 → DAILY_POOL_MISSING.

Safety checker validates both current and historical modes separately.
