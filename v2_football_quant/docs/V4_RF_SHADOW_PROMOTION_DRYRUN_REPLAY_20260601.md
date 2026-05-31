# V4_RF_SHADOW_PROMOTION_DRYRUN_REPLAY_20260601

## 目标
Phase 3C 只做 RF shadow promotion 的 dryrun/replay 对比：
- current official 口径
- vs shadow dryrun 口径（基于 `rf_shadow_grade` / `market_adjusted_shadow_grade` / `recent5_bilateral_gate`）

本轮不是正式切换，不改 production 默认，不改 official grade。

## 本轮边界（强约束）
1. 不改变 official grade。
2. 不改变 production_grade_mode。
3. 不写 pending_bet_candidates。
4. 不推 QQ。
5. 不重算 validation。
6. 不修改 live bet。
7. 不修改 cron。
8. 不提交 runtime artifact。

## Dryrun 输出字段
- `shadow_dryrun_grade`
- `shadow_dryrun_score`
- `shadow_dryrun_reason`
- `shadow_dryrun_reason_code`
- `shadow_dryrun_source`
- `current_official_grade`
- `official_vs_shadow_delta`
- `promotion_delta_reason`
- `dryrun_allowed_to_promote`
- `dryrun_block_reason`

以上字段均为 dryrun/replay 观察字段，不进入 official 推荐链路。

## recent5 bilateral gate 口径
- 统计 `PASS / HOT_ANCHOR_PASS / DUAL_HEAT_PASS / FAIL`。
- `FAIL` 默认 `cap_to_C`，不直接 SKIP，不删 scout row。
- `RF_STRONG_CONFIRMED_B_FLOOR_EXCEPTION` 仅允许保 B，不允许升 A。

## 安全守卫
1. `MARKET_NO_DATA` 不升 A。
2. `MARKET_EXTREME_VETO` 必须 SKIP。
3. market/H2H/Events/CPL 不得制造 official A/B。
4. H2H 只做 add-only，不降级。
5. Events 不制造 A/B。
6. CPL 不影响 official。

## 产物与工具
- Runner: `tools/run_v4_rf_shadow_promotion_dryrun_replay.py`
- Checker: `tools/check_v4_rf_shadow_promotion_dryrun.py`
- Runtime artifact（不提交）：
  - `data/runtime/acceptance/v4_rf_shadow_promotion_dryrun_replay_<date>.json`
  - `data/runtime/acceptance/v4_rf_shadow_promotion_dryrun_replay_<date>.md`

## 结论口径
本阶段是 dryrun/replay 对比层，不是 official promotion。
后续若要接入正式 promotion，必须 BOSS 单独授权并经过 OpenClaw 验收。
