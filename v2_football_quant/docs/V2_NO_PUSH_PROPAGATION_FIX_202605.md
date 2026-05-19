# V2 No-Push Propagation Fix — 2026-05-19

## Issue
check_v2_readonly_live_window.py called window_checker WITHOUT --no-push.

## Fix
- Added --no-push to subprocess call
- Added OPENCLAW_NO_PUSH=1 env var (dual safety)
- Window checker already has robust guard: checks both argv and env

## Verified
- check_v2_readonly_live_window PASS
- qq_sent=false, cron=false, D13=false, verified=false
- active_window=false (correct — no T-90/T-45 window at test time)
