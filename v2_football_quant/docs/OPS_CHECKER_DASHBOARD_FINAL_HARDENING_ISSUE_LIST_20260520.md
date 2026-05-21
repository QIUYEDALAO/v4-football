# OPS Checker Dashboard Final Hardening Issue List — 20260520

**Phase:** OPS-CHECKER-DASHBOARD-FINAL-HARDENING-20260520  
**Generated:** 2026-05-20

## Issue Inventory

| # | Category | Status | Detail |
|:--|:---------|:-------|:-------|
| 1 | ops_checker --scan-date | FAIL | check_ops_daily_operation.py uses `--date`, ignores --scan-date |
| 2 | ops_checker --review-date | FAIL | No --review-date parameter; review files use ops_date which may differ |
| 3 | ops_checker --ops-date | WARN | --date exists but naming is ambiguous between scan/review/ops |
| 4 | ops_checker hardcoded 20260519 | FAIL | Window log checks hardcoded `20260519` (line 76); invalid_sources date hardcoded (line 93) |
| 5 | ops_checker hardcoded 20260517 | WARN | Dashboard stale check uses `20260517` (line 122) |
| 6 | ops_checker parse_known_args | WARN | `parse_known_args()` silently drops unknown flags instead of erroring |
| 7 | ops_checker traceback on missing file | FAIL | review structured file for non-existent date causes FileNotFoundError |
| 8 | V4 review files vs review_date | PASS | review files use ops_date (currently --date), correct |
| 9 | V4 scan window files vs scan_date | FAIL | Window log checks hardcoded 20260519, not dynamic |
| 10 | ops_heartbeat old V4 data | FAIL | Shows A/B/C/SKIP = 0/0/3/2 (generated 01:13); should show 0/6/4/0 |
| 11 | ops_heartbeat stale tags | FAIL | CURRENT section should not show cron_removed, readonly_only, no_cron_recovery |
| 12 | ops_heartbeat PROD_VERIFIED=false | WARN | Shows PRODUCTION_VERIFIED=true for V2 (correct) but V4 status missing |
| 13 | dashboard route checker exists | PASS | check_intel_web_route.py exists but only checks files, not HTTP pages |
| 14 | dashboard route checker HTTP | FAIL | No HTTP actual page checker exists for the 4 routes |
| 15 | V33 references classification | WARN | Mixed: guards (9 files), historical docs (7 files), potential active paths in engine (2 files) |
| 16 | active V33 path | PENDING | engine/v4_scan_and_brief.py:39-40, engine/v2_daily_pool_summary.py:109 need classification |
| 17 | D13/HOURLY false | PASS | All markers confirm false |
| 18 | V4_QQ_ENABLED false | PASS | All 7 markers confirm false |
| 19 | midday one-shot not executed | PASS | Status=SCHEDULED, capture_ran=false |

**Summary:** 19 items checked, 5 PASS, 5 WARN, 8 FAIL, 1 PENDING
