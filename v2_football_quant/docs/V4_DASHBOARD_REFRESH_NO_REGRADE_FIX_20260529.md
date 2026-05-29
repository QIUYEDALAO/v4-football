# V4_DASHBOARD_REFRESH_NO_REGRADE_FIX_20260529

## 结论
V4_DASHBOARD_REFRESH_NO_REGRADE_FIX_PASS

## Root Cause
- 12:00 正式 scan 产物 `scout_v4_20260529.json` 已有正式 grade（A=1/B=3）。
- 13:00 refresh 链路里，`tools/v3v4_dashboard_brief_resolver.py` 之前按 brief 解析 A/B；当 brief 解析不到或解释字段缺失时，会把 `candidate_view` 写成 A=0/B=0，覆盖正式 scan 结论。
- 同时 parallel adapter 写 scout entry 时把 `market_scores`/`factors` 写成空对象，放大了“解释层缺失→展示层误降级”的风险。

## 修复点
1. `tools/v3v4_dashboard_brief_resolver.py`
- 改为 **official grade 优先**：从 scout 的 `official_grade/grade` 作为唯一正式评级来源。
- brief/explain 仅补充展示字段，不允许覆盖 A/B/SKIP。
- 当 `market_scores`/`factors` 为空时：保留原 grade，并标记 `explain_factors_missing=true`、`official_grade_preserved=true`。
- 仅在 legacy 场景（完全无 official grade）才允许 fallback。

2. `engine/v4_scan_and_brief.py`
- parallel adapter 的 scout entry 现在尽量写入：
  `official_grade/market_scores/factors/score_pack/ht_score/h2h_score/recent_form_summary/source_trace/scoring_complete`。
- 缺失时不伪造评分，写缺失标志并保留 official grade。

3. 新增 checker
- `tools/check_v4_dashboard_refresh_no_regrade.py`
- 拦截 refresh 期“重算覆盖 official grade”。

## 结果验证（不重跑 scan）
- scout: A=1 / B=3（不变）
- candidate_view: A=1 / B=3（已恢复）
- control center model rebuild: PASS
- `tools/check_v4_dashboard_refresh_no_regrade.py`: PASS

## 强制约束确认
- 未重跑 scan
- 未重算 validation
- 未修改 live bet
- 未修改 cron
- 未修改 DEFAULT_RULES
- 未推 QQ 推荐

## Q&A
1. 13:00 是否曾重新计算 grade？
- 是，原 refresh 路径会按 brief 解析结果重写 candidate_view，等价于覆盖正式评级。

2. 空 market_scores/factors 是否导致 A/B 被覆盖成 SKIP？
- 会触发解释层缺失并放大覆盖风险；现在已改为缺失时保留 official grade。

3. 修复后 official grade 来源是什么？
- `scout_v4_YYYYMMDD.json` 的 `official_grade/grade`。

4. explain_match 是否还能覆盖 official grade？
- 不能。仅用于解释文案。

5. 20260529 dashboard 是否恢复 A=1/B=3？
- 是。

6. 是否重跑 scan？
- 否。

7. 是否重算 validation？
- 否。

8. 是否修改 live bet？
- 否。

9. 是否修改 cron？
- 否。

10. 是否修改 DEFAULT_RULES？
- 否。

11. 是否推 QQ 推荐？
- 否。
