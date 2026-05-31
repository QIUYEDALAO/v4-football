# V4 RF Season-Aware Recent Form Window Refactor (RF-SA-3)

## 1. 范围与边界
- 本轮是 **RF-SA-3: Recent Form Window Refactor**。
- 本轮不是 RF-SA-4（Shadow Grade Integration）。
- 仅增强 season-aware window selector 与 baseline separation 的 shadow 字段逻辑。
- 不改 `rf_shadow_grade`、`market_adjusted_shadow_grade`、dryrun A/B/C/SKIP、official grade。

## 2. 核心改动
### 2.1 ACTIVE_SEASON：60天主窗口
- `rf_window_policy = D60_PRIMARY`。
- `recent10_used_count_*` 基于 `recent60_match_count_*` 选择，不再默认全部 recent10。
- `recent10_window_days_*` / `recent5_window_days_*` 按已选样本比例缩放。

### 2.2 SHORT_BREAK：90天fallback + penalty
- `rf_window_policy = D90_SHORT_BREAK_FALLBACK`。
- 允许使用 `recent90_match_count_*` 作为 fallback。
- 强制 `rf_short_break_penalty = true`，并通过 `rf_season_aware_reason` 与 reason code 记录。
- SHORT_BREAK 不等同 ACTIVE_SEASON。

### 2.3 EARLY_SEASON：样本限制语义
- `rf_window_policy = D60_EARLY_GUARD`。
- `recent10_used_count_*` 受 `current_season_match_count_*` 限制。
- 强制 `rf_early_season_penalty = true`。

### 2.4 POST_OFFSEASON_RETURN / OFFSEASON：baseline separation
- `rf_window_policy = BASELINE_ONLY`。
- `rf_baseline_only_flag = true`。
- `recent10_used_count_*` 保守限制（最多2），避免旧赛季样本伪装成本赛季强信号。
- `last_season_baseline_*` 仅保留为 shadow baseline 参考，不接入评级决策。

### 2.5 OFFSEASON / UNKNOWN 安全默认
- OFFSEASON 与 UNKNOWN 均保持保守语义。
- UNKNOWN 不强行升格 ACTIVE_SEASON。
- 全路径禁止 `undefined / null / NaN`。

## 3. league_tier 与 non-formal safety
- `TIER_3_WEAK_COVERAGE` 保守处理，不提升强信号资格。
- `TIER_4_NON_FORMAL`（友谊赛/U系列/非正式）强制防误判，避免 ACTIVE_SEASON 强解释。
- `UNKNOWN_TIER` 保持安全默认。

## 4. 字段与映射
RF-SA-3 关键字段继续进入以下层：
- scout 字段层（由 detector 产出）
- dashboard model builder（只读展示）
- promotion dryrun artifact builder（只读统计）
- checker 可读层

关键字段：
- `season_phase`
- `league_tier`
- `rf_window_policy`
- `recent60_match_count_home/away`
- `recent90_match_count_home/away`
- `recent10_used_count_home/away`
- `recent5_used_count_home/away`
- `recent10_window_days_home/away`
- `recent5_window_days_home/away`
- `current_season_match_count_home/away`
- `days_since_last_official_match_home/away`
- `last_season_baseline_available`
- `last_season_baseline_score`
- `rf_baseline_only_flag`
- `rf_sample_status`
- `rf_freshness_status`
- `rf_early_season_penalty`
- `rf_short_break_penalty`
- `rf_season_aware_reason`

## 5. reason code 与可解释性
沿用并增强 reason code：
- `season_phase_reason_code`
- `league_tier_reason_code`
- `current_season_count_reason_code`

这些字段只用于 shadow 检测解释，不参与 official/dryrun评级。

## 6. 本轮不变项
- 不影响 `rf_shadow_grade`。
- 不影响 `market_adjusted_shadow_grade`。
- 不影响 dryrun A/B/C/SKIP 规则。
- 不影响 official grade。
- 不影响 validation / QQ / cron / live bet。
- 不调用 API，不执行全量重扫，不执行 no-push live scan。

## 7. 与 RF-SA-4 边界
- RF-SA-3 仅完成 window refactor。
- RF-SA-4 才允许讨论 shadow grade integration。
