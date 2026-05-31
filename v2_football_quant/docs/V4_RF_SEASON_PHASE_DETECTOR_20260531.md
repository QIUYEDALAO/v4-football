# V4 RF Season Phase Detector (RF-SA-2)

## 1. 目标与边界
- 目标：增强 `season_phase`、`league_tier`、`current_season_match_count` 的 detector 稳定性、可解释性与可回放性。
- 仅影响 shadow detector 字段层，不改变评分链路。
- 不调用 API，不执行全量重扫，不触碰 validation / live bet / QQ / cron。

## 2. 本轮不做
- 不做 RF-SA-3（recent form window refactor）。
- 不做 RF-SA-4（shadow grade integration）。
- 不改 `rf_shadow_grade`、`market_adjusted_shadow_grade`。
- 不改 dryrun A/B/C/SKIP 规则，不改 official grade。

## 3. Detector 输入（本地可得）
- recent10/5 样本计数与时间跨度：`recent10_sample_count_*`、`recent10_window_days_*`。
- recent60/90 估算计数：由 recent10 样本窗口换算。
- 最近正式比赛间隔：`days_since_last_official_match_home/away`（由 recent 样本最后比赛时间与 kickoff 估算）。
- 本赛季比赛数估算：`current_season_match_count_home/away`（优先 record，缺失回退 recent60）。
- 联赛信息：`league_name`、`country`、`league_type`。
- season payload（如存在）：`season_phase_payload`。

## 4. season_phase 状态机
支持并只输出以下枚举：
- `ACTIVE_SEASON`
- `SHORT_BREAK`
- `EARLY_SEASON`
- `POST_OFFSEASON_RETURN`
- `OFFSEASON`
- `UNKNOWN`

判定原则（保守优先）：
- `TIER_4_NON_FORMAL` 直接 `UNKNOWN`（避免友谊赛/U系列误判活跃赛季）。
- payload 可用且合法时优先使用。
- `current_season_match_count` 在 1-5：
  - gap 长 → `POST_OFFSEASON_RETURN`
  - gap 不长 → `EARLY_SEASON`
- recent10 窗口短且样本足且近期活跃 → `ACTIVE_SEASON`
- 短间歇信号（窗口 61-90 或 gap 信号）→ `SHORT_BREAK`
- 长间歇且 recent90 极低 → `OFFSEASON`
- 其余不确定 → `UNKNOWN`

## 5. league_tier detector
支持并只输出以下枚举：
- `TIER_1_ELITE`
- `TIER_2_MAINSTREAM`
- `TIER_3_WEAK_COVERAGE`
- `TIER_4_NON_FORMAL`
- `UNKNOWN_TIER`

规则：
- 五大联赛/主流顶级赛事识别为 `TIER_1_ELITE`（shadow-only 语义，不制造 A/B）。
- 主流二级覆盖联赛识别为 `TIER_2_MAINSTREAM`。
- 友谊赛/U系列/明显非正式赛事严格降级到 `TIER_4_NON_FORMAL`。
- 无法判断时返回 `UNKNOWN_TIER`。

## 6. current_season_match_count 识别
- 新增本地估算：
  - `days_since_last_official_match_home/away`
  - `current_season_match_count_home/away`
- 优先使用 record 已有值；缺失时回退 recent60 估算。
- 不把旧赛季样本直接当作本赛季强信号。
- 与 `EARLY_SEASON` / `POST_OFFSEASON_RETURN` 语义分离。

## 7. 新增 reason code（shadow-only）
- `season_phase_reason_code`
- `league_tier_reason_code`
- `current_season_count_reason_code`

说明：
- reason code 只用于解释 detector 决策与回放审计。
- 不参与评分，不参与 official/dryrun评级决策。

## 8. 字段映射范围
- scout：由 detector 输出提供（新产物可携带 reason code）。
- dashboard model builder：透传 reason code，缺失时 `UNKNOWN_REASON` 安全默认。
- promotion dryrun artifact：透传 reason code 并输出分布统计。
- checker：校验 phase/tier 枚举、数值安全、reason code 输出链路。

## 9. 安全默认
- `UNKNOWN`、`UNKNOWN_TIER`、`UNKNOWN_REASON` 为合法安全默认。
- 严禁输出 `undefined` / `null` / `NaN`。

## 10. 与后续阶段边界
- RF-SA-3 才处理窗口重构，不在本轮。
- RF-SA-4 才讨论 shadow grade integration，不在本轮。
- 本轮结果不可视为生产评分切换。
