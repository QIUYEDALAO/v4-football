# V2 System Restructure — Issue Inventory 2026-05-19

## P0 Issues
| ID | Issue | Status |
|----|-------|--------|
| P0_TRUE_READONLY_NOT_PROVEN | readonly chain missing --observe-only guard | FIXING |
| P0_DAILY_RUNNER_GUARD_WEAK | flags in argparse but not enforced in run_once | DOCUMENTED |
| P0_OPS_DATE_STATE_DATE_MISMATCH | daily_runner uses get_ops_date(), window_worker uses natural date | FIXING |
| P0_SELECTED_IDS_SEMANTIC | CANDIDATE/WATCH mixed with BET_LOCKED in selected | FIXING |
| P0_ACTIVE_LOCK_CONFLATED | T-3H treated like T-90 | FIXED (kickoff_time fix) |
| P0_T90_WAIT_PASS_BROKEN | T-3H could be called T90 PASS | FIXING |
| P0_ODDS_BOUNDARY | 2.90 ambiguous between IN_BAND and ODDS_HIGH | VERIFYING |
| P0_NO_BET_REASON_COARSE | "no recommendation" without per-fixture reason | FIXING |

## P1 Issues
| ID | Issue | Status |
|----|-------|--------|
| P1_CRON_DISABLED | cron removed, no auto-scan | KNOWN |
| P1_QQ_ROUTE_NOT_READY | QQ gate not production-ready | KNOWN |
| P1_D13_PREVIEW_ONLY | D13 only draft, not executable | KNOWN |
| P1_DASHBOARD_INCOMPLETE | missing lock_window_active, bet_lockable fields | FIXING |
