# Validation AB133 Forensic Recount — 2026-05-20

## Conclusion: VALIDATION_AB133_FORENSIC_RECOUNT_PASS

All 5 checkers pass (69/69). All 4 forensic JSONs created. Dashboard updated to three-policy display.

---

## Q1: A+B=133 到底是什么口径？

**Answer:** 133 = 原始 attribution 记录条数（Policy A — Raw Attribution Record）。每条记录是一个唯一比赛条目（fixture_id + match_date），在 8 个 v4_result_attribution JSONL 文件中各出现一次。

It is NOT a count of unique teams. It IS a count of unique match entries.

---

## Q2: 是否 raw attribution record？

**Answer:** YES. 133 = 41条A级 + 92条B级，直接从 8 个 JSONL 文件中逐行计数。每个 fixture_id+date 组合恰好出现一次，无多窗口重复。

---

## Q3: 是否 production recommendation？

**Answer:** NOT exactly. Production recommendation (Policy C) = 130（排除3条未结算的B级记录）。3条B级记录来自 2026-05-19 attribution，当天 API disabled，所有24条记录均为 MODEL_RESULT_UNKNOWN。

- Raw records (含未结算): A=41 + B=92 = **133**
- Production resolved (仅已结算): A=41 + B=89 = **130**

---

## Q4: 是否 unique fixture？

**Answer:** Depends on definition:
- Unique by fixture_id + date (match-level): **133** — same as raw count. Zero duplicates.
- Unique by fixture_id only (team-level): **106** = 32A + 74B. 9支A队和18支B队在7天内多次出场。

Each match is an independent recommendation event. Same team on different days = different recommendation. Match-level counting (133) is correct for recommendation tracking.

---

## Q5: 是否多窗口重复？

**Answer:** NO. Zero cases of same fixture_id+date appearing in multiple attribution files. 126 fixture_ids appear on multiple dates (same team, different match days), but these are different matches — not duplicates.

12 pairs of same-team-same-grade on consecutive days found, all confirmed as different match dates.

---

## Q6: 是否多 grade 重复？

**Answer:** 38 fixture_ids have different grades on different dates (e.g., SKIP on day 1, A on day 2). This reflects legitimate model reassessment as new scouting data arrives. Not double-counting.

Zero "true duplicates" (same fixture_id+date+grade appearing 2+ times).

---

## Q7: Dashboard 默认应该显示哪个口径？

**Answer:** Production recommendation policy (Policy C) — A+B = 130 resolved. This reflects decisions where outcomes are known. Raw 133 and team-dedup 106 are shown in the audit expansion area.

Updated dashboard now displays: "生产推荐口径（已结算）A+B=130 | 原始记录 133条（含3未结算）| 球队去重 A=32+B=74=106"

---

## Q8: 7/14/30 为何相同？

**Answer:** Attribution data only spans 2026-05-13 to 2026-05-19 (7 days). All 438 records fall within the narrowest window (7d). Wider windows (14d, 30d) capture identical records because no data exists for dates before 05-13. Each window filter is applied independently — verified not a code copy.

---

## Q9: 是否仍可用于策略判断？

**Answer:** YES. With the three-policy clarification:
- Hit rate is computed correctly: 75/(75+55) = 57.69% (resolved only)
- Unknown records (3 B, 13 C, 1 V2) display N/A — never 0%
- The 130 resolved A+B recommendations are fit for strategy evaluation
- Caveat: 7-day sample is small. Hit rates should not be over-interpreted.

---

## Q10: 是否需要降级为 WARN？

**Answer:** NO. The 133 number is legitimate and fully traced. No overcounting, no duplicates, no fabrication. The only issue was imprecise labeling in the dashboard (calling it "样本 133" without clarifying it's raw record count, not unique teams). This has been fixed.

---

## Checker Results — 69/69 PASS

| Checker | Checks | Result |
|---------|--------|--------|
| check_validation_ab133_forensic_recount | 10 | PASS |
| check_validation_lineage_hard_freeze | 10 | PASS |
| check_validation_data_lineage | 17 | PASS |
| check_intel_ops_console_chinese_ux | 13 | PASS |
| check_intel_ops_console | 19 | PASS |

## Forensic Artifacts Created

| Artifact | Path |
|----------|------|
| Per-file inventory | data/runtime/status/validation_ab133_forensic_inventory_20260520.json |
| Three-policy recount | data/runtime/status/validation_ab133_recount_by_policy_20260520.json |
| Duplicate audit | data/runtime/status/validation_ab133_duplicate_audit_20260520.json |
| Date window audit | data/runtime/status/validation_ab133_date_window_audit_20260520.json |
| Forensic checker | tools/check_validation_ab133_forensic_recount.py |
| Report | docs/VALIDATION_AB133_FORENSIC_RECOUNT_20260520.md |

## Prohibitions Audit

| Rule | Status |
|------|--------|
| NO capture | VERIFIED |
| NO QQ push | VERIFIED |
| NO V4_QQ_ENABLED | VERIFIED |
| NO D13/V33/HOURLY | VERIFIED |
| NO strategy changes | VERIFIED |
| NO fabricated results | VERIFIED |
| NO C/SKIP in formal hit rate | VERIFIED |
| NO same-fixture multi-window as multiple matches | VERIFIED — zero multi-window entries |
