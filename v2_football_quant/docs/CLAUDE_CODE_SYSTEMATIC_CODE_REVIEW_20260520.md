# Claude Code Systematic Code Review — Report 20260520

**Phase:** CLAUDE-CODE-SYSTEMATIC-CODE-REVIEW-20260520
**Generated:** 2026-05-20T12:10:00+08:00

---

## Step 1: Audit Scope — PASS

12 files reviewed across 3 categories:
- **Core execution**: `engine/v4_scan_and_brief.py`, `engine/v4_runner.py`, `tools/run_v4_window_scan_capture_readonly.py`
- **Checkers (9)**: `check_ops_daily_operation.py`, `check_v4_next_scan_window_capture.py`, `check_v4_wrapper_regression.py`, `check_v4_midday_one_shot_job.py`, `check_v4_qq_decision_pack_consistency.py`, `check_v33_residual_audit.py`, `check_intel_desk_candidate_view.py`, `check_intel_dashboard_user_visible_routes.py`, `check_dashboard_route_stale_regression.py`

---

## Step 2: Parameter Contract Audit — WARN

### Missing args
| File | Missing |
|:---|:---|
| `engine/v4_scan_and_brief.py` | `--scan-date`, `--review-date`, `--no-push`, `--no-d13`, `--no-v33`, `--no-hourly`, `--preflight` |
| `check_v4_midday_one_shot_job.py` | No arguments at all (hardcoded to 20260520) |
| `check_v4_qq_decision_pack_consistency.py` | No arguments at all (hardcoded to 20260520) |

### Ignored args
| File | Ignores |
|:---|:---|
| `check_intel_dashboard_user_visible_routes.py` | `--no-push`, `--no-d13`, `--no-v33`, `--no-hourly` accepted but never passed to subprocess |

### parse_known_args_risk
- **P2**: `check_ops_daily_operation.py` previously used `parse_known_args()` — now fixed to `parse_args()`. No remaining instances found.

### date_contract_risk
- **P1**: `engine/v4_scan_and_brief.py` uses `--date` (not `--scan-date`). Wrapper `run_v4_window_scan_capture_readonly.py` translates `--scan-date` → `--date` at line 56. If engine is called directly without the wrapper, the parameter name mismatch could cause confusion.
- **P1**: `engine/v4_scan_and_brief.py` uses `--push` with values `always/conditional/never` (default=`always`). This is **inverted semantics** from `--no-push` (default=True) used everywhere else. The wrapper doesn't pass `--push never` — it relies on env var `OPENCLAW_NO_PUSH=1` instead. If engine is invoked directly without this env var, it defaults to `--push always`.

---

## Step 3: Evidence Authenticity Audit — WARN

### synthetic_evidence_risks
- **SAFE**: `run_v4_window_scan_capture_readonly.py` hardcodes `"synthetic_evidence": False` and binds evidence via before/after MD5 hash comparison.
- **SAFE**: `check_v4_next_scan_window_capture.py` requires window-specific evidence (log or status file) and explicitly rejects date-level scout alone as insufficient.

### window_specific_risks
- **P2**: `check_v4_next_scan_window_capture.py` line 76 checks only first 500 chars of log file (`log_content = win_log.read_text()[:500]`). If the window identifier appears after 500 chars, the check will false-negative.
- **P2**: `check_v4_next_scan_window_capture.py` lines 135-147: Auto-runner fallback executes `SCAN_RUNNER` as subprocess when `minutes_past <= 30`. This **can trigger an actual production scan** as a side effect of running a checker. Mitigated by env vars `OPENCLAW_NO_PUSH=1, V2_OBSERVE_ONLY=1`, but the scan itself still runs.

### evidence_source_contract
- **P1**: `check_v4_next_scan_window_capture.py` reads grades from the date-level scout file (not window-specific) when window evidence is missing (lines 89-101). It correctly marks `date_level_scout_only=True` and refuses `production_evidence`, but still reports A/B/C/SKIP counts derived from the date-level scout — which could be confused with window-specific counts.
- **SAFE**: All checker files read evidence markers rather than writing them (with the exception of the auto-runner fallback noted above).

---

## Step 4: Dashboard CURRENT/History Partition — PASS

### current_history_risks
- **SAFE**: `check_intel_desk_candidate_view.py` uses `CURRENT\s*:` prefix regex — correctly excludes `not_current=true` from CURRENT section matching.
- **SAFE**: All 4 dashboard HTML files have clean CURRENT sections with stale tags quarantined to 历史审计 section.
- **SAFE**: B=6 candidates visible on all 4 routes with match details.
- **SAFE**: C=4 items all marked observation-only.
- **P2**: `check_intel_dashboard_user_visible_routes.py` still uses a fragile guard for C value detection (line 47): `all(x in html.split("历史")[0] if "历史" in html else True for x in c_matches)`. This splits the HTML on the literal character "历史" which could appear in match names or other content. Lower risk since current dashboard data doesn't trigger this code path.

---

## Step 5: Regex and Text Checker Audit — PASS (with P2 notes)

### regex_risks
- **SAFE**: `check_dashboard_route_stale_regression.py` C value regex: `C\s*[=:：]\s*(\d+)` — only matches assignment patterns.
- **SAFE**: `check_intel_desk_candidate_view.py` V4_QQ_ENABLED check: `V4_QQ_ENABLED[^|]{0,30}true` — bounded within same status line.
- **P2**: `check_intel_dashboard_user_visible_routes.py` line 46: `r'C[:\s]*(\d+)'` still broad — matches `C1`, `C2`, `C3`, `C4` labels. The guard logic on line 47 partially mitigates but is fragile.
- **P2**: `check_v4_next_scan_window_capture.py` log content window check only reads 500 chars — could miss late-appearing window markers.
- **SAFE**: All QQ true/false checks have V2/V4 subsystem labels to prevent false conflict detection.

---

## Step 6: One-shot / Cron Boundary — PASS

### cron_modified_risk
- **SAFE**: No checker modifies cron configuration.
- **SAFE**: `check_v4_midday_one_shot_job.py` verifies: `not_cron=true`, `autodelete_after_run=true`, `cron_modified=false`.
- **P2**: Checkers verify JSON marker files, not the actual system crontab. If a marker file is manually edited to say `not_cron=true` when a real cron exists, the checker would be deceived. Low risk given the operational context.

### one_shot_risk
- **SAFE**: One-shot job configured with `autodelete_after_run=true` — self-cleaning.
- **SAFE**: `engine/v4_scan_and_brief.py` has global lock (`v4_scan_global.lock`) preventing concurrent scan execution.
- **P2**: `engine/v4_scan_and_brief.py` default `--push=always` means if the engine is run directly (not via wrapper), it will attempt to output QQ text to stdout. The env var `OPENCLAW_NO_PUSH=1` set by the wrapper is the only gate preventing this.

---

## Step 7: V33/D13/HOURLY Safety — PASS

### active_v33_path_count
- **SAFE**: Previous audit confirmed 0 active V33 paths (20 allowed_guard, 42 historical_doc).
- **SAFE**: `check_v33_residual_audit.py` classifier correctly distinguishes guard/checker files from executable V33 code.

### d13_risk
- **SAFE**: All wrappers and checkers default `--no-d13=True`.
- **P2**: `engine/v4_scan_and_brief.py` has no D13 awareness — if invoked without the env var guard, it doesn't block D13.

### hourly_risk
- **SAFE**: All wrappers and checkers default `--no-hourly=True`.
- **SAFE**: `engine/v4_scan_and_brief.py` has no hourly trigger logic — hourly execution is controlled externally.

---

## P0/P1/P2 Summary

### P0 — None found
No blocker-level issues that would immediately compromise production safety.

### P1 — 2 items (recommend fix)
1. **`engine/v4_scan_and_brief.py` inverted push semantics**: Uses `--push always` default vs `--no-push` everywhere else. If engine is invoked directly without env var, QQ content is printed to stdout.
2. **`engine/v4_scan_and_brief.py` parameter name mismatch**: Uses `--date` not `--scan-date`. Wrapper translates at call site; direct invocation breaks contract.

### P2 — 7 items (can defer)
1. `check_v4_midday_one_shot_job.py` has no date arguments — hardcoded to 20260520.
2. `check_v4_qq_decision_pack_consistency.py` has no date arguments — hardcoded to 20260520.
3. `check_v4_next_scan_window_capture.py` auto-runner fallback can trigger production scan.
4. `check_v4_next_scan_window_capture.py` log check only reads first 500 chars.
5. `check_intel_dashboard_user_visible_routes.py` C value regex still broad (with fragile guard).
6. `check_ops_daily_operation.py` V4 review file schema mismatch — expects flat `v4['A']` but 20260519 file uses `official_counts.A` nested structure → KeyError traceback.
7. `check_ops_daily_operation.py` hardcoded expectations `V4_A0`/`V4_B0` may not match current operational state (B=6 today, B=3 yesterday).

### Confirmed Safe
- All 9 checker files produce no synthetic evidence
- All dashboard HTML files have clean CURRENT/History partition
- V33 active path count = 0
- D13/HOURLY blocked at all wrapper/checker layers
- One-shot job properly configured (not_cron, autodelete)
- B=6, C=4, QQ disabled visible on all routes

### Did not touch production
- No captures ran
- No QQ pushes
- No strategy changes
- No cron modifications

### Next Steps
1. Fix P1 items in `engine/v4_scan_and_brief.py` (add `--no-push` flag, align parameter names)
2. Add date arguments to `check_v4_midday_one_shot_job.py` and `check_v4_qq_decision_pack_consistency.py`
3. Remove auto-runner fallback from `check_v4_next_scan_window_capture.py` (checker should not execute production code)
4. Fix remaining regex issues in `check_intel_dashboard_user_visible_routes.py`
5. Fix `check_ops_daily_operation.py` to handle nested `official_counts` schema
6. Update `check_ops_daily_operation.py` V4_A0/V4_B0 expectations for current operational state

---

## Step 8: Non-Production Verification — WARN_ONLY

| Checker | Result |
|:---|:---|
| `check_v4_wrapper_regression.py` | PASS 14/14 |
| `check_v4_midday_one_shot_job.py` | PASS 24/24 |
| `check_v4_qq_decision_pack_consistency.py` | PASS 23/23 |
| `check_dashboard_route_stale_regression.py` | PASS 42/42 |
| `check_intel_desk_candidate_view.py` | PASS 68/68 |
| `check_v33_residual_audit.py` | PASS active_v33=0 |
| `check_ops_daily_operation.py` | FAIL — KeyError 'A' (schema mismatch) |

6/7 checkers PASS. 1 checker fails due to V4 review file schema mismatch (P2-006).

## Step 9: Report Generated
- Report: `docs/CLAUDE_CODE_SYSTEMATIC_CODE_REVIEW_20260520.md`
- JSON: `data/runtime/status/claude_code_systematic_code_review_20260520.json`
