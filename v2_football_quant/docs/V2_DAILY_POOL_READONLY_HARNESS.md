# V2 DAILY_POOL Readonly Safety Harness
Phase: SAFE-HARNESS-0 | cron removed | readonly only, no production

daily_runner.py: added --dry-run --review-only --no-push --no-state-write --no-verified-write --no-cron --no-supervisor
v2_daily_pool_readonly_runner.py: safe wrapper, default dry-run + no-push + no-state + no-verified
v2_window_checker_with_watchdog.py: already readonly-safe
