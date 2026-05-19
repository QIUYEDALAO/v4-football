# V2 Cron Enable Plan — 2026-05-19 23:35

## Commands
1. DAILY_POOL (12:35): python3 engine/daily_runner.py --run_tag DAILY_POOL --no-push --no-verified-write --no-cron --no-supervisor
2. WINDOW_CHECK (hourly :05): python3 engine/v2_window_checker_with_watchdog.py --no-verified-write --no-cron --no-supervisor
3. T90_PROOF (on-demand): python3 tools/run_v2_t90_lock_window_proof_guarded.py
4. DASHBOARD_REFRESH (hourly :10): python3 tools/intel_ops_refresh.py --no-push --no-verified-write
5. HEARTBEAT (hourly :00): check_v2_prod_automation_closure.py

## Guard Rules
- All commands: lock + timeout(300s) + watchdog
- No V33, no HOURLY, no D13
- QQ only via V2_QQ_SEND_ENABLED + route guard + duplicate suppression
