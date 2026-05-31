# V4_RECENT5_GATE_BFLOOR_RESCUE_TUNING_20260601

## 目标
本轮为 Phase 3F：仅在 shadow/dryrun 层调优 `RECENT5_BILATERAL_HEAT_GATE` 与 `RF_STRONG_CONFIRMED_B_FLOOR_EXCEPTION`，减少不合理 B→C 压制。

本轮不是 promotion 上线，不是 official 切换，不是 QQ 推送。

## 调整原则
1. recent5 gate 继续保留，不取消。
2. 只允许在 high RF + strong market + safe boundary 下做 C→B rescue。
3. rescue 只能到 B，不能升 A。
4. TIER_4 / MARKET_EXTREME_VETO / baseline-only 必须阻断 rescue。
5. MARKET_NO_DATA 场景不能用于 A 升级。
6. 不改 official grade，不写 pending，不推 QQ。

## 新增/强化字段
- `recent5_rescue_to_B`
- `recent5_rescue_reason`
- `recent5_rescue_block_reason`
- `bfloor_rescue_to_B`
- `bfloor_rescue_reason`
- `bfloor_rescue_block_reason`

## Replay 新增统计
- `recent5_rescue_to_B_count`
- `bfloor_rescue_to_B_count`
- `rescue_to_A_count`
- `rescue_blocked_tier4_count`
- `rescue_blocked_extreme_veto_count`
- `rescue_blocked_baseline_only_count`
- `rescue_blocked_market_no_data_A_count`
- `b_to_c_before / b_to_c_after`
- `b_to_b_before / b_to_b_after`
- `shadow_dryrun_grade_before_tuning / shadow_dryrun_grade_after_tuning`

## Phase 3F-N 命名清理（market rescue 字段）
为避免把“合法救援”误记为“非法制造”，新增并固定以下口径：

- `market_assisted_rescue_to_B_count`：合法（RF 强 + market confirm 下的 C→B rescue）。
- `market_assisted_rescue_to_B_list`：合法 rescue 的 fixture_id 列表。
- `market_alone_manufactured_AB_count`：非法（仅靠 market 制造 A/B）计数。
- `market_alone_manufactured_AB_list`：非法制造 fixture_id 列表。
- `market_rescue_safety_status`：`CLEAN`/`VIOLATION`。
- `market_rescue_naming_status`：`RENAMED_SPLIT_ACTIVE`。

旧字段 `market_manufactured_AB_found` 仅保留为 deprecated alias，禁止继续作为 safety violation 判断依据。

## 安全红线
1. official grade 不变。
2. production_grade_mode 不变。
3. pending 逻辑不变。
4. QQ 不推送。
5. validation 不重算。
6. live bet 不修改。
7. cron 不修改。
8. DEFAULT_RULES 与 A/B 阈值不改。

## 结论
本轮仅 shadow tuning。
是否进入 promotion 或 official 切换，仍需 BOSS 后续单独授权与 OpenClaw 验收。
