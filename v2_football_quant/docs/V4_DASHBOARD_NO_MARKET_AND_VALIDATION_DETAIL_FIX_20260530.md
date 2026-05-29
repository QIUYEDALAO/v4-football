# V4 Dashboard No-Market Exclusion & Validation Detail Fix

**Date**: 2026-05-30
**Status**: V4_DASHBOARD_NO_MARKET_AND_VALIDATION_DETAIL_FIX_PASS

## Issues Fixed

### 1. Bottom validation detail "暂无"
The `buildValidationPanel()` function used optional chaining (`?.`) which may not be supported in all runtime environments. Replaced with explicit null checks and string concatenation instead of template literals for maximum compatibility. Enhanced fallback chain to read from `MODEL.cumulative_validation_detail`.

### 2. Undefined values in betting form
`first(x.default_odds, '')` returned `undefined` because `first()` treats empty string as an invalid value. Changed to `safe(x.default_odds, '')` which correctly returns empty string for null/undefined inputs.

### 3. No-market exclusion
Added ability to manually mark candidates without available betting markets:
- New "无盘口排除" button in expanded bet form
- `markNoMarket()` function posts to `/api/v4_live_bet/no_market`
- Server writes `v4_no_market_exclusions_YYYYMMDD.jsonl`
- Model builder loads exclusions and marks candidates with `no_market_excluded=true`
- Excluded candidates do not count toward pending bets
- Excluded candidates do not enter validation or statistics
- Original candidate/scout records are preserved

## Verification
- 35/35 no-market & validation detail checks PASS
- 22/22 data binding checks PASS
- 36/36 validation detail & list scroll checks PASS
- All other checkers PASS
