# V4 Dashboard Validation Detail & List Scroll Fix

**Date**: 2026-05-30
**Status**: V4_DASHBOARD_VALIDATION_DETAIL_AND_LIST_SCROLL_FIX_PASS

## Issues Fixed

### 1. Bottom validation detail panel showing "暂无"
The `buildValidationPanel()` function only displayed "累计A+B" as a single combined row, and the fallback chain was insufficient. Fixed by:
- Adding individual rows for 累计A, 累计B, 累计AB
- Enhancing fallback chain to read from `MODEL.cumulative_validation_detail.A/B/AB.display`
- Keeping 昨日A/B/AB rows with proper fallbacks

### 2. Candidate list premature internal scrolling
`.candidate-panel` used `height:auto` which prevented it from filling the grid row. `.candidate-list` used `max-height:100%` without a definite parent height reference, causing the scroll container to be too small. Fixed by:
- `.candidate-panel`: `height:100%` to fill the grid row
- `.candidate-list`: `flex:1; min-height:0; overflow-y:auto` to fill remaining space in panel
- `.side-sticky`: `height:100%` for same-height alignment

## Verification
- 36/36 validation detail & list scroll checks PASS
- 22/22 data binding checks PASS
- All other checkers PASS
- A=1, B=4, SKIP=217 unchanged
