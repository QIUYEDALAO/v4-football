# V4 RF-SA-4: Season-Aware Shadow Grade Integration (2026-05-31)

## 1. 范围声明
本轮为 **RF-SA-4**，只做 season-aware recent form 结果接入 shadow grade / dryrun。

允许变化：
- `rf_shadow_grade`
- `market_adjusted_shadow_grade`
- promotion dryrun 的 `A/B/C/SKIP`

禁止变化：
- official grade / official_legacy
- validation / QQ / cron / live bet / pending_bet_candidates
- API 调用、全量重扫、live no-push 扫描

## 2. 设计目标
将 RF-SA-3 的 season-aware字段接入 shadow评分：
- `season_phase`
- `league_tier`
- `rf_window_policy`
- `rf_sample_status`
- `rf_freshness_status`
- `rf_early_season_penalty`
- `rf_short_break_penalty`
- `rf_baseline_only_flag`
- `last_season_baseline_available`
- `last_season_baseline_score`

并输出可解释字段：
- `season_aware_shadow_grade_before`
- `season_aware_shadow_grade_after`
- `season_aware_shadow_applied`
- `season_aware_shadow_action`
- `season_aware_shadow_reason`

## 3. Season-Aware Shadow 行为
- ACTIVE_SEASON：60天主窗口可正常作为 shadow 信号。
- SHORT_BREAK：90天 fallback 可用，但必须 penalty，限制强等级。
- EARLY_SEASON：样本不足时限制 A 或强信号（降为 B/C）。
- POST_OFFSEASON_RETURN：仅 baseline 参考，不允许 baseline 单独制造强 A。
- OFFSEASON：保守处理，偏向 C/SKIP。
- UNKNOWN：安全默认，禁止强行升格。

联赛层级：
- TIER_1_ELITE / TIER_2_MAINSTREAM：正常 shadow 解释。
- TIER_3_WEAK_COVERAGE：保守限制强信号。
- TIER_4_NON_FORMAL：禁止强 shadow grade。
- UNKNOWN_TIER：安全默认。

## 4. Market Policy 合流边界
RF season-aware 后的 shadow grade 进入 market policy：
- 保留 `MARKET_LIGHT_CONFLICT / MARKET_STRONG_CONFLICT / MARKET_EXTREME_VETO` 分层。
- 仅 `MARKET_EXTREME_VETO` 允许直接 SKIP。
- `MARKET_NO_DATA` 不允许升 A，但强 RF 可保留 B/C 观察。
- 不恢复 `MARKET_HARD_VETO` 一刀切旧逻辑。

## 5. H2H 边界
- H2H 维持加分项定位。
- `H2H_LOW_SAMPLE` 只标注，不做降级硬杀。
- H2H 不单独制造 A/B。

## 6. Dryrun 口径
promotion dryrun 允许输出 season-aware 变化：
- 可改变 dryrun A/B/C/SKIP
- 必须提供 reason / action / delta
- 必须明确是 shadow/dryrun，不是 official 推荐

## 7. 本轮实施点
代码：
- `engine/rf_shadow_fields.py`
- `tools/build_v4_control_center_model.py`
- `tools/build_v4_rf_shadow_to_official_promotion_dryrun.py`
- `tools/check_v4_rf_season_aware_shadow_grade_integration.py`（新增）

## 8. 安全边界结果
本轮校验目标：
- official grade unchanged
- no validation recompute
- no pending write
- no live bet mutation
- no QQ push
- no cron change
- no API call
- no runtime artifact commit

## 9. 后续阶段边界
- RF-SA-5：Replay Acceptance（下一阶段）
- RF-SA-6：Live Shadow Acceptance（后续）
- RF-SA-7：Promotion Policy Review（后续）

RF-SA-4 本轮不进入上述阶段结论。
