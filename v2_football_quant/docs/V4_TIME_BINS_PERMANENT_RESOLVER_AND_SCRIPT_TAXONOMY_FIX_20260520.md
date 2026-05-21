# V4 Time-Bins Permanent Resolver & Script Taxonomy Fix — 2026-05-20

## Conclusion: V4_TIME_BINS_RESOLVER_SCRIPT_TAXONOMY_PASS

### 1. time_bins 是否永久接入？
**YES.** `tools/v4_today_source_resolver.py` now has `extract_goal_time_distribution()` with permanent 4-tier source priority. `tools/v4_build_candidate_view.py` permanently rebuilds candidate view JSON from scout_v4 each run.

### 2. resolver 文件在哪里？
- `tools/v4_today_source_resolver.py` — extract_goal_time_distribution() + extract_candidate_entries()
- `tools/v4_build_candidate_view.py` — permanent candidate view builder
- `tools/v4_script_classifier.py` — 9-type BOSS-directed taxonomy

### 3. 是否仍依赖临时 JSON patch？
**NO.** The builder reads scout_v4 → extracts time_bins → classifies scripts → writes candidate view JSON → regenerates HTML. Fully automated.

### 4. factors.recent_time_bins 是否优先？
**YES.** Priority 1 of 4-tier system. `factors.time_bins` is Priority 2 and excluded when all-zero.

### 5. factors.time_bins 全0是否被排除？
**YES.** `tb_all_zero` guard prevents all-zero time_bins from being used.

### 6. Palmeiras 分类是否修正？
**YES.** 开局冲击型 → **中段压迫型** (16-30m=60% is max segment AND >=45%). Root cause: removed buggy fallback `(m0_15+m16_30)>=75` that overrode correct classification.

### 7. B1/B2/B3/B4 分类是否符合 taxonomy？
| Card | Distribution | Classification | Correct? |
|------|-------------|----------------|----------|
| B1 Hangzhou | 20/30/60 | 慢热绝杀型 | YES (31-45m≥60% AND 0-15m≤25%) |
| B2 Ilves | 60/50/40 | 开局冲击型（高压） | YES (0-15m≥55% AND 16-30m≥45%) |
| B3 Start | 10/50/40 | 中段压迫型 | YES (16-30m max AND ≥45%) |
| B4 Santos | 10/60/40 | 中段压迫型 | YES (16-30m max AND ≥45%) |

### 8. C是否仍 observation-only？
**YES.** All 6 C cards marked "仅观察，不是推荐".

### 9. 是否伪造时间分布？
**NO.** All 11 entries source from `scout_v4 → factors.recent_time_bins`, with `source_file`, `source_field`, and `source_priority` documented per entry.

### 10. 是否运行 capture？
**NO.**

### 11. 是否真实推 QQ？
**NO.** V4_QQ_ENABLED=false, actual_send=false, qq_sent=false.

---

## Changed Files

| File | Action | Description |
|------|--------|-------------|
| `tools/v4_today_source_resolver.py` | MODIFIED | Added time_bins extraction with 4-tier priority |
| `tools/v4_script_classifier.py` | REWRITTEN | 9-type formal taxonomy, priority-ordered, removed buggy fallback |
| `tools/v4_build_candidate_view.py` | CREATED | Permanent candidate view builder |
| `tools/check_v4_script_goal_distribution.py` | UPDATED | Loads taxonomy from JSON, added strict regression checks |
| `tools/check_v4_goal_distribution_source_trace.py` | CREATED | 10-check strict source trace regression |
| `data/runtime/status/v4_script_taxonomy_20260520.json` | CREATED | BOSS-directed formal taxonomy |

## Checker Results: 74/74 PASS

| Checker | Checks | Result |
|---------|--------|--------|
| v4_goal_distribution_source_trace | 10 | PASS |
| v4_script_goal_distribution | 15 | PASS |
| intel_ops_console | 19 | PASS |
| intel_ops_console_chinese_ux | 13 | PASS |
| validation_data_lineage | 17 | PASS |
