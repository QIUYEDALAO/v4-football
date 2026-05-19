# V2 Next Window Capture Runbook — 2026-05-19

## Step 1: System State
- CODE_READY: true
- PIPELINE_READY: false
- PRODUCTION_VERIFIED: false
- QQ: false
- cron: false
- D13: false
- verified: false
- daily_pool: RESTORED (13 fixtures in selected_fixtures_20260519.json)
- window_status: SKIPPED_STARTED_OR_CLOSED → **NEXT WINDOW COMING**

## Step 2: Next Fixture
| Field | Value |
|-------|-------|
| Match | **Ried vs Wolfsberger AC** |
| League | 奥甲 |
| Kickoff | 2026-05-20 00:29 CST |
| Remaining | 184 min (from 21:21) |
| Odds D | 2.28 |
| Stage | T_MINUS_6H |

## Step 3: Window Times
| Window | Time (CST) | Status |
|--------|-----------|--------|
| T-90m | **2026-05-19 22:59** | ⏰ 94 min from now |
| T-45m | 2026-05-19 23:44 | |
| T-15m | 2026-05-20 00:14 | |

## Step 4: Upcoming Fixture Windows Tonight
| Time | Match | League | T-90 | T-45 |
|------|-------|--------|------|------|
| 00:29 | Ried vs Wolfsberger AC | 奥甲 | 22:59 | 23:44 |
| 01:59 | Monza vs Juve Stabia | 意乙 | 00:29 | 01:14 |
| 02:29 | Bournemouth vs Man City | 英超 | 00:59 | 01:44 |
| 02:29 | KVC Westerlo vs Standard Liege | 比甲 | 00:59 | 01:44 |
| 02:29 | Genk vs Antwerp | 比甲 | 00:59 | 01:44 |
| 02:29 | Charleroi vs OH Leuven | 比甲 | 00:59 | 01:44 |
| 02:29 | Rouen vs Laval | 法乙 | 00:59 | 01:44 |
| 03:14 | Chelsea vs Tottenham | 英超 | 01:44 | 02:29 |

## Step 5: Manual Capture Commands
```
# At T-90 (22:59 CST tonight):
cd v2_football_quant
python3 engine/v2_window_checker_with_watchdog.py

# Readonly runner (no push, no state):
python3 tools/v2_daily_pool_readonly_runner.py --dry-run --no-push --no-state-write --no-verified-write --no-cron --no-supervisor --watchdog-only-failure
```

## Step 6: Answers
| Question | Answer |
|----------|--------|
| 下一场是什么？ | Ried vs Wolfsberger AC (奥甲) |
| T-90 几点？ | 2026-05-19 22:59 CST |
| T-45 几点？ | 2026-05-19 23:44 CST |
| 现在 active window？ | 否 (SKIPPED_STARTED_OR_CLOSED, 等T-90) |
| 为什么没有 BET_LOCKED？ | 全13场在 T-6H 早盘阶段，未进入锁仓窗口 |
| 明天手动时间？ | 22:59, 23:44, 00:14... |
| PIPELINE_READY？ | ❌ 仍禁止 |
| PRODUCTION_VERIFIED？ | ❌ 仍禁止 |
| GUARD_WEAK？ | ✅ 仍存在 |
