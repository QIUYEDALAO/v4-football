# V4 RF Strong Confirmed B Floor Hotfix (2026-05-31)

## 背景
- 目标场次：BK Hacken vs Hammarby FF（瑞典超，fixture_id=1494188）。
- 现场观察：
  - `rf_shadow_score=73.5`
  - `rf_recent10_gate_status=RECENT10_GATE_PASS_7_OF_10`
  - `rf_recent5_grade_status=RECENT5_B_BASE_4_OF_5`
  - `rf_balance_status=STRONG_DRIVER_ACCEPTABLE`
  - `season_phase=ACTIVE_SEASON`
  - `league_tier=TIER_3_WEAK_COVERAGE`
  - `opening_market_support_status=MARKET_STRONG_CONFIRM`
  - `market_adjusted_shadow_grade=C`
- 问题：在 `season_aware_rf` official route 下，这类“强RF + 市场确认”候选被机械停留在 C，未进入 official B。

## 根因
- `engine/v4_scan_and_brief.py::_resolve_official_grade_from_shadow(...)` 之前只沿用 `market_adjusted_shadow_grade` 并做风险降级，缺少“强RF确认场景的 B-floor 保底”。
- 目标场次在进入 official route 前已是 `C`，因此 official 同步为 `C`。

## 本次最小修复
新增规则：`RF_STRONG_CONFIRMED_B_FLOOR`

触发条件（全部满足）：
1. `season_phase=ACTIVE_SEASON`
2. `league_tier in {TIER_1_ELITE, TIER_2_MAINSTREAM, TIER_3_WEAK_COVERAGE}`
3. `rf_shadow_score >= 73`
4. `recent5` 满足（`A_BASE_5_OF_5` 或 `B_BASE_4_OF_5`，或 used_count 双边>=4）
5. `recent10` 满足（`PASS_7_OF_10` 或 used_count 双边>=7）
6. Balance 为强驱动（`STRONG_DRIVER` 或 `HOT_DRIVER`）
7. Market 为确认/中性确认（`MARKET_STRONG_CONFIRM / MARKET_WEAK_CONFIRM / MARKET_NEUTRAL`）
8. 不属于硬风险（`MARKET_EXTREME_VETO` / `MARKET_NO_DATA` / `MARKET_NO_MARKET` / `TIER_4_NON_FORMAL` / `POST_OFFSEASON baseline-only`）

动作：
- 若当前 official 级别为 `C/SKIP`，仅保底升至 `B`。
- 追加 reason：`RF_STRONG_CONFIRMED_B_FLOOR`。

## 硬边界保持
- 不升 `A`。
- 不放开 `TIER_4_NON_FORMAL`。
- 不放开 `MARKET_EXTREME_VETO`。
- 不放开 `POST_OFFSEASON baseline-only`。
- 不允许 `MARKET_NO_DATA` 升 `A`。
- `H2H_LOW_SAMPLE` 仍保持“只标注不降级”，且 H2H 不单独制造 A/B。

## 验证结果
- `tools/check_v4_season_aware_production_switch.py` 新增 B-floor 样例与反例后通过。
- `tools/run_v4_season_aware_production_switch_dryrun.py --scan-date 20260531` 输出：
  - season_aware_rf: `A=1, B=36, C=35, SKIP=20`
  - `pending_ab_count=37`
  - `qq_route_guard_dryrun.real_send=false`
  - rollback smoke: `switchable=true`

## 影响范围
- 仅 `season_aware_rf` official route 的最小保护。
- 未修改 A/B 全局阈值。
- 未修改 cron / validation / live bet / QQ 实际发送。
- 未提交 runtime/scout/pending 产物。
