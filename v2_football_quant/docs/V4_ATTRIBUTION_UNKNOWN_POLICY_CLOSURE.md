# V4 Attribution UNKNOWN Policy — Phase Closure

Phase: V4-E.2
Date: 2026-05-19
Status: CLOSED

## Background

V4-E.1 fixed the API guard: `--dry-run` no longer calls API. However,
`allow_api=false` set `ht_goal=False` which caused the downstream `_model_result()`
to generate `MODEL_MISS` for A/B grades.

## Problem

- `ht_goal=False` was defaulted (no-API = no goal) rather than "unknown"
- `_model_result(pre_grade, ht_goal=False)` returned `MODEL_MISS` for A/B/C grades
- `_diagnosis(ht_goal=False)` generated `MODEL_OVERCONFIDENT` for A/B/C
- `_root_cause(ht_goal=False)` computed misleading root causes
- `attribution_status` could be generated as HIT/MISS incorrectly

## Fix Applied

1. **API-disabled path now skips all HIT/MISS computation**:
   - Builds row directly with `continue` before `_model_result` / `_diagnosis` / `_root_cause`
   - Sets `model_result = "MODEL_RESULT_UNKNOWN"`
   - Sets `diagnosis = "RESULT_UNKNOWN_API_DISABLED"`
   - Sets `attribution_status = "UNKNOWN"`
   - Sets `failure_category = "unknown_result"`
   - Sets `ht_goal_observed = "unknown"`
   - Sets `result_known = False`

2. **All downstream scoring skipped** via `continue`:
   - No `_model_result()` call
   - No `_diagnosis()` call
   - No `_root_cause()` call
   - No `_variance_dimension()` call
   - No `bucket_hit` calculation

3. **Full API path unchanged** — `allow_api=True` provides full attribution

## Verification

| Check | Value |
|-------|-------|
| dry-run rows with MODEL_RESULT_UNKNOWN | 5/5 (100%) |
| HIT/MISS in dry-run | 0 |
| API-disabled path calls _model_result | false |
| API-disabled path calls _diagnosis | false |
| API-disabled path calls _root_cause | false |
| api_disabled_unknown_policy_found | true |

## Modified Files (this phase)

- `engine/v4_result_attribution.py` (API-disabled continue path + MODEL_RESULT_UNKNOWN)
- `tools/check_v4_attribution_guard.py` (added api_disabled_no_model_result checks)
- `tools/check_v4_attribution_no_api_guard.py` (added UNKNOWN policy checks)
- `docs/V4_ATTRIBUTION_GUARD.md` (already covered in V4-E.1)
- `docs/V4_ATTRIBUTION_SYSTEM_CLOSURE.md` (updated)
- `docs/V4_ATTRIBUTION_NO_API_GUARD_CLOSURE.md` (already covered)
- `docs/V4_ATTRIBUTION_UNKNOWN_POLICY_CLOSURE.md` (this file)

## V4-F Readiness

| Readiness | Value |
|-----------|-------|
| V4-F allowed_to_generate | true |
| V4-F allowed_to_execute | false |
| production_verified | false |
| phase_e_allowed | false |
