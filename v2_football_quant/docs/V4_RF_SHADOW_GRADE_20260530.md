# V4_RF_SHADOW_GRADE_20260530

## 目标
本轮实现 Phase 3B 的 **RF Shadow Grade** 代码层，不改 official grade，不切换正式规则，不进入 Phase 4/5/6。

## 本轮新增字段
- `rf_shadow_grade`
- `rf_shadow_score`
- `rf_shadow_route`
- `rf_shadow_reason`
- `rf_shadow_confidence`
- `rf_entry_rule`
- `rf_recent10_gate_status`
- `rf_recent5_grade_status`
- `rf_heating_exception`
- `rf_heating_exception_reason`
- `rf_balance_status`
- `rf_balance_driver_side`
- `rf_balance_driver_level`
- `rf_balance_weak_side_status`
- `rf_balance_adjustment`
- `rf_balance_reason`
- `h2h_recent5_fh_involved_count`
- `h2h_recent5_sample_count`
- `h2h_recent5_support_status`
- `h2h_recent5_bonus_level`
- `h2h_recent5_bonus_reason`
- `opening_market_support_status`
- `opening_market_confirm_level`
- `opening_market_veto_level`
- `opening_market_reason`
- `opening_market_data_status`
- `market_adjusted_shadow_grade`
- `market_adjustment_reason`

## RF-10G7-5M 规则
- 近10 `>=7/10`：正常入池。
- 近5 `5/5`：A 基础。
- 近5 `4/5`：B 基础。
- 近5 `3/5`：C 观察。
- 近10 `6/10 + 近5 5/5`：B 破格。
- 近10 `5/10 + 近5 5/5`：C 观察。
- 近10 `<=4/10`：不进 A/B shadow。

## Team Balance 规则
- 启用强侧驱动 + 弱侧保底逻辑，替代 `min(home,away)` 一刀切。
- 关键场景：主队 `7/10 + 5/5`，客队 `6/10 + 3/5`。
  - `rf_balance_driver_side=HOME`
  - `rf_balance_driver_level=HOT_DRIVER`
  - `rf_balance_weak_side_status=ACCEPTABLE`
  - 输出 `B` shadow，不直接 SKIP。

## H2H recent5 bonus-only
- H2H 只做加分/说明，不做降级。
- weak/no-bonus 不降级。
- strong bonus 不单独制造 A/B。

## Opening Market confirm/veto
- 仅用初盘。
- 盘口不能单独制造 A/B。
- `MARKET_HARD_VETO` 只影响 shadow（`market_adjusted_shadow_grade`），不影响 official grade。
- `MARKET_NO_MARKET` 仅 shadow 标注，不改 official 评分链路。

## 透传范围
- 已透传到 scout / candidate_view / dashboard model。
- dashboard 增加 shadow 解释折叠展示，不替代 official grade 展示。

## no-regrade 约束
- 不改 `grade` / `official_grade`。
- 不改 DEFAULT_RULES。
- 不改 A/B 阈值。
- 不改 H2H runtime 正式判级含义。

## 自检范围（轻量）
- 语法编译（`py_compile`）。
- 规则样例单测（含 HOT_DRIVER+ACCEPTABLE => B，6/10+5/5 => B，5/10+5/5 => C）。
- checker 源码级验证（`tools/check_v4_rf_shadow_grade.py`）。
- 未执行正式入口长耗时 dry-run 验收。

## 重要说明
- 本文档仅声明 **CODE_READY**，不是运行态 PASS。
- 正式运行态验收（whitelist serial no-push dry-run 与产物核对）由 **OpenClaw** 单独执行。
