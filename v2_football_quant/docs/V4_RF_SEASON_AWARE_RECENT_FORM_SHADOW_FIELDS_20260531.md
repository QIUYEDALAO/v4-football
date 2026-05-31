# V4 RF Season-Aware Recent Form Shadow Fields (2026-05-31)

## 1. 本轮目标
本轮只新增 **season-aware recent form 影子字段层**，用于可观测与后续评估，不做正式评分切换。

范围：
- 新增/透传字段到 scout
- 字段进入 dashboard model
- 字段进入 promotion dryrun artifact
- 新增专项 checker

非目标：
- 不改变 `rf_shadow_grade`
- 不改变 `market_adjusted_shadow_grade`
- 不改变 dryrun A/B/C/SKIP 规则
- 不改变 official grade
- 不进入 validation / live bet / QQ

## 2. 新增字段（影子层）

### 2.1 基础字段
- `season_phase`
- `league_tier`
- `rf_window_policy`
- `recent60_match_count_home`
- `recent60_match_count_away`
- `recent90_match_count_home`
- `recent90_match_count_away`
- `recent10_used_count_home`
- `recent10_used_count_away`
- `recent5_used_count_home`
- `recent5_used_count_away`
- `recent10_window_days_home`
- `recent10_window_days_away`
- `recent5_window_days_home`
- `recent5_window_days_away`
- `current_season_match_count_home`
- `current_season_match_count_away`
- `days_since_last_official_match_home`
- `days_since_last_official_match_away`

### 2.2 baseline 字段
- `last_season_baseline_available`
- `last_season_baseline_score`
- `rf_baseline_only_flag`

### 2.3 状态字段
- `rf_sample_status`
- `rf_freshness_status`
- `rf_early_season_penalty`
- `rf_short_break_penalty`
- `rf_season_aware_reason`
- `rf_season_adjusted_shadow_grade`

## 3. best-effort 约束
- `season_phase` 采用保守 best-effort 判定。
- `league_tier` 采用保守映射（精英/主流/弱覆盖/非正式/未知）。
- 数据不足时允许 `UNKNOWN` / `UNKNOWN_TIER`。
- `UNKNOWN` 是安全默认，不是错误。
- 所有字段禁止 `undefined/null/NaN`。

## 4. 严格不改评分（本轮）
本轮实现严格遵守：
1. 不覆写 `rf_shadow_grade`。
2. 不覆写 `market_adjusted_shadow_grade`。
3. 不改变 promotion dryrun 的 A/B/C/SKIP 规则。
4. 不改变 official grade。
5. 不写 pending_bet_candidates。
6. 不改 validation / live bet / QQ。

## 5. 链路透传
- Scout: season-aware 字段已落盘。
- Dashboard Model: 字段已透传并提供安全默认。
- Promotion Dryrun Artifact: 字段已透传，并新增分布摘要。

## 6. 验证结果
- `check_v4_rf_season_aware_recent_form_shadow_fields.py`：PASS
- `check_v4_rf_promotion_market_veto_policy.py`：PASS
- `check_v4_rf_shadow_to_official_promotion_dryrun.py`：PASS
- `check_v4_production_default_rules_guard.py`：PASS
- `check_v4_control_center.py`：WARN_ONLY（candidate_items_empty，非阻断）

## 7. 本轮结论
本轮完成的是 **Season-Aware RF Shadow Fields Layer**，属于字段层冻结后的第一步落地。

尚未做且本轮明确禁止：
- 未启用 season-aware 正式评分
- 未做窗口重构的正式判级切换
- 未改 cron / DEFAULT_RULES / official grade

下一阶段才会在 BOSS 单独授权下讨论“窗口重构对 shadow 评分”的接入。
