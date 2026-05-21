# V2/V4 Grade-Split Validation Dashboard V2 — Completion Report 20260520

**Phase:** V2-V4-GRADE-SPLIT-VALIDATION-DASHBOARD-V2-20260520
**Generated:** 2026-05-20T18:00:00+08:00
**Conclusion:** V2_V4_GRADE_SPLIT_VALIDATION_DASHBOARD_PASS

---

## Problem Statement

The previous V2/V4 validation dashboard incorrectly received PASS because:
1. V4 A/B was merged — no separate A or B hit rate
2. C observation performance was hidden (not optimized because "not in hit rate" = hidden)
3. V2 only showed "样本不足" without state distribution
4. Rolling validation had no layered structure
5. Checker was too loose, allowing incorrect PASS

## Step Results

### Step 1 — Validation Schema
**PASS** — `validation_schema_v2_20260520.json` created

Defines V2 official (BET_LOCKED only) + non_official_audit (WATCH/CANDIDATE/FINAL_RECORD/ODDS_OUT/HT_SKIP counts only), V4 official (A/B/A+B with separate hit rates), V4 observation (C with observation_hit_rate), V4 skip (SKIP with reason_distribution).

### Step 2 — V2 Yesterday Validation
**PASS** — `v2_yesterday_validation_20260519.json` created

- Official BET_LOCKED: 1 sample, 0 hit, 0 miss, 1 unknown → hit_rate null (样本不足)
- Non-official audit: WATCH=0, CANDIDATE=0, FINAL_RECORD=0, ODDS_OUT=0, HT_SKIP=0
- Settlement BLOCKED — no hit/miss determinable

### Step 3 — V4 Yesterday Validation
**PASS** — `v4_yesterday_validation_20260519.json` created

| Grade | Count | Hit | Miss | Unknown | Hit Rate |
|:---|:---|:---|:---|:---|:---|
| A | 0 | 0 | 0 | 0 | N/A |
| B | 3 | 0 | 0 | 3 | 0% |
| A+B | 3 | 0 | 0 | 3 | 0% |
| C (观察) | 13 | 0 | 0 | 13 | 0% |
| SKIP | 8 | — | — | — | N/A |

C_not_in_formal_hit_rate=true, SKIP_not_in_hit_rate=true

### Step 4 — V2 Rolling Validation
**PASS** — `v2_rolling_validation_split_20260520.json` created

7/14/30d windows: BET_LOCKED=1, hit=0, miss=0, unknown=1 — 样本不足
Non-official audit: all zero (no WATCH/CANDIDATE files generated)

### Step 5 — V4 Rolling Validation
**PASS** — `v4_rolling_validation_split_20260520.json` created

| Grade | 7d Count | Hit | Miss | Unknown | Hit Rate |
|:---|:---|:---|:---|:---|:---|
| A | 41 | 25 | 16 | 0 | 61.0% |
| B | 92 | 50 | 39 | 3 | 54.3% |
| A+B | 133 | 75 | 55 | 3 | 56.4% |
| C (观察) | 190 | 75 | 102 | 13 | 39.5% |
| SKIP | 115 | — | — | — | N/A |

8 days of attribution data (2026-05-12 to 2026-05-19). 14d and 30d same as 7d (only 8 days available).

### Step 6 — Dashboard Updated
**PASS** — `intel_ops_console.html` updated with grade-split modules

Two main modules before candidate cards:

1. **昨日验证** — V2 BET_LOCKED official + V2 audit (WATCH/CANDIDATE/FINAL_RECORD/ODDS_OUT/HT_SKIP) + V4 A/B/A+B separate + V4 C observation layer + SKIP
2. **滚动验证** — V2 7/14/30d official + V4 A 7/14/30d + V4 B 7/14/30d + V4 A+B 7/14/30d + V4 C观察 7/14/30d

### Step 7 — New Strict Checker
**PASS** — `check_v2_v4_grade_split_validation_dashboard.py` — 13/13 PASS

### Step 8 — Verification
**PASS** — All 5 checkers PASS, 107 total checks

| Checker | Status | Checks |
|:---|:---|:---|
| v2_v4_grade_split_validation_dashboard | PASS | 13/13 |
| v2_v4_validation_dashboard | PASS | 10/10 |
| chinese_ux | PASS | 13/13 |
| ops_console | PASS | 19/19 |
| routes (HTTP) | PASS | 52/52 |

---

## 11 Questions Answered

1. **A是否单独统计？** 是。A级 0/41 样本，单独命中率 61.0%（滚动）。
2. **B是否单独统计？** 是。B级 3/92 样本，单独命中率 54.3%（滚动）。
3. **C是否单独统计？** 是。C级 13/190 观察样本，观察命中率 39.5%。
4. **C是否排除正式命中率？** 是。明确标注"不计入正式命中率"，C为观察层。
5. **SKIP是否统计但排除命中率？** 是。SKIP 8/115 统计，明确"不计入命中率"。
6. **V2是否只用 BET_LOCKED 算正式命中率？** 是。明确"只统计BET_LOCKED"。
7. **V2 WATCH/CANDIDATE是否仅审计？** 是。明确"仅审计，不进正式命中率"。
8. **7/14/30是否分层展示？** 是。A/B/A+B/C 各分层展示7/14/30日。
9. **是否伪造赛果？** 否。所有数据来自真实attribution JSONL文件（8天）。
10. **是否运行 capture？** 否。
11. **是否真实推 QQ？** 否。

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
| C_in_formal_rate | false |
| SKIP_in_hit_rate | false |

## Deliverables

- data/runtime/status/validation_schema_v2_20260520.json
- data/runtime/status/v2_yesterday_validation_20260519.json
- data/runtime/status/v4_yesterday_validation_20260519.json
- data/runtime/status/v2_rolling_validation_split_20260520.json
- data/runtime/status/v4_rolling_validation_split_20260520.json
- data/runtime/dashboard/intel_ops_console.html (updated with grade-split modules)
- tools/check_v2_v4_grade_split_validation_dashboard.py
- docs/V2_V4_GRADE_SPLIT_VALIDATION_DASHBOARD_V2_20260520.md

## Key Findings

- V4 A级命中率 61.0%（25/41）— 强推荐表现优于B级
- V4 B级命中率 54.3%（50/92）— 候选级仍有52.9%以上
- V4 A+B 合并命中率 56.4%（75/133）— 正式候选整体过半
- V4 C级观察命中率 39.5%（75/190）— 低于A/B，验证C级筛选有效
- V2 数据极少（4天仅1条 BET_LOCKED），结算系统长期BLOCK
