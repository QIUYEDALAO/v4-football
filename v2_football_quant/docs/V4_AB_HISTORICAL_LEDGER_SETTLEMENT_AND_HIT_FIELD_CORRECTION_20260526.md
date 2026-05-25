# V4_AB_HISTORICAL_LEDGER_SETTLEMENT_AND_HIT_FIELD_CORRECTION_20260526

## 结论
本轮已修复 AB 历史复盘页面的三类关键错误：
1. 盘口结算占位符未渲染；
2. `result_hit` 与 `ht_goal_count` 逻辑冲突；
3. 历史行 `league=UNKNOWN` 缺原因。

修复后：
- O0.75 / O1 / O1.25 / O1.5 均显示真实结算枚举；
- settled 行已满足 `ht_goal_count>=1 => result_hit=true`、`=0 => false`；
- pending 行 `result_hit=null`；
- script_hit 与 result_hit 已拆分并单独展示；
- UNKNOWN 联赛均附带 missing reason。

## 必答
1. 页面为什么出现结算占位符？
因为 HTML builder 把结算列写死为字符串 `{WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS}`，未按逐场计算结果渲染。

2. 为什么 HT进球>=1 却显示未命中？
旧实现混用了历史 `result_hit` 脏字段，且未强制按 `ht_goal_count` 重新计算。

3. 是否混用了 script_hit 和 result_hit？
是。已拆分：`result_hit`（按 HT 进球规则）与 `script_hit`（剧本验证）独立。

4. 已修正多少行命中字段？
见 `data/runtime/status/v4_ab_ledger_result_hit_recalc_20260526.json` 的 `changed_count`。

5. O0.75/O1/O1.25/O1.5 是否已真实结算？
是，已按规则逐场计算并写入 JSON/CSV/HTML。

6. UNKNOWN league 修复了多少？
见 `data/runtime/status/v4_ab_ledger_league_repair_20260526.json`（before/after）。

7. 当前 ledger 是否可用于盘口分析？
可用于诊断/回测分析（paper 模式，odds_source=paper_default_0.80）。

8. 当前 ledger 是否可用于优化备注？
可以，备注已基于修正后字段重算；但仍是建议观察，不直接改生产策略。

9. 是否改策略？
否。

10. 是否改 candidate？
否。

11. 是否重写 validation 历史？
否。

12. 是否污染 dashboard 主累计？
否，主累计 checker 通过。

13. 是否需要继续修 192 页面？
若 192 返回 503，仅属静态服务链路问题，建议后续单独修服务路由，不影响本轮数据修正。

14. 是否可以进入人工复盘阶段？
可以。

## 最终状态
V4_AB_LEDGER_SETTLEMENT_HIT_FIELD_CORRECTION_PASS

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
