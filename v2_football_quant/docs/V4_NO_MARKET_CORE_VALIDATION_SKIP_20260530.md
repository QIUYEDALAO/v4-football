# V4 NO_MARKET Core Validation Skip — 2026-05-30

## Problem

NO_MARKET exclusions (e.g., "无盘口已排除") were only filtered at the
dashboard model layer, not at the validator core. The validation pipeline
still fetched HT results for excluded fixtures from the API and could
count them in statistics.

Additionally, repeated dashboard clicks on "无盘口已排除" appended
duplicate records to the marker file, inflating `no_market_excluded_count`.

## Fixes

### 1. NO_MARKET marker idempotency (`tools/serve_live_bet_tracker.py`)

`_append_no_market_exclusion` now checks for existing (date, fixture_id)
records before appending. Repeated clicks return `already_excluded`
instead of appending another duplicate.

### 2. Deduplicated loader (`tools/build_v4_control_center_model.py`)

`_load_no_market_exclusions_for_date` deduplicates by (date, fixture_id)
key, keeping only the first record. `no_market_excluded_count` uses
`len(deduped_list)`, eliminating phantom inflation from raw duplicates.

### 3. Validator core skip (`engine/v4_ht_result_validator.py`)

Added `_load_no_market_excluded_fixtures()` which loads all no-market
exclusions across all dates into a cross-date fixture_id set.

Before any date/grade filtering or API calls, fixtures in the NO_MARKET
set are skipped:
- No API call to fetch HT result
- No entry in win/loss/missed/pending
- No entry in A/B/AB statistical denominators
- Only recorded as `no_market_excluded_count` and `no_market_excluded_fixtures`

### 4. Statistics aggregation

The validator output now includes `no_market_excluded_count` and
`no_market_excluded_fixtures` alongside the standard funnel metrics.

## Files Changed

- `engine/data_sources/h2h_engine.py` — no changes
- `engine/v4_ht_result_validator.py` — add NO_MARKET filter at core level
- `tools/build_v4_control_center_model.py` — dedup loader
- `tools/serve_live_bet_tracker.py` — idempotent marker write
- `tools/check_v4_no_market_core_validation_skip.py` — new checker

## Verification

- 1418141: 3 raw marker records → 1 deduplicated exclusion
- no_market_excluded_count: 3 → 1
- Validator loader finds 1418141 in excluded set
- Dashboard model still shows no_market_excluded=True
- Candidate/playbook/distribution intact
- DEFAULT_RULES unchanged (b04f3da9b770)
- Validation history untouched
- Live bet records untouched

## Commit

`v4: skip no-market fixtures in validation core`
