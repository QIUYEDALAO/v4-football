# V4 Script & Goal-Time Distribution Fix — Completion Report 20260520

**Phase:** V4-SCRIPT-AND-GOAL-TIME-DISTRIBUTION-FIX-20260520
**Generated:** 2026-05-20T19:00:00+08:00
**Conclusion:** PASS

---

## Step Results

### Step 1 — Data Source Audit
**PASS** | distribution_available: false | missing_distribution_fields: true

Sources checked: scout_v4_20260520.json, v4_evening_current_freeze_20260520.json, v4_review_input_pack_20260520.json, intel_desk_v4_candidate_view_20260520.json

Fields found: `ht_score` (A+B), `best_score` (B only)
Fields missing: `0_15`, `16_30`, `31_45`, `goal_time_distribution`, `pressure_distribution`, `expected_goals`, `ht_pressure`, `hit_rate`, `script_type`, `strength_pct`

**No time-segmented distribution data exists in any source.** No data was fabricated.

### Step 2 — Script Classifier
**PASS** | tools/v4_script_classifier.py created

7 script types defined with precise classification rules:
1. 开局冲击型 — 0-15m >= 45 dominant, or 0-15m+16-30m >= 75
2. 中段压迫型 — 16-30m >= 45 dominant
3. 中后段发力型 — 31-45m >= 55, or >= 20 above other segments
4. 均衡持续型 — max-min <= 20
5. 双峰拉扯型 — 2+ segments >= 40, no single dominant
6. 低压观察型 — HT < 60 or expected_goals < 1.2 or all segments < 35
7. 数据不足 — missing 0-15m/16-30m/31-45m data

FULLTIME_OVER/SH_OU/FT_OU/SECOND_HALF_OVER are direction labels only, never script names.

### Step 3 — Candidate Model Enriched
**PASS** | All A/B/C entries now have: goal_time_distribution, script_type, script_reason, expected_goals, ht_pressure, strength_pct, distribution_text

All 11 cards correctly classified as 数据不足 (no time distribution data available).

### Step 4 — Dashboard Card Format Updated
**PASS** | intel_ops_console.html rewritten with new card format:

```
帕尔梅拉斯 vs 波特诺山丘
Palmeiras vs Cerro Porteno
自由杯｜05-21 08:30
HT79｜暂无数据｜暂无数据｜剧本：数据不足
时段：暂无完整时间分布数据
```

FULLTIME_OVER/SH_OU/FT_OU moved to model-tag small text only.

### Step 5 — Script & Goal Distribution Checker
**PASS** | tools/check_v4_script_goal_distribution.py — 11/11 PASS

### Step 6 — Verification
**PASS** | All 5 checkers PASS, 150 total checks

| Checker | Status | Checks |
|:---|:---|:---|
| v4_script_goal_distribution | PASS | 11/11 |
| chinese_ux | PASS | 13/13 |
| ops_console | PASS | 19/19 |
| latest_window | PASS | 55/55 |
| routes (HTTP) | PASS | 52/52 |

### Step 7 — Report
report_path: docs/V4_SCRIPT_AND_GOAL_TIME_DISTRIBUTION_FIX_20260520.md

---

## Key Decisions

1. **No time distribution data → 数据不足 for all cards.** The classifier correctly identifies this and does not fabricate scripts.
2. **HT pressure alone gives secondary signal.** B2 (HT=80) gets "数据不足（高压）" sub-classification.
3. **FULLTIME_OVER etc. are direction labels only.** Moved to model-tag small text below the main card info.
4. **All 11 cards show "暂无完整时间分布数据".** Honest about data limitations.

## Prohibitions Confirmed

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
| fabricated_distribution_data | false |

## Deliverables

- tools/v4_script_classifier.py — Script classification engine
- tools/check_v4_script_goal_distribution.py — 11-check validator
- data/runtime/status/intel_desk_v4_candidate_view_20260520.json — Enriched with script fields
- data/runtime/status/v4_goal_time_distribution_source_audit_20260520.json — Source audit
- data/runtime/dashboard/intel_ops_console.html — Rewritten with script-based card format
- docs/V4_SCRIPT_AND_GOAL_TIME_DISTRIBUTION_FIX_20260520.md — This report

## Next Steps

1. BOSS 审阅剧本分类规则和卡片格式
2. 未来数据源接入真实 0-15m/16-30m/31-45m 分布数据后，剧本分类将自动生效
3. 考虑从 scout_raw_dump 或 match detail API 提取时间段进球数据
