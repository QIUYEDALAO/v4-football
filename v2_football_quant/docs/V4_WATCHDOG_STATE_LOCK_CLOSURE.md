# V4 Watchdog / State / Lock — Phase Closure

Phase: V4-D
Date: 2026-05-19
Status: CLOSED (ready for V4-E)

## Scope

This phase established V4 watchdog, state, lock, timeout, and fail-closed boundaries.

## Contract Status

| Contract | Status |
|----------|--------|
| Watchdog contract | ✅ ESTABLISHED |
| State lifecycle contract | ✅ ESTABLISHED |
| Lock contract | ✅ ESTABLISHED |
| Timeout contract | ✅ ESTABLISHED |
| No AI kill/retry | ✅ LOCKED |
| Stale lock report-only | ✅ LOCKED |
| Route depends on watchdog | ✅ LOCKED |
| Sent depends on watchdog | ✅ LOCKED |

## Production Guards

| Guard | Value |
|-------|-------|
| `production_verified` | **false** (locked) |
| `phase_e_allowed` | **false** (locked) |
| `qq_push_allowed` | **false** (locked) |
| `state_write_allowed` | **false** (locked) |
| `cron_enable_allowed` | **false** (locked) |
| `watchdog_bypass_allowed` | **false** (locked) |

## V4-E Readiness

| Readiness | Value |
|-----------|-------|
| V4-E allowed_to_generate | **true** |
| V4-E allowed_to_execute | **false** |

## Modified Files (this phase)

- `docs/V4_WATCHDOG_STATE_LOCK.md` (new)
- `docs/V4_STATE_LIFECYCLE_CONTRACT.md` (new)
- `docs/V4_WATCHDOG_STATE_LOCK_CLOSURE.md` (this file, new)
- `tools/check_v4_watchdog_contract.py` (new)
- `tools/check_v4_lock_timeout_contract.py` (new)
- `v2_football_quant/engine/v4_review_with_watchdog.py` (added guard markers: NO_AI_KILL_RETRY, FAIL_CLOSED, REPORT_ONLY)
- `v2_football_quant/engine/v4_scan_and_brief.py` (added guard markers: NO_AI_KILL_RETRY, FAIL_CLOSED, REPORT_ONLY, HARD_TIMEOUT, SOFT_TIMEOUT)

## Next Phase (V4-E)

- Allowed to generate: YES
- Allowed to execute: NO
- Must run all checkers before proceeding
- Must keep all production guards in place
