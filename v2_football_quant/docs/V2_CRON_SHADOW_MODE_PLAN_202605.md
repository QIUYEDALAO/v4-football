# V2 Cron Shadow Mode Plan — 2026-05-19
**STATUS: PLAN ONLY — CRON NOT ENABLED**

## Shadow Schedule
- DAILY_POOL: 12:35 daily → `daily_runner.py --run_tag DAILY_POOL --dry-run --no-push --no-state-write`
- Window checker: hourly :05 → `v2_window_checker_with_watchdog.py --no-push --observe-only`
- T-90/T-45 lock window: on-demand → `check_v2_readonly_live_window.py`

## Guard Requirements
- no-push always
- no-verified always
- no-D13 always
- hash guard before/after state writes
- watchdog-only failure report
- BOSS approval required to move from shadow → production
