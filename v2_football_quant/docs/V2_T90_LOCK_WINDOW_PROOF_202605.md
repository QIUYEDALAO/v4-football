# V2 T-90 Lock Window Proof — 2026-05-19 22:30

## Step 1: System
- PIPELINE_READY: true ✅
- PRODUCTION/QQ/cron/D13/verified: all false

## Step 2: Lock Window Check
- target: Ried vs Wolfsberger AC
- kickoff: 2026-05-20 00:30 CST
- remaining: ~118 min to KO
- stage: **T_MINUS_3H** (NOT T-90M/T-45M)
- T-90M estimated: ~23:00 CST (30 min from now)

## Step 3-4: Readonly + Window
- readonly: PASS, BL=0, formal_state_written=false
- window: DONE_WATCH_ONLY, T-90M=0, T-45M=0, T-3H=1

## Conclusion
**T90_LOCK_WINDOW_WAIT** — ~30 min to T-90 window
Re-run at ~23:00 CST.
