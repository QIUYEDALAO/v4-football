# V2 Active Window Live Proof Gate — 2026-05-19

## Step 1: Readonly Live Checker
- check_status: PASS
- active_window: true
- readonly_runner_result: present
- BET_LOCKED_count: 0
- qq_sent: false
- state_written: false
- verified_written: false
- proof_executed: false
**PASS**

## Step 2: Window Checker
- window_status: DONE_WATCH_ONLY
- checked_at: 2026-05-19T21:35
- window_summary: present (10 WATCH_EARLY, 1 CANDIDATE)
- new_locks: 0, locked_total: 0
**PASS**

## Step 3: State Contract
- fixtures_count: 13
- kickoff_time_present: 13/13
- missing_kickoff_time: 0
- next fixture: Ried vs Wolfsberger AC (T-3H, T-90 at 23:00)
**PASS**

## Step 4: No-Push Guard
- --no-push propagated to window checker
- OPENCLAW_NO_PUSH=1 set
- qq_sent: false
- push_suppressed: true
**PASS**

## Step 5: Web Page
- active window status visible
- BET_LOCKED=0 clearly shown
- QQ/cron/D13/verified all false
**PASS**

## Step 6: Conclusion
**PIPELINE_READY_ALLOWED**

### Rationale
- V2 DAILY_POOL → window_checker → readonly_runner chain verified
- kickoff_time contract fixed
- no-push propagation verified
- active_window=true observed with BET_LOCKED=0 (normal — no fixtures in T-90/T-45 window yet)
- No QQ, no cron, no D13, no verified, no state mutation during proof

### Awaiting
- First T-90 window at 23:00 CST (Ried vs Wolfsberger AC)
- At T-90, window checker may produce BET_LOCKED candidates
- PRODUCTION_VERIFIED still false and MUST remain so
