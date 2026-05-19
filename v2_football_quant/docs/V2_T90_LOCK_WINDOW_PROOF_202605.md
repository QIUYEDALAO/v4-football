# V2 T-90 Lock Window Proof — 2026-05-19 23:00

## Step 1: System
- PIPELINE_READY: true ✅
- PRODUCTION/QQ/cron/D13/verified: all false

## Step 2: Lock Window Active
- target: Ried vs Wolfsberger AC
- stage: **T_MINUS_90M** ✅
- minutes_to_ko: ~89 min

## Step 3-4: Readonly Proof
- readonly: PASS, formal_state_written=false
- window_status: **DONE_BET_LOCKED**
- T-90M: 1, T-45M: 0, T-3H: 1

## Step 5: Lock Result
**T90_LOCK_WINDOW_BET_LOCKED_PROOF**

| Field | Value |
|-------|-------|
| BET_LOCKED_count | **1** |
| Locked fixture | **Ried vs Wolfsberger AC** (#1545407) |
| Odds D | 2.28 (IN_BAND ✓) |
| Lock stage | T_MINUS_90M |
| selected_fixture_ids | [not persisted — observe-only] |
| qq_sent | false |
| formal_state_written | false |

## Guards
- PRODUCTION_VERIFIED: false
- QQ: false | cron: false | D13: false
- True readonly enforced

## Conclusion
**V2 lock window logic PROVEN at T-90. BET_LOCKED correctly identified, safely isolated.**
