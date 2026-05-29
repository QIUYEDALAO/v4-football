# V4 Dashboard Layout / Validation / Sort Fix

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_LAYOUT_VALIDATION_SORT_FIX_PASS

## Issues Fixed

### 1. Sort order
`sortCandidates()` sorted by grade first, then time. This put all A-grade candidates before B-grade regardless of kickoff time. Fixed to sort by kickoff time ascending first, then by grade within the same time slot.

### 2. Left-right panel alignment
After removing fixed 440px heights in the spacing fix, the left candidate panel and right "待办与实盘快照" panel were no longer aligned. Fixed by:
- `align-items:stretch` on `.primary-layout` grid
- `align-self:stretch` on `.side-sticky`
- `min-height:0` + `overflow:hidden` on `.candidate-panel`
- `overflow-y:auto` + `max-height:100%` on `.candidate-list`

### 3. Validation data
Enhanced `renderTop()` fallback chain to read from `MODEL.cumulative_validation_detail` and `MODEL.yesterday_validation_detail` when `top_status` fields are empty. Added KPI hint showing A|B breakdown below cumulative display.

## Verification
- 28/28 layout/validation/sort checks PASS
- 22/22 data binding checks PASS
- All other checkers PASS
- A=1, B=4, SKIP=217 unchanged
- playbook_script and true goal distribution preserved
