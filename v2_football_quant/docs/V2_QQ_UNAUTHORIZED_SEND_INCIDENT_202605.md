# V2 QQ Unauthorized Send Incident — 2026-05-19

## Incident Summary
- **type**: QQ_UNAUTHORIZED_SEND
- **detected**: 2026-05-19 23:11 CST
- **boss_received_qq**: true
- **message**: "新增 BET_LOCKED：1 场，执行投注：有"
- **production_verified**: false
- **qq_expected**: false

## Root Cause
v2_window_checker_with_watchdog.py → _push_system_event() fired at 23:09:22.
The window_checker ran during T-90 proof and the _push_system_event() path was
not gated by V2_QQ_SEND_ENABLED or incident block.

## Evidence
- notify: v2_window_notify_20260519.json, pushed=true, run_id=966f21e9f7723b28
- state: selected_fixture_ids=['1545407'], official_bet_locked=true, qq_required=true
- lock: Ried vs Wolfsberger AC, T_MINUS_90M, odds_D=2.28
- real_bet_execution: FALSE (no broker/order evidence)
- QQ text "执行投注：有" is standard V2 lock announcement, not real execution

## Fixes Applied
1. **V2_QQ_SEND_ENABLED hard gate**: _push_system_event() requires V2_QQ_SEND_ENABLED=1
2. **Incident emergency block**: v2_qq_unauthorized_send_incident marker blocks all pushes
3. **Verified**: no secondary push risk confirmed

## Current State
- PRODUCTION_VERIFIED: still false
- QQ: false (enforced by gate)
- cron: false
- D13: false
- verified: false

## Next Steps
- Resume PROD_SHADOW_CLOSURE_MASTER after incident acknowledged
- BOSS approval required before any QQ enable
