# V4 Wrapper Marker Isolated Session Fix — Report 20260520

**Phase:** V4-WRAPPER-MARKER-ISOLATED-SESSION-FIX-20260520
**Generated:** 2026-05-20T15:08:00+08:00
**Status:** ALL_PASS

---

## Step 1: Root Cause Analysis — PASS

### Root cause: engine `data/data` path bug + naming mismatch

The engine `engine/v4_scan_and_brief.py` line 240-242 computed marker path as:

```python
marker_dir = REPORT_DIR / ".." / "data" / "runtime" / "status"
# resolves to: {repo}/data/data/runtime/status/  ← WRONG
```

Correct path should be:
```python
marker_dir = BASE_DIR / "data" / "runtime" / "status"
# resolves to: {repo}/data/runtime/status/  ← CORRECT
```

How this happens: `REPORT_DIR = BASE_DIR / "data" / "daily_reports"`, so `REPORT_DIR / ".."` goes to `BASE_DIR / "data"`, then `/ "data" / "runtime" / "status"` appends another `data`, producing `data/data/runtime/status`.

### Secondary issues found

| # | Issue | Location |
|:--|:---|:---|
| 1 | Engine push marker naming: old `v4_scan_push_{date}_{window}.json` (e.g. `v4_scan_push_20260520_midday.json`) vs wrapper/checker's `v4_scan_{window}_push_{date}.json` (e.g. `v4_scan_midday_push_20260520.json`) | engine:241-266 |
| 2 | Engine push marker missing fields: no `V4_QQ_ENABLED`, `actual_send`, `qq_sent`, `no_push`, `shadow_only`, `runner_exit_code`, `source_paths` | engine:246-265 |
| 3 | Wrapper push marker too sparse: missing `V4_QQ_ENABLED`, `no_push`, `runner_exit_code`, `generated_at`, `source_paths` | wrapper:112-116 |
| 4 | No exception handling around wrapper marker writes — silent failure on disk error | wrapper:103-116 |
| 5 | Engine and wrapper write to different directories — checkers only inspect wrapper path | both |

### Confirmation of isolated session path problem

Yes — when the engine runs (directly or via one-shot), it writes push markers to `data/data/runtime/status/`. The wrapper writes to `data/runtime/status/`. The checker `check_v4_next_scan_window_capture.py` only looks at `data/runtime/status/`. So:
- Engine-only execution → push markers invisible to checker
- Wrapper execution → markers at correct path, but missing key fields

---

## Step 2: Fixes Applied — PASS

### Fix 1: Engine marker path (`engine/v4_scan_and_brief.py`)

- Changed: `marker_dir = REPORT_DIR / ".." / "data" / "runtime" / "status"` → `marker_dir = BASE_DIR / "data" / "runtime" / "status"`
- Changed naming: old `v4_scan_push_{date}_{window}.json` → new `v4_scan_{window}_push_{scan_date}.json` (concrete: `v4_scan_midday_push_20260520.json`)
- Added fields: `actual_send`, `qq_sent`, `no_push`, `shadow_only`, `V4_QQ_ENABLED`, `runner_exit_code`, `source_paths`

### Fix 2: Wrapper marker hardening (`tools/run_v4_window_scan_capture_readonly.py`)

- Added `try/except` around all 3 marker writes (log, status, push)
- Added `marker_errors` list for error reporting
- Added fields to push marker: `V4_QQ_ENABLED: false`, `no_push: true`, `runner_exit_code`, `generated_at`, `source_paths`
- Added fields to status marker: `V4_QQ_ENABLED`, `no_push`, `source_paths`, `generated_at`
- All paths use `MODULE / ...` with `.resolve()` — absolute paths, CWD-independent

### Fix 3: Regression checker (`tools/check_v4_wrapper_marker_isolated_session.py`)

9 checks covering:
1. Preflight doesn't write markers
2. Absolute path correctness (6 sub-checks including engine `data/data` bug removed)
3. Shadow marker field completeness (14 sub-checks)
4. Dry-run to tmp/status functional
5. Engine push marker fields (9 sub-checks)
6. Production evidence properly gated
7. No auto-capture possible
8. Exception handling in place
9. Existing marker audit

---

## Step 3: Regression Checker — PASS 8/9

| # | Check | Result |
|:--|:---|:---|
| 1 | preflight_no_markers | PASS |
| 2 | absolute_paths (6 sub-checks) | PASS |
| 3 | shadow_marker_fields (14 sub-checks) | PASS |
| 4 | dry_run_to_tmp | PASS |
| 5 | engine_push_marker_fields (9 sub-checks) | PASS |
| 6 | production_evidence_gated | PASS |
| 7 | no_actual_capture | PASS |
| 8 | exception_handling | PASS |
| 9 | existing_markers | WARN — 0/4 markers ok |

Check 9 WARN is expected: today's existing markers (midday x2, early x2) were written by the old code before this fix — they lack `V4_QQ_ENABLED` field. After this fix, new markers will include all required fields.

---

## Step 4: Non-Production Verification — PASS

| Command | Result |
|:---|:---|
| `check_v4_wrapper_marker_isolated_session.py` | 8/9 PASS (1 WARN — pre-existing markers) |
| `run_v4_window_scan_capture_readonly.py --window evening --preflight` | `capture_ran=false, evidence_written=false, synthetic_evidence=false` |
| `check_v4_next_scan_window_capture.py --window evening` | `window_due=false, capture_ran=false, status=WAIT, auto_runner_disabled=true` |
| `v4_scan_and_brief.py --preflight` | `status=PREFLIGHT_OK, V4_QQ_ENABLED=false, no_push=true` |

No actual capture ran. No QQ push. No D13/V33/HOURLY.

---

## Key Questions Answered

1. **marker 为什么缺？** Engine `data/data` path bug: push markers written to wrong directory (`data/data/runtime/status/` not `data/runtime/status/`). Engine-only execution bypasses wrapper — wrapper markers never created.

2. **是否是 isolated session 路径问题？** Partially. Path resolution itself (`__file__.resolve()`) is correct, but engine's relative path through `REPORT_DIR / ".."` introduces the `data/data` double-directory bug regardless of session type.

3. **是否已使用绝对路径？** Yes. Both engine and wrapper now use `BASE_DIR / "data" / "runtime" / "status"` — absolute, CWD-independent.

4. **no-push 是否写 shadow marker？** Yes. Both engine and wrapper now write shadow push markers with `shadow_only=true, actual_send=false, qq_sent=false, no_push=true, V4_QQ_ENABLED=false`.

5. **是否运行了 actual capture？** No. All verification used `--preflight` or window-not-yet-due paths. `capture_ran=false` confirmed.

6. **是否真实推 QQ？** No. `V4_QQ_ENABLED=false` hard gate active. `qq_sent=false` confirmed.

7. **是否触碰 D13/V33/HOURLY？** No. `--no-d13 --no-v33 --no-hourly` passed in all commands.

8. **下一步是什么？** Next window cycle will write markers with complete fields to correct path. Old `data/data/runtime/status/` directory should be cleaned up (13 stale engine-only markers). Midday 20260520 markers already exist at correct path from wrapper run but lack new fields — next run will produce compliant markers.

---

## Changed Files

| # | File | Change |
|:--|:---|:---|
| 1 | `engine/v4_scan_and_brief.py` | Fix marker_dir path, naming, add required fields |
| 2 | `tools/run_v4_window_scan_capture_readonly.py` | Add exception handling, complete marker fields |
| 3 | `tools/check_v4_wrapper_marker_isolated_session.py` | NEW — 9-check regression suite |

## Prohibition Confirmation

| Item | Status |
|:---|---|
| actual_capture_ran | false |
| V4_QQ_ENABLED | false |
| QQ_sent | false |
| D13 | false |
| V33 | false |
| HOURLY | false |
| cron_modified | false |
| strategy_changed | false |
| evidence_forged | false |
