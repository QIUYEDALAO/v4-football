# V2/V4 Yesterday & Rolling Validation Dashboard — Completion Report 20260520

**Phase:** V2-V4-YESTERDAY-AND-ROLLING-VALIDATION-DASHBOARD-20260520
**Generated:** 2026-05-20T20:00:00+08:00
**Conclusion:** PASS

---

## Step Results

### Step 1 — Data Source Audit
**PASS**

V2 sources identified: v2_bet_locked_proof_freeze, v2_settlement_preflight, v2_daily_status_push (17-18), v2_daily_pool_summary
V4 sources identified: v4_review_structured, v4_ht_recommend_validation, v4_result_attribution (JSONL), scout_v4, v4_evening_current_freeze

### Step 2 — Yesterday Validation (2026-05-19)
**PASS**

| Metric | V2 | V4 |
|:---|:---|:---|
| Formal count | 0 BET_LOCKED | 3 (A=0 B=3) |
| Hit / Miss / Unknown | 0 / 0 / 0 | 0 / 0 / 3 |
| Hit rate | 样本不足 | 样本不足 |
| C / SKIP | - | 13 / 8 |

V2: 无BET_LOCKED投注记录。V4: 24场比赛已归因，其中3场B级正式候选结果未知。

### Step 3 — Rolling Validation
**PASS**

V2 Rolling (7/14/30d): 0 BET_LOCKED — **样本不足，无正式投注记录**
V4 Rolling (7/14/30d): 133 formal candidates, hit=75, miss=55, unknown=3 — **命中率 56.4%**

Data source: 8 days of v4_result_attribution JSONL files (2026-05-12 to 2026-05-19).

### Step 4 — Dashboard Updated
**PASS** — Two new main modules inserted before candidate cards:

1. **昨日验证** — V2 BET_LOCKED + V4 A/B formal, with scope notes
2. **滚动验证** — V2 + V4 7/14/30 day rolling tables

NOT in audit section. Visible on main page above candidate list.

### Step 5 — Checker
**PASS** — tools/check_v2_v4_validation_dashboard.py: 10/10 PASS

### Step 6 — Verification
**PASS** — All 5 checkers PASS, 105 total checks

| Checker | Status | Checks |
|:---|:---|:---|
| v2_v4_validation_dashboard | PASS | 10/10 |
| v4_script_goal_distribution | PASS | 11/11 |
| chinese_ux | PASS | 13/13 |
| ops_console | PASS | 19/19 |
| routes (HTTP) | PASS | 52/52 |

---

## 10 Questions Answered

1. **昨日验证是否显示？** 是。首页可见，位于候选列表上方。
2. **V2是否只统计 BET_LOCKED？** 是。明确标注"只统计BET_LOCKED，WATCH/CANDIDATE不计入"。
3. **V4是否只统计 A/B？** 是。明确标注"只统计A/B，C/SKIP不计入命中率"。
4. **C/SKIP是否排除？** 是。C观察和SKIP单独列出，不计入命中率计算。
5. **V2滚动验证是否显示？** 是。7/14/30日三个周期，标注"样本不足"。
6. **V4滚动验证是否显示？** 是。7/14/30日三个周期，命中率56.4%。
7. **样本不足是否正确提示？** 是。V2显示"样本不足：无正式投注记录"。
8. **是否伪造赛果？** 否。所有数据来自真实attribution JSONL文件（24条/天，共8天）。
9. **是否运行 capture？** 否。
10. **是否真实推 QQ？** 否。

---

## 禁止项确认

| Item | Status |
|:---|:---|
| capture_ran | false |
| V4_QQ_ENABLED | false |
| QQ_sent | false |
| D13 | false |
| V33 | false |
| HOURLY | false |
| cron_modified | false |
| strategy_changed | false |
| fabricated_results | false |

## Deliverables

- data/runtime/status/validation_yesterday_20260519.json
- data/runtime/status/rolling_validation_summary_20260520.json
- data/runtime/status/v2_v4_validation_source_audit_20260520.json
- tools/check_v2_v4_validation_dashboard.py
- data/runtime/dashboard/intel_ops_console.html (updated with validation modules)
- docs/V2_V4_YESTERDAY_AND_ROLLING_VALIDATION_DASHBOARD_20260520.md
