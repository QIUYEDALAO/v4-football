# Phase 3B: V4_RF_SHADOW_GRADE (2026-06-01)

## 目标
本阶段建设 RF shadow grade 层，在不改变 official 推荐出口的前提下，输出可解释的影子评分链路。

## 范围与红线
- 只做 shadow grade 与解释字段。
- 不修改 official grade 逻辑。
- 不修改 production_grade_mode。
- 不修改 pending / QQ / cron / validation / live bet。
- 不把 shadow grade 作为正式推荐。

## 输入基础（来自 Phase 3A）
- `collection_stage`
- `rf_collected` / `market_collected` / `prefilter_done`
- `h2h_required` / `h2h_skipped_reason` / `h2h_collected`
- `events_required` / `events_skipped_reason` / `events_collected`
- `cpl_required` / `cpl_skipped_reason` / `cpl_collected`
- `expensive_calls_saved` / `collection_reason`

## RF Shadow 输出
- `rf_shadow_score`
- `rf_shadow_grade`
- `rf_shadow_reason`
- `rf_shadow_reason_code`
- `rf_primary_signal_level`
- `rf_recent10_signal`
- `rf_recent5_signal`
- `rf_freshness_signal`
- `rf_balance_signal`
- `rf_collection_stage_used`

说明：RF 仍是主因子，recent10/recent5/freshness/balance 必须可解释，缺失字段使用安全默认，不输出 undefined/null/NaN。

## RECENT5_BILATERAL_HEAT_GATE
### 设计目的
- `recent10 >= 7/10` 仅表示入池，不等价于稳定 B。
- 稳定 B 需要近5双边热度确认。

### 通过模式
1. `HOT_ANCHOR_PASS`：任意一队 `recent5=5/5` 且另一队 `recent5>=3/5`。
2. `DUAL_HEAT_PASS`：双方 `recent5>=4/5`。

### 未通过处理
- `recent5_bilateral_gate=FAIL` 时默认 `cap_to_C`。
- 不直接 SKIP，不删除 scout row，不影响 collection pipeline。

### 例外保护
- 保留 `RF_STRONG_CONFIRMED_B_FLOOR_EXCEPTION`：
  在 `rf_score>=73`、`recent10>=7/10`、强驱动/可接受平衡、市场确认、`ACTIVE_SEASON`、非 `TIER_4_NON_FORMAL`、非 `MARKET_EXTREME_VETO`、非 baseline-only、非 `MARKET_NO_DATA` 升A场景时，允许从 gate FAIL 保留 B（仅保 B，不升 A）。

### 新增字段
- `recent5_bilateral_gate`
- `recent5_bilateral_gate_mode`
- `recent5_bilateral_gate_reason`
- `home_recent5_pass_count`
- `away_recent5_pass_count`
- `recent5_hot_anchor_team`
- `recent5_other_side_count`
- `recent5_dual_heat_pass`
- `recent5_bilateral_gate_cap_action`
- `recent5_bilateral_gate_exception_used`

## Market 调整输出
- `market_adjusted_shadow_grade`
- `market_adjusted_shadow_reason`
- `market_policy_action`
- `market_veto_status`
- `market_risk_flag`

规则：
- Market 只做确认/降级/风险提示/极端 veto。
- `MARKET_NO_DATA` 不得升 A。
- `MARKET_EXTREME_VETO` 直接 SKIP。
- 不恢复旧式 `MARKET_HARD_VETO` 一刀切。
- Market 不得单独制造 A/B。

## H2H / Events / CPL 解释层
- `h2h_bonus_status` / `h2h_bonus_reason`
- `time_bin_shadow_status` / `playbook_script`
- `cpl_shadow_status` / `cpl_shadow_reason`

规则：
- H2H add-only，不降级，不制造 A/B。
- H2H_LOW_SAMPLE 只标注。
- Events/Time Bin 只解释候选，不制造 A/B。
- CPL 仅 shadow placeholder，不进入 official，不触发 live bet / validation / QQ。

## Dashboard 映射
`tools/build_v4_control_center_model.py` 已映射以上 shadow 字段，保持 False 语义，不把 False 误写为 UNKNOWN。

## 验证
关键 checker：
- `tools/check_v4_rf_shadow_grade.py`
- `tools/check_v4_collection_pipeline_redesign_shadow.py`
- `tools/check_v4_season_aware_production_switch.py`
- `tools/check_v4_qq_enabled_gate.py`
- `tools/check_v4_production_default_rules_guard.py`

## 结论
本阶段是 shadow grade 层建设，不代表 production promotion。后续如需正式提升 shadow 到 official，必须另行 BOSS 单独授权。

## Phase 3F 调优补充（Shadow-only）
- recent5 gate 保留，不取消。
- 对 gate FAIL 增加最小救援：`RECENT5_BILATERAL_GATE_FAIL_BUT_RF_STRONG_CONFIRMED_RESCUE`、`RECENT5_FAIL_HIGH_RF_STRONG_MARKET_RESCUE_TO_B`。
- 救援只允许 `C -> B`，不允许 `-> A`。
- `TIER_4_NON_FORMAL`、`MARKET_EXTREME_VETO`、`POST_OFFSEASON_RETURN/baseline-only`、`MARKET_NO_DATA` A 风险场景必须阻断。
- 本补充仅作用 shadow/dryrun，不改变 official/pending/QQ/validation/live bet/cron。
