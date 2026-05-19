# V2 T-90 Lock Window Proof — 2026-05-19 22:02

## Step 1: System State
- PIPELINE_READY: true ✅
- PRODUCTION_VERIFIED: false
- QQ/cron/D13/verified: all false
**PASS**

## Step 2: Lock Window Check
- target_fixture: Ried vs Wolfsberger AC
- kickoff_time: 2026-05-20 00:29 CST
- minutes_to_ko: 147 min
- stage: **T_MINUS_3H** (NOT T-90M or T-45M)
- T-90 time: **2026-05-19 22:59 CST**
- T-90 remaining: 57 min
**WAIT — T-90 lock window not yet active**

## Step 3-4: Readonly Checker + Window Status
- window_status: DONE_WATCH_ONLY
- T-90M: 0, T-45M: 0
- lock_window_active: false
- bet_lockable: false
- BET_LOCKED_count: 0
- formal_state_written: false
- qq_sent: false

## Step 5: Lock Window Result
- BET_LOCKED_count: 0
- reason: **NO_T90_T45_FIXTURE**
- Ried vs Wolfsberger AC at T-3H, not in lock range

## Conclusion
**T90_LOCK_WINDOW_WAIT** — Re-run at 22:59 CST
