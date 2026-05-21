# Claude Code Safe Hardenning Issue List — 20260520

**Phase:** CLAUDE-CODE-SAFE-HARDENING-PACK-20260520  
**Generated:** 2026-05-20  
**Audit scope:** V4 wrapper, window checker, dashboard routes, QQ decision pack, one-shot job

---

## Issue Inventory

### 1. Wrapper: --date / --scan-date parameter passing
- **File:** `tools/run_v4_window_scan_capture_readonly.py:56`
- **Finding:** PASS. Wrapper accepts `--scan-date` (line 13) and passes it to runner as `--date` (line 56) which is the runner's expected parameter name. Both `--window` and the date are correctly forwarded.

### 2. Wrapper: --window parameter
- **File:** `tools/run_v4_window_scan_capture_readonly.py:12,56`
- **Finding:** PASS. `--window` is required (line 12) and correctly passed to runner (line 56).

### 3. Wrapper: no-push/no-d13/no-v33/no-hourly guards
- **File:** `tools/run_v4_window_scan_capture_readonly.py:15-18`
- **Finding:** PASS. All four flags defined with `default=True`. Env var `OPENCLAW_NO_PUSH=1` set in runner subprocess (line 55). However flags themselves are NOT explicitly passed to the runner subprocess command — they rely on env vars.

### 4. Wrapper: synthetic evidence
- **File:** `tools/run_v4_window_scan_capture_readonly.py:49`
- **Finding:** PASS. `synthetic_evidence` hardcoded to `False`. Evidence only set to `True` when `scout_after_hash != scout_before_hash` AND `runner_rc == 0`.

### 5. Window Checker: window-specific evidence requirement
- **File:** `tools/check_v4_next_scan_window_capture.py:67-103`
- **Finding:** PASS. Requires `win_evidence_ok` (window log or status contains correct window name). Date-level scout alone → WARN with explicit message "scout alone ≠ production_evidence".

### 6. Window Checker: date-level scout cannot PASS alone
- **File:** `tools/check_v4_next_scan_window_capture.py:84-103`
- **Finding:** PASS. When `has_scout and not win_evidence_ok`: sets `date_level_scout_only=True`, `status=WARN`, `production_evidence=False`.

### 7. Window Checker: late evidence blocking
- **File:** `tools/check_v4_next_scan_window_capture.py:35`
- **Finding:** PASS. `late_as_early_blocked=True` hardcoded in result.

### 8. Window Checker: auto-runner fallback risk
- **File:** `tools/check_v4_next_scan_window_capture.py:135-154`
- **Finding:** WARN. Has auto-runner fallback that executes `SCAN_RUNNER` when `minutes_past <= 30` and no evidence exists. This runs the real runner without --no-push flag explicitly passed. Mitigated by env vars but warrants a guard check.

### 9. Dashboard Route Checker: No HTTP actual-page checker
- **File:** `tools/check_intel_dashboard_user_visible_routes.py`
- **Finding:** MISSING. This file does not exist. Current `check_intel_web_route.py` only checks file existence and content, not actual HTTP responses.

### 10. Dashboard HTML: cron_removed and readonly_only as current-state tags
- **File:** `data/runtime/dashboard/index.html:79,84`
- **Finding:** WARN. `cron_removed` and `readonly_only` appear as current-state tags in the dashboard, which could be misinterpreted as stale/outdated status.

### 11. Dashboard HTML: ops_heartbeat.html V4 data mismatch
- **File:** `data/runtime/dashboard/ops_heartbeat.html:46`
- **Finding:** WARN. ops_heartbeat.html shows V4 A/B/C/SKIP = 0/0/3/2 (generated 01:13) while index.html correctly shows 0/6/4/0 (generated 10:00). ops_heartbeat is stale.

### 12. One-shot job: cron permanence guard
- **File:** `data/runtime/status/v4_midday_one_shot_schedule_20260520.json`
- **Finding:** PASS. `not_cron=true`, `job_type=one_shot`, `cron_modified=false`, `autodelete_after_run=true`.

### 13. V4 QQ Decision Pack: V4_QQ_ENABLED
- **File:** Multiple JSON markers, `docs/V4_QQ_ENABLE_DECISION_PACK_20260520.md`
- **Finding:** PASS. All markers confirm `V4_QQ_ENABLED=false`, `boss_approval_required=true`, `route=shadow_only`, `actual_send=false`, `qq_sent=false`.

### 14. D13/V33/HOURLY status
- **File:** Multiple status JSON markers
- **Finding:** PASS. All markers confirm D13_EXECUTED=false, V33_ENABLED=false, HOURLY_ENABLED=false.

### 15. check_ops_daily_operation.py: hardcoded date
- **File:** `tools/check_ops_daily_operation.py:76`
- **Finding:** WARN. Window log checks use hardcoded date `20260519` rather than dynamic `ops_date`.

---

## Summary

| # | Category | Status | Detail |
|:--|:---------|:-------|:-------|
| 1 | Wrapper --scan-date | PASS | Correctly passed as --date to runner |
| 2 | Wrapper --window | PASS | Required and forwarded to runner |
| 3 | Wrapper no-* guards | PASS | All four flags default True, env vars set |
| 4 | Wrapper synthetic evidence | PASS | Hardcoded False, hash-based evidence only |
| 5 | Window-specific evidence | PASS | Requires window log/status match |
| 6 | Date-level scout alone | PASS | → WARN, not PASS |
| 7 | Late evidence blocking | PASS | late_as_early_blocked=True |
| 8 | Auto-runner fallback | WARN | Runner called without explicit --no-push CLI flag |
| 9 | HTTP route checker | MISSING | `check_intel_dashboard_user_visible_routes.py` does not exist |
| 10 | Dashboard stale tags | WARN | cron_removed/readonly_only as current tags |
| 11 | ops_heartbeat stale | WARN | Shows old V4 data (0/0/3/2 vs 0/6/4/0) |
| 12 | One-shot job | PASS | not_cron=true, autodelete_after_run=true |
| 13 | V4_QQ_ENABLED | PASS | Consistently false across all markers |
| 14 | D13/V33/HOURLY | PASS | All consistently false |
| 15 | ops_daily hardcoded date | WARN | Window log check uses 20260519 not ops_date |

**Total issues:** 15 checked, 7 PASS, 4 WARN, 0 BLOCKER, 1 MISSING (file not found), 3 INFO  
**Blocker count:** 0
