# V4_AB_HISTORICAL_RECOMMENDATION_LEDGER_AND_POSTMATCH_ATTRIBUTION_20260526

## 执行结论
本轮已完成 official A/B 历史推荐账本、逐场赛后匹配、盘口结算模拟、分层归因、优化备注与 iPhone 页面生成。
未修改 V4 正式策略、未改候选评级/数量、未重写历史 validation。

## 核心结果
- 当前 A/B-only 累计基线（冻结源）：`A 28/46 · 60.9%`，`B 53/94 · 56.4%`，`A+B 81/140 · 57.9%`
- 昨日验证（页面口径）：`A 3/5 · 60.0%`，`B 3/5 · 60.0%`，`A+B 6/10 · 60.0%`
- 历史 official A/B 账本：140 场推荐（账本中可逐场查看 settled / pending / excluded）
- 输出页面：`/v4_ab_historical_ledger.html`

## 产物
- `data/runtime/status/v4_ab_ledger_current_baseline_freeze_20260526.json`
- `data/runtime/status/v4_ab_historical_official_recommendation_inventory_20260526.json`
- `data/runtime/status/v4_ab_historical_postmatch_matchup_20260526.json`
- `data/runtime/validation/v4_ab_historical_ledger_20260526.json`
- `data/runtime/validation/v4_ab_historical_ledger_20260526.csv`
- `data/runtime/status/v4_ab_historical_crown_ou_settlement_simulation_20260526.json`
- `data/runtime/status/v4_ab_historical_segment_attribution_20260526.json`
- `data/runtime/status/v4_ab_historical_optimization_notes_20260526.json`
- `data/runtime/dashboard/v4_ab_historical_ledger.html`
- `data/runtime/status/v4_ab_historical_ledger_checker_20260526.json`

## 13问答复
1. 当前 A/B-only 总命中率怎么样？
A+B 为 `81/140 · 57.9%`（冻结基线）。

2. 昨日命中率是否真的很差？
不是，昨日为 `6/10 · 60.0%`，属于中性偏上，不是极端差值。

3. 裸命中率和实盘盘口收益有什么区别？
裸命中率只看“有无进球”；盘口收益要区分 `WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS`，并叠加返水，收益结论可能与裸命中率不同。

4. 历史 official A/B 一共多少场？
账本汇总 140 场 official A/B 推荐。

5. A/B 分别表现如何？
基线：A `28/46`；B `53/94`。

6. 哪些盘口模拟最优？
本轮输出了 O0.75/O1/O1.25/O1.5 全量模拟，具体最优组合见 settlement simulation 文件中的 `aggregate`（按 line+odds+stake 场景）。

7. O0.75 / O1 / O1.25 / O1.5 哪些可做？
从模拟结果看，O0.75/O1 的稳健性通常优于 O1.25/O1.5；但仍需以分层样本与 shadow 观察为准，不直接改正式策略。

8. 哪些联赛值得观察？
在 `segment_attribution` 中已按 sample_count+ROI 列出。样本 >=20 的联赛优先观察。

9. 哪些联赛样本不足，不能下结论？
`confidence_level=OBSERVE_ONLY/LOW` 的联赛均不足以下正式结论。

10. 哪些脚本类型表现较好？
已在 `segment_attribution` 的 `script_type` 维度给出，建议优先查看 `HIGH/MEDIUM` 样本置信级别。

11. 哪些时间段表现较差？
已在 `kickoff_hour` 与 time-bin 维度输出，低样本段仅观察不下结论。

12. 哪些比赛需要人工复盘？
`optimization_tag` 为 `DATA_QUALITY / PENDING_RETRY / WATCH_LINE / WATCH_SCRIPT` 的场次优先人工复盘。

13. 是否有优化备注？
有，逐场输出到 `v4_ab_historical_optimization_notes_20260526.json`，但未触发正式规则变更。

14. 是否建议立即改策略？
不建议。先做 shadow test。

15. 是否需要 shadow test？
需要，建议以 100-200 场继续观测盘口净收益与回撤。

16. 是否修改了 V4 正式规则？
没有。

## 风险/说明
- 127 页面可访问；192 当前返回 503（内网链路状态），不影响本地账本生成。
- 历史链路中存在 pre-retry 与 post-retry 两种昨日口径文件；本轮账本保持来源可追溯并未伪造。

## 禁止项确认
- full_scan_ran=false
- capture_ran=false
- strategy_changed=false
- candidate_changed=false
- candidate_rating_changed=false
- result_validation_history_changed=false
- script_validation_history_changed=false
- brief_used_for_hit_rate=false
- scan_date_used_for_validation=false
- scout_full_pool_used=false
- outside_57_mixed_into_official=false
- live_bet_real_records_modified=false
- v2_restored=false
- v33_active=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- secrets_printed=false
- secrets_committed=false
