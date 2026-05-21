# V4 Wrapper Marker Fix Report Normalize — Report 20260520

**Phase:** V4-WRAPPER-MARKER-FIX-REPORT-NORMALIZE-20260520
**Generated:** 2026-05-20T15:18:00+08:00
**Status:** WARN_ONLY

---

## Step 1: JSON Validation — PASS

**json_valid:** true

`data/runtime/status/v4_wrapper_marker_isolated_session_fix_20260520.json` parsed successfully via `python3 -m json.tool`.

No JSON format anomaly risk. The file is valid JSON.

---

## Step 2: Conclusion Normalization — PASS

**old_conclusion:** V4-WRAPPER-MARKER-ISOLATED-SESSION-FIX_PASS (ALL_PASS)
**new_conclusion:** V4_WRAPPER_MARKER_FIX_NORMALIZE_WARN_ONLY

### Why the original report could NOT say ALL_PASS

The previous phase checker returned 8/9 PASS with `existing_markers` as the sole failure. The report wrote "ALL_PASS" which was incorrect — 8/9 ≠ ALL_PASS. The existing markers (4 files for 20260520 midday and early windows) were written by pre-fix code and lacked the `V4_QQ_ENABLED` field. Calling this "ALL_PASS" masked a real data quality gap.

After this normalization phase, the checker now correctly classifies existing markers as `legacy_warn` (not active_fail), yielding 9/9 code-level PASS. However, the overall phase conclusion remains WARN_ONLY because:
- 4 legacy markers still have field deficiencies
- 13 legacy files exist in the wrong `data/data/` directory
- System normalization is incomplete until legacy artifacts are addressed

---

## Step 3: Existing Markers Classification — PASS

**legacy_marker_warn_count:** 4
**active_marker_fail_count:** 0
**checker_status:** WARN_ONLY

### Classification logic

Markers generated before `2026-05-20T15:00:00+08:00` (the fix cutoff) are classified as **legacy_warn**. They were written by old code that didn't include `V4_QQ_ENABLED`, `generated_at`, etc. Their deficiencies are expected and do NOT indicate active code failure.

Markers generated after the cutoff missing required fields would be classified as **active_fail** — a real code problem.

### Legacy markers (4)

| Path | Deficiency |
|:---|:---|
| `v4_scan_midday_window_capture_after_due_20260520.json` | missing_V4_QQ_ENABLED |
| `v4_scan_midday_push_20260520.json` | missing_V4_QQ_ENABLED |
| `v4_scan_early_window_capture_after_due_20260520.json` | missing_V4_QQ_ENABLED |
| `v4_scan_early_push_20260520.json` | missing_V4_QQ_ENABLED |

All 4 are from before the fix. Zero active failures. Next window's wrapper/engine run will produce compliant markers.

---

## Step 4: Wrong Directory Audit — PASS

**legacy_wrong_dir_marker_count:** 13
**audit_only:** true

### `data/data/runtime/status/` — 13 legacy engine push markers

| # | File | Date | Window |
|:--|:---|:---|:---|
| 1 | v4_scan_push_20260517_early.json | 20260517 | early |
| 2 | v4_scan_push_20260517_evening.json | 20260517 | evening |
| 3 | v4_scan_push_20260517_late.json | 20260517 | late |
| 4 | v4_scan_push_20260518_evening.json | 20260518 | evening |
| 5 | v4_scan_push_20260518_late.json | 20260518 | late |
| 6 | v4_scan_push_20260518_midday.json | 20260518 | midday |
| 7 | v4_scan_push_20260518_night.json | 20260518 | night |
| 8 | v4_scan_push_20260519_early.json | 20260519 | early |
| 9 | v4_scan_push_20260519_evening.json | 20260519 | evening |
| 10 | v4_scan_push_20260519_late.json | 20260519 | late |
| 11 | v4_scan_push_20260519_midday.json | 20260519 | midday |
| 12 | v4_scan_push_20260519_night.json | 20260519 | night |
| 13 | v4_scan_push_20260520_midday.json | 20260520 | midday |

All 13 use old naming (`v4_scan_push_{date}_{window}`), old path (`data/data/`), and lack new fields.

Audit JSON written to: `data/runtime/status/v4_legacy_wrong_marker_dir_audit_20260520.json`

**Not deleted. Not migrated. audit_only=true. production_evidence=false.**

---

## Step 5: Naming Unification — PASS

**new push marker pattern (standard):**
```
data/runtime/status/v4_scan_{window}_push_{scan_date}.json
```
Concrete example: `v4_scan_midday_push_20260520.json`

**old push marker generated:** false (old pattern `v4_scan_push_{date}_{window}` not found in any source file)

Unified across all 3 files:

| File | Pattern | Concrete example |
|:---|:---|:---|
| `engine/v4_scan_and_brief.py:277` | `v4_scan_{window}_push_{scan_date}.json` | `v4_scan_midday_push_20260520.json` |
| `tools/run_v4_window_scan_capture_readonly.py:30` | `v4_scan_{window}_push_{scan_date}.json` | `v4_scan_evening_push_20260520.json` |
| `tools/check_v4_next_scan_window_capture.py:51` | `v4_scan_{window}_push_{scan_date}.json` | `v4_scan_night_push_20260520.json` |

Window capture markers also unified:
```
data/runtime/status/v4_scan_{window}_window_capture_after_due_{date}.json
```
Concrete example: `v4_scan_midday_window_capture_after_due_20260520.json`

---

## Step 6: Non-Production Verification — PASS

| Check | Result |
|:---|:---|
| `check_v4_wrapper_marker_isolated_session.py` | 9/9 PASS, status=PASS, legacy_warn=4, active_fail=0 |
| `run_v4_window_scan_capture_readonly.py --preflight` | `capture_ran=false, evidence_written=false, synthetic_evidence=false` |
| `check_v4_next_scan_window_capture.py --window evening` | `window_due=false, capture_ran=false, auto_runner_disabled=true` |

No actual capture ran. No `--run-readonly-runner` passed.

---

## Key Questions Answered

1. **原报告为什么不能写 ALL_PASS？** The checker was 8/9 PASS with existing_markers failing. 8/9 ≠ ALL_PASS. The failure was dismissed as "expected" but the report still claimed ALL_PASS — a contradiction.

2. **JSON 是否有效？** Yes. `python3 -m json.tool` parses successfully. No format anomaly.

3. **existing_markers 是 legacy_warn 还是 active_fail？** legacy_warn. All 4 markers were generated before the fix cutoff. Zero active_fail.

4. **data/data 错目录是否仍有历史 marker？** Yes. 13 legacy engine push markers from 20260517–20260520, all with old naming. Audited, not deleted.

5. **新 marker 路径是否统一？** Yes. All 3 files now use `v4_scan_{window}_push_{date}.json` under `data/runtime/status/`. Old `v4_scan_push_{date}_{window}.json` pattern not found in source.

6. **是否运行了 actual capture？** No. All verification used `--preflight` or window-not-yet-due paths.

7. **是否真实推 QQ？** No. `V4_QQ_ENABLED=false`, `qq_sent=false` across all checks.

8. **是否触碰 D13/V33/HOURLY？** No. `--no-d13 --no-v33 --no-hourly` on all commands.

9. **当前是否阻塞 evening？** No. Evening window is 62 minutes away. preflight confirms `capture_ran=false`. Checker shows `window_due=false, status=WAIT`. No blocker.

10. **下一任务是什么？** Evening window (16:20) will be the first test of the fixed marker code. After wrapper+engine runs, verify: (a) markers land in correct `data/runtime/status/`, (b) all fields present including `V4_QQ_ENABLED`, (c) no new files appear in `data/data/runtime/status/`. Then consider cleanup of 13 legacy files from wrong directory.

---

## Changed Files

| # | File | Change |
|:--|:---|:---|
| 1 | `tools/check_v4_wrapper_marker_isolated_session.py` | legacy/active classification, WARN_ONLY status tier |
| 2 | `data/runtime/status/v4_legacy_wrong_marker_dir_audit_20260520.json` | NEW — 13-file wrong-dir audit |
| 3 | `docs/V4_WRAPPER_MARKER_FIX_REPORT_NORMALIZE_20260520.md` | NEW — this report |
| 4 | `data/runtime/status/v4_wrapper_marker_fix_report_normalize_20260520.json` | NEW — status JSON |

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
| old_marker_rewritten_as_evidence | false |
