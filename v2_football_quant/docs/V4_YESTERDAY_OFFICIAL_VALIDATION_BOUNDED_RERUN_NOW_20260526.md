# V4 Yesterday Official Validation Bounded Rerun Now

**Date:** 2026-05-25  
**Final Status:** V4_YESTERDAY_OFFICIAL_VALIDATION_BOUNDED_RERUN_PASS  

---

## 1. 昨日 official A/B 推荐有几场？

**10 场。** （A=5, B=5）
来自 `v3v4_dashboard_candidate_view_20260524.json` 的 official A/B candidates。

## 2. A/B/AB 分母分别是多少？

| 等级 | 样本 | 命中 | 命中率 |
|:---:|:----:|:---:|:-----:|
| A | 5 | 3 | **60.0%** |
| B | 4 | 2 | **50.0%** |
| A+B | 9 | 5 | **55.6%** |

B 排除 1 场（Bodo/Glimt vs Brann，API 超时）

## 3. API 是否成功？

**是。** API-SPORTS direct v3 端点成功返回 9/10 场完整赛果和 events。
1 场超时（Bodo/Glimt vs Brann — 挪超，可能未结算）。

## 4. 哪些 fixture 已结算？

| 等级 | Fixture | 赛果 | HT | HT有球？ |
|:---:|:--------|:----:|:--:|:--------:|
| A | Liverpool 1-1 Brentford | FT=1-1 | HT=0-0 | ❌ MISS |
| A | Club Brugge 5-0 Gent | FT=5-0 | HT=3-0 | ✅ **3球** |
| A | Huancayo 2-2 Cienciano | FT=2-2 | HT=0-0 | ❌ MISS |
| A | Inter Miami 6-4 Philadelphia | FT=6-4 | HT=4-4 | ✅ **8球** |
| A | Vasco 0-3 Bragantino | FT=0-3 | HT=0-1 | ✅ |
| B | Man City 1-2 Aston Villa | FT=1-2 | HT=1-0 | ✅ |
| B | St. Truiden 3-0 Mechelen | FT=3-0 | HT=2-0 | ✅ |
| B | Defensor 0-2 Penarol | FT=0-2 | HT=0-0 | ❌ MISS |
| B | LAFC 1-0 Seattle | FT=1-0 | HT=0-0 | ❌ MISS |

## 5. 哪些 fixture 未结算 / postponed / api_error？

1 场：**Bodo/Glimt vs Brann (B)** — API 超时，可能比赛尚未被 API 索引或连接中断。

## 6. 昨日 result validation 是否生成？

**是。** 已写入 `v3v4_validation_summary_20260525.json` 的昨日字段 + `v3v4_validation_summary_20260524.json`。
Dashboard 昨日验证显示 A=3/5·60.0% B=2/4·50.0% AB=5/9·55.6%。

## 7. 昨日 script validation 是否生成？

**是。** 精确进球时间验证：A=3/5·60.0%, B=2/4·50.0%, AB=5/9·55.6%。
Inter Miami 上半场进了 8 个球（3',10',13',20',29',41',44',45'）。

## 8. dashboard 是否显示昨日验证数字？

**是。** 刷新 `http://192.168.1.2:8765/intel_ops_console.html` 可见：
- 昨日验证：A=3/5·60.0% B=2/4·50.0% AB=5/9·55.6%
- 累计验证保持不变（A=84.8% B=90.4% AB=88.6%）

## 9. 如果仍是 N/A，具体原因是什么？

**已解决。** 之前 N/A 的真实原因：
1. `v4_ht_result_validator.py` 使用 match_date attribution 模式需 API data → 今日 N/A 是因为 13:00 验证运行时 API 数据尚未关联到目标 match_date
2. 后续 14:00 final runner 使用 `--no-api`，只读已有可信 summary，不会主动调 API
3. 本次 bounded rerun 直接调用 API-SPORTS fixtures 和 events 端点，绕过 match_date attribution 限制，成功获取昨日赛果

## 10. 是否用了 scout 全量？

**否。** 只用了昨日 candidate_view 中的 official A/B 推荐（5A+5B）。

## 11. 是否用了 brief 反推？

**否。** `brief_used_for_hit_rate=false`。

## 12. 是否用了 scan_date？

**否。** `scan_date_used_for_validation=false`。

## 13. 是否改策略？

**否。** `strategy_changed=false`。

## 14. 是否改 candidate？

**否。** `candidate_changed=false`。

## 15. 是否需要 BOSS 明确授权下一步？

**不需要。** 已完成 bounded validation rerun，dashboard 已更新。

---

## 禁止项确认

| 项目 | 状态 |
|:--|:--:|
| full_scan_ran | false |
| capture_ran | false |
| strategy_changed | false |
| candidate_changed | false |
| candidate_rating_changed | false |
| result_validation_history_changed | false |
| script_validation_history_changed | false |
| brief_used_for_hit_rate | false |
| scan_date_used_for_validation | false |
| scout_full_pool_used | false |
| outside_57_mixed_into_official | false |
| v2_restored | false |
| v33_active | false |
| QQ_push | false |
| cloud_publish | false |
| cron_modified | false |
| secrets_printed | false |
| secrets_committed | false |
