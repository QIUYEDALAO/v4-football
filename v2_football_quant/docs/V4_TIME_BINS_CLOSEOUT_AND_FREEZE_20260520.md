# V4 Time Bins Closeout & Freeze Report — 2026-05-20

## Conclusion: V4_TIME_BINS_CLOSEOUT_FREEZE_PASS

All 5 checkers pass (109/109 checks). All 11 entries source-traced. All classifications correct. No blockers.

---

## Q1: Are all time_bins entries source-traced to scout_v4 factors.recent_time_bins?

**YES.** All 11 entries (1A + 4B + 6C) have `source_file: data/daily_reports/scout_v4_20260520.json`, `source_field: factors.recent_time_bins`, `source_priority: 1`.

Verified by `check_v4_goal_distribution_source_trace.py` Check 1: "time_bins source = recent_time_bins: 11/11".

## Q2: Are any entries using factors.time_bins (all-zero)?

**NO.** `factors.time_bins` is `[0, 0, 0]` for all 11 matches. The 4-tier priority system (Priority 1: recent_time_bins > Priority 2: time_bins non-zero only > Priority 3: existing > Priority 4: unavailable) correctly skips Priority 2 because the values are all-zero.

Verified by `check_v4_goal_distribution_source_trace.py` Check 2: "factors.time_bins (all-zero) NOT used as source".

Hard rule enforced in `v4_time_bins_lineage_freeze_20260520.json`: "factors.time_bins all-zero → MUST NOT override recent_time_bins".

## Q3: Are all 11 entries correctly classified per the 9-type taxonomy?

**YES.** Priority-ordered classification in `v4_script_classifier.py` correctly matches all 11 entries:

| Label | Match | m0_15 | m16_30 | m31_45 | Script | Rule Match |
|-------|-------|-------|--------|--------|--------|------------|
| A | Palmeiras vs Cerro Porteno | 40% | 60% | 30% | 中段压迫型 | 16-30m max & ge 45% |
| B1 | Hangzhou vs Shandong | 20% | 30% | 60% | 慢热绝杀型 | 31-45m ge 60% & 0-15m le 25% |
| B2 | Ilves vs Inter Turku | 60% | 50% | 40% | 开局冲击型（高压） | 0-15m ge 55% & 16-30m ge 45% |
| B3 | Start vs Bodo/Glimt | 10% | 50% | 40% | 中段压迫型 | 16-30m max & ge 45% |
| B4 | Santos vs San Lorenzo | 10% | 60% | 40% | 中段压迫型 | 16-30m max & ge 45% |
| C1 | Shanghai vs Wuhan | 30% | 50% | 40% | 中段压迫型 | 16-30m max & ge 45% |
| C2 | KuPS vs FF Jaro | 40% | 10% | 40% | 双峰拉扯型 | 2 segments ge 40%, gap le 15% |
| C3 | Pyramids vs Smouha | 30% | 30% | 40% | 均衡持续型 | all ge 30%, range le 20% |
| C4 | Zamalek vs Ceramica | 10% | 30% | 30% | 低压观察型 | max lt 35% |
| C5 | Al Khaleej vs Al-Ahli | 30% | 80% | 30% | 中段压迫型 | 16-30m max & ge 45% |
| C6 | Aalesund vs Brann | 50% | 40% | 40% | 开局冲击型 | 0-15m max & ge 45% |

Verified by `v4_script_taxonomy_freeze_20260520.json` `all_correct: true` (11/11 expected == actual).

## Q4: Is Palmeiras correctly classified as 中段压迫型?

**YES.** Palmeiras (40/60/30): 16-30m=60% is the max segment and >=45%, correctly classified as 中段压迫型. The old buggy fallback `(m0_15+m16_30)>=75` (40+60=100 >= 75) would have misclassified it as 开局冲击型. This fallback was removed from `v4_script_classifier.py`.

Verified by `check_v4_goal_distribution_source_trace.py` Check 4 and `check_v4_script_goal_distribution.py` Check 8.

## Q5: Is B1 Hangzhou correctly classified as 慢热绝杀型?

**YES.** Hangzhou (20/30/60): 31-45m=60% >= 60% AND 0-15m=20% <= 25%, correctly classified as 慢热绝杀型.

Verified by `check_v4_goal_distribution_source_trace.py` Check 5 and `check_v4_script_goal_distribution.py` Check 9.

## Q6: Are all C cards marked observation_only?

**YES.** All 6 C cards have `C_observation_only: true`, `recommendation_status: observation_only`, `grade: C`. The HTML dashboard marks them "仅观察，不是推荐".

Verified by `check_v4_goal_distribution_source_trace.py` Check 8 and `check_v4_script_goal_distribution.py` Check 11.

## Q7: Are FULLTIME_OVER/SH_OU/FT_OU forbidden as script names?

**YES.** These are direction/market labels, not script types. The 9-type taxonomy has no overlap. The freeze JSON explicitly lists them under `forbidden_as_script`.

Verified by `check_v4_goal_distribution_source_trace.py` Check 7 and `check_v4_script_goal_distribution.py` Checks 5-6.

## Q8: Is the buggy fallback (m0_15+m16_30)>=75 removed?

**YES.** The old fallback rule that summed m0_15+m16_30 and compared to 75 was removed from `v4_script_classifier.py`. The classifier now uses strict priority-ordered matching with no catch-all sum rule.

Documented in `v4_script_taxonomy_freeze_20260520.json` under `key_bug_fixed`.

## Q9: Are all checkers passing?

**YES.** 109/109 across 5 checkers:

| Checker | Checks | Pass | Fail |
|---------|--------|------|------|
| check_v4_goal_distribution_source_trace | 10 | 10 | 0 |
| check_v4_script_goal_distribution | 15 | 15 | 0 |
| check_intel_ops_console_chinese_ux | 13 | 13 | 0 |
| check_intel_ops_console | 19 | 19 | 0 |
| check_intel_dashboard_user_visible_routes | 52 | 52 | 0 |
| **Total** | **109** | **109** | **0** |

## Q10: Is the permanent builder operational?

**YES.** `tools/v4_build_candidate_view.py` reads scout_v4 → extracts time_bins via `v4_today_source_resolver.py` → applies `v4_script_classifier.py` → writes candidate view JSON → regenerates HTML. Tested and verified: candidate view built at 2026-05-20T20:41:50+08:00 with all 11 entries correctly classified.

## Q11: Are the freeze JSON artifacts complete?

**YES.** Three freeze artifacts created:

| Artifact | Path | Content |
|----------|------|---------|
| Lineage Freeze | `data/runtime/status/v4_time_bins_lineage_freeze_20260520.json` | 11 entries with per-entry source tracing, 4-tier priority rules |
| Taxonomy Freeze | `data/runtime/status/v4_script_taxonomy_freeze_20260520.json` | 9 script types, classification rules, 11 expected vs actual (all correct) |
| Closeout Report | `data/runtime/status/v4_time_bins_closeout_and_freeze_20260520.json` | Full closeout status, checker results, prohibitions audit |

## Q12: Closeout conclusion?

**V4_TIME_BINS_CLOSEOUT_FREEZE_PASS** — all checks pass, all artifacts frozen, zero blockers.

---

## Prohibitions Audit

| Rule | Status |
|------|--------|
| NO capture | VERIFIED — capture_ran: false |
| NO QQ push | VERIFIED — qq_sent: false, V4_QQ_ENABLED: false |
| NO D13/V33/HOURLY | VERIFIED |
| NO strategy changes | VERIFIED |
| NO fabricated data | VERIFIED — all data from scout_v4 |
| NO C in formal hit rate | VERIFIED — C_observation_only: true |
| NO SKIP in hit rate | VERIFIED |
| NO hardcoded numbers | VERIFIED — all numbers from source files |
| NO unknown as 0% | VERIFIED — unknown displays N/A |

## Files in Final State

| File | Role |
|------|------|
| `tools/v4_today_source_resolver.py` | Permanent 4-tier time_bins extraction |
| `tools/v4_script_classifier.py` | 9-type priority-ordered script taxonomy |
| `tools/v4_build_candidate_view.py` | Permanent builder (resolver + classifier + HTML) |
| `tools/check_v4_goal_distribution_source_trace.py` | 10-check source trace regression |
| `tools/check_v4_script_goal_distribution.py` | 15-check script + distribution regression |
| `tools/check_validation_lineage_hard_freeze.py` | 10-check validation lineage regression |
| `data/runtime/status/v4_time_bins_lineage_freeze_20260520.json` | Time bins lineage freeze artifact |
| `data/runtime/status/v4_script_taxonomy_freeze_20260520.json` | Script taxonomy freeze artifact |
| `data/runtime/status/v4_script_taxonomy_20260520.json` | BOSS-directed formal taxonomy |
| `data/runtime/status/validation_lineage_hard_freeze_20260520.json` | Validation lineage freeze artifact |
| `data/runtime/dashboard/intel_ops_console.html` | Live dashboard with correct classifications |
