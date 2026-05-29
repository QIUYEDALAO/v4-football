# V4 Dashboard Data Binding Restore

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_DATA_BINDING_RESTORE_PASS

## Root Cause

Commit `d5e11a1` ("v4: make candidate list layout effective at runtime") introduced an extra closing brace `}` at the end of the `toggleBetPanel()` function in `v4_control_center.html`. This caused a JavaScript syntax error (210 `{` vs 211 `}`), preventing the entire script from executing. As a result, `loadModel()` was never called, and the page remained stuck showing "正在读取候选数据…".

## Fix

Removed the extra `}` at line 202 of the JS script block, restoring balanced braces (210 `{` == 210 `}`).

## Verification

- All 22 checks in `check_v4_dashboard_data_binding_runtime.py` PASS
- Underlying data intact: A=1, B=4, SKIP=217, candidates.items=5
- API `/api/v4_control_center_model` returns correct data
- JS syntax valid, `loadModel()` can execute normally

## Preserved

- playbook_script display
- true goal time distribution
- WHITELIST_57 / OUTSIDE_57 split statistics
- No scan rerun, no validation recomputation, no live bet/cron/QQ modification
