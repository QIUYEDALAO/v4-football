# V4 Attribution No-API Guard — Phase Closure

Phase: V4-E.1
Date: 2026-05-19
Status: CLOSED (ready for V4-F)

## Background

V4-E found that `--dry-run` mode in the attribution module would still call `_api_get()`
to fetch live match results, even though file writes were disabled. This meant dry-run
was not truly no-API safe.

## Fix Applied

1. **`--allow-api` flag** (default: false) — required for any API call
2. **`if allow_api:` guard** wraps all `_api_get()` calls
3. **`--dry-run` defaults `allow_api=false`** — no API calls during dry-run
4. **`--validate-only` exits before `run()`** — no API, no writes, no side effects
5. **API-disabled path** marks attribution as UNKNOWN, not HIT/MISS
6. **Guard markers** added: `NO_API_DEFAULT`, `DRY_RUN_NO_API`

## Guard Check Results

| Check | Value |
|-------|-------|
| api_call_found | true (_api_get exists) |
| api_call_guarded_by_allow_api | true |
| dry_run_no_api_safe | true |
| validate_only_no_api_safe | true |
| allow_api_default_false | true |
| verified_write_found | false |
| state_write_found | false |
| qq_send_call_found | false |
| production_verified | false |
| phase_e_allowed | false |

## V4-F Readiness

| Readiness | Value |
|-----------|-------|
| V4-F allowed_to_generate | true |
| V4-F allowed_to_execute | false |

## Modified Files (this phase)

- `engine/v4_result_attribution.py` (added --allow-api, if allow_api guard, API-disabled path)
- `tools/check_v4_attribution_guard.py` (strengthened to check no-API compliance)
- `tools/check_v4_attribution_no_api_guard.py` (new)
- `docs/V4_ATTRIBUTION_GUARD.md` (added Section 5: No-API Guard)
- `docs/V4_ATTRIBUTION_SYSTEM_CLOSURE.md` (updated V4-E to reflect V4-E.1)
- `docs/V4_ATTRIBUTION_NO_API_GUARD_CLOSURE.md` (this file)
