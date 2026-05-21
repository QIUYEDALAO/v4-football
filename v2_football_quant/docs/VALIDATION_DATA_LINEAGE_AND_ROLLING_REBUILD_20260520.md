# Validation Data Lineage & Rolling Rebuild — Completion Report 20260520

**Phase:** VALIDATION-DATA-LINEAGE-AND-ROLLING-REBUILD-20260520
**Generated:** 2026-05-20T19:00:00+08:00
**Conclusion:** VALIDATION_DATA_LINEAGE_REBUILD_PASS

---

## Why Old Validation Was Rejected

1. **A+B=133 suspicious**: No source trace — couldn't explain where 133 came from
2. **7d/14d/30d identical**: Date window filtering appeared broken
3. **B=3 unknown → 0%**: Unknown treated as 0% hit rate instead of N/A
4. **C=13 unknown → 0%**: Same bug — unknown confused with miss
5. **Lineage missing**: No number could be traced to raw source file + fixture_id
6. **Goal distribution missing**: 0-15m/16-30m/31-45m data exists in QQ but not dashboard

Old status: VALIDATION_DASHBOARD_V2_RUNTIME_VERIFY_PASS → **REJECTED_BY_BOSS**

---

## What Was Fixed

### A+B=133 — Traced
133 = 41 A records (32 unique fixtures) + 92 B records (74 unique fixtures). All from 8 attribution JSONL files (20260512-20260519), 438 total records, 0 duplicates. Every record has `source_file`, `source_hash`, `fixture_id`, `match_date`.

### 7d/14d/30d Identical — Documented, Not a Bug
Attribution data only covers 2026-05-13 to 2026-05-19 (7 days). All three windows (7d from 05-13, 14d from 05-06, 30d from 04-20) extend beyond available data and capture the same 438 records. `same_window_reason` documented in output. This is a data availability limit, not a code bug.

### Unknown → N/A (Not 0%)
hit_rate = hit / (hit + miss), not hit / (hit + miss + unknown). When resolved=0, hit_rate = N/A.
- Yesterday B: 3 records, 0 resolved → N/A (was incorrectly 0%)
- Yesterday C: 13 records, 0 resolved → N/A (was incorrectly 0%)
- Rolling A+B: 57.69% (75/130 resolved), not 56.4% (75/133 including unknown)

### Lineage Verified
Every number in the dashboard can be traced:
- V4: → v4_result_attribution_*.jsonl → specific fixture_id + match_date
- V2: → v2_window_notify_*.json → specific date

---

## Step Results

### Step 1 — Rejection
**PASS** — `validation_dashboard_v2_rejection_20260520.json` created. Dashboard banner: "REJECTED — 旧版已打回"

### Step 2 — Source Inventory
**PASS** — `validation_data_source_inventory_20260520.json` created

V2 sources: 4 window_notify files, 2 settlement_preflight, 2 daily_status_push, 1 bet_locked_proof
V4 sources: 8 attribution JSONL files (PRIMARY for hit/miss), scout_v4 in daily_reports, candidate_view downstream

Key finding: attribution JSONL has `bucket_hit` (True/False/null) but NOT `time_bins` (0_15/16_30/31_45). Time distribution data exists in scout_v4 `ht_rec.time_bins` but is not extracted to candidate model.

### Step 3 — V4 Raw Records
**PASS** — `v4_validation_raw_records_20260520.json` created

438 records, 438 unique keys, 0 duplicates. Each record: record_id, source_file, source_hash, fixture_id, match_date, league, home, away, grade, status (hit/miss/unknown/skip), result_status, is_formal_candidate, is_observation, is_skip.

### Step 4 — V4 Rolling Rebuilt
**PASS** — `v4_rolling_validation_rebuilt_20260520.json` created

| Grade | Count | Hit | Miss | Unknown | Resolved | Hit Rate |
|:---|:---|:---|:---|:---|:---|:---|
| A | 41 | 25 | 16 | 0 | 41 | 61.0% |
| B | 92 | 50 | 39 | 3 | 89 | 56.2% |
| A+B | 133 | 75 | 55 | 3 | 130 | 57.7% |
| C | 190 | 75 | 102 | 13 | 177 | 42.4% |
| SKIP | 115 | — | — | — | — | N/A |

same_window_detected=true, same_window_reason documented.

### Step 5 — V4 Yesterday Rebuilt
**PASS** — `v4_yesterday_validation_rebuilt_20260519.json` created

| Grade | Count | Hit | Miss | Unknown | Resolved | Hit Rate |
|:---|:---|:---|:---|:---|:---|:---|
| A | 0 | 0 | 0 | 0 | 0 | N/A |
| B | 3 | 0 | 0 | 3 | 0 | **N/A** |
| C | 13 | 0 | 0 | 13 | 0 | **N/A** |
| SKIP | 8 | — | — | — | — | N/A |

### Step 6 — V2 Validation Rebuilt
**PASS** — `v2_validation_rebuilt_20260520.json` created

| Window | BET_LOCKED | Hit | Miss | Unknown | Resolved | Hit Rate |
|:---|:---|:---|:---|:---|:---|:---|
| Yesterday | 1 | 0 | 0 | 1 | 0 | N/A |
| 7d | 1 | 0 | 0 | 1 | 0 | N/A |
| 14d | 1 | 0 | 0 | 1 | 0 | N/A |
| 30d | 1 | 0 | 0 | 1 | 0 | N/A |

Settlement always BLOCKED. All results unknown.

### Step 7 — Dashboard Updated
**PASS** — lineage-verified banners, date_from/date_to, unique_fixture_count, duplicate_count, resolved_count, N/A for unknown

### Step 8 — Lineage Checker
**PASS** — `check_validation_data_lineage.py` — 17/17 PASS

### Step 9 — Verification
**PASS** — 124/124 across 6 checkers

| Checker | Status | Checks |
|:---|:---|:---|
| validation_data_lineage | PASS | 17/17 |
| grade_split_validation_dashboard | PASS | 13/13 |
| v2_v4_validation_dashboard | PASS | 10/10 |
| chinese_ux | PASS | 13/13 |
| ops_console | PASS | 19/19 |
| routes (HTTP) | PASS | 52/52 |

---

## 15 Questions Answered

1. **旧验证 dashboard 为什么被打回？** 滚动数字可疑（A+B=133无法追溯）、7d/14d/30d完全一致、unknown显示为0%、数据血缘缺失、进球时间分布缺失。
2. **A+B=133 从哪里来？** 41 A (32 unique fixtures) + 92 B (74 unique fixtures) = 133，来自8天 attribution JSONL，0 duplicates。
3. **7d/14d/30d 为什么一样？** 数据仅覆盖7天（0513-0519），三窗口范围均超出可用数据，捕获相同438条记录。已记录 same_window_reason。
4. **每个滚动窗口 raw_record_count 是多少？** 438（7d/14d/30d 相同，因为数据覆盖限制）。
5. **unique_fixture_count 是多少？** A=32, B=74, C=151, SKIP=93，总计350 unique fixtures across all grades。
6. **duplicate_count 是多少？** 0 — 无重复 (fixture_id, match_date, grade) 键。
7. **unknown 是否已从命中率剔除？** 是。hit_rate = hit/(hit+miss)，resolved=0 时显示 N/A。
8. **B=3 unknown 是否已显示 N/A？** 是。
9. **C=13 unknown 是否已显示 N/A？** 是。
10. **V2是否只用 BET_LOCKED？** 是。明确 scope="BET_LOCKED only"。
11. **V4是否只用 A/B 计算正式命中率？** 是。C 为观察层，SKIP 不计入。
12. **是否有无法追溯的数据？** 否。每条记录有 source_file + fixture_id。V2 结算数据不可用（BLOCKED）→ 所有 unknown。
13. **是否伪造赛果？** 否。所有数据来自真实 attribution JSONL 文件。
14. **是否运行 capture？** 否。
15. **是否真实推 QQ？** 否。

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
| unknown_as_miss | false |
| C_in_formal_rate | false |
| SKIP_in_hit_rate | false |

## Deliverables

- data/runtime/status/validation_dashboard_v2_rejection_20260520.json
- data/runtime/status/validation_data_source_inventory_20260520.json
- data/runtime/status/v4_validation_raw_records_20260520.json
- data/runtime/status/v4_rolling_validation_rebuilt_20260520.json
- data/runtime/status/v4_yesterday_validation_rebuilt_20260519.json
- data/runtime/status/v2_validation_rebuilt_20260520.json
- data/runtime/dashboard/intel_ops_console.html (updated)
- tools/check_validation_data_lineage.py
- docs/VALIDATION_DATA_LINEAGE_AND_ROLLING_REBUILD_20260520.md

## Next Tasks

1. V4-GOAL-DISTRIBUTION-SOURCE-TRACE-AND-SCRIPT-FIX-20260520 — trace QQ 0-15m/16-30m/31-45m time distribution to scout_v4 ht_rec.time_bins and fix candidate model extraction
