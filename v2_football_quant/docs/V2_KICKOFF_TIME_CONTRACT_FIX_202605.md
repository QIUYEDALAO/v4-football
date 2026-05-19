# V2 Kickoff Time Contract Fix — 2026-05-19

## Root Cause
- selected_fixtures fixture_state wrote last_seen_time but NOT kickoff_time
- v2_window_worker: `ko_str = fstate.get("kickoff_time") or fstate.get("last_seen_time", "")`
- Result: last_seen_time (scan time ~21:18) used as kickoff → all fixtures judged STARTED_OR_CLOSED

## Fix
1. daily_runner.py: add kickoff_time, time_bj, home, away, league_id, league_name to fixture_state writes
2. v2_window_worker.py: remove last_seen_time fallback; skip fixtures with MISSING_KICKOFF_TIME

## After Fix
- kickoff_time present: 13/13 ✅ (was 0/13)
- window_status: DONE_WATCH_ONLY ✅ (was SKIPPED_STARTED_OR_CLOSED)
- WATCH_EARLY: 10, CANDIDATE: 1
- Next T-90 window: tonight ~22:59 CST (Ried vs Wolfsberger AC)
