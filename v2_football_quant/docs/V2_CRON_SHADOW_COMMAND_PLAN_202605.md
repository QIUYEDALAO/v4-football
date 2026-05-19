# V2 Cron Shadow Command Plan — 2026-05-19
**CRON NOT ENABLED — COMMANDS FOR MANUAL USE ONLY**

## DAILY_POOL (12:35)
```
python3 engine/daily_runner.py --run_tag DAILY_POOL --no-push --no-state-write --no-verified-write --no-cron --no-supervisor
```

## Window Check (hourly :05)
```
python3 engine/v2_window_checker_with_watchdog.py --no-push --observe-only --no-formal-state-write --no-verified-write
```

## T-90 Lock Window Proof (on-demand)
```
python3 tools/run_v2_t90_lock_window_proof_guarded.py --target-fixture Ried --no-push --no-state-write --no-verified-write --no-cron
```
