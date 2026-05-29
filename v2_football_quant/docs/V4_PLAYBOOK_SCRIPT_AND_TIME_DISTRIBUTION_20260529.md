# V4 Playbook Script & Time Distribution

**Date**: 2026-05-29
**Status**: V4_PLAYBOOK_SCRIPT_AND_TIME_DISTRIBUTION_PASS
**HEAD**: 1da6d18 → (new commit)

## Summary

1. Added `_derive_playbook_script()` — derives playbook labels from goal distribution
2. Added `_normalize_goal_distribution()` — normalizes per-bin hit rates into goal distribution percentages
3. Updated model builder to include `playbook_script` and `fh_goal_dist_*_pct` fields
4. Updated dashboard HTML with playbook and time distribution display structure
5. Updated candidate normalizer to pass through new fields

## Playbook Classification Rules

| Script | Condition |
|--------|-----------|
| 开局冲击 | 0-15 highest AND >= 40% |
| 中段发力 | 16-30 highest AND >= 40% |
| 尾段压迫 | 31-45 highest AND >= 40% |
| 双段压迫 | Any two >= 35% AND difference <= 15% |
| 均衡压迫 | All three in 25%-40% |
| 弱剧本 | Low-confidence patterns |
| 数据暂缺 | Missing data or zero goals |

## Current Results (2026-05-30 scan)

| Candidate | Playbook | 0-15 | 16-30 | 31-45 | Sum |
|-----------|----------|------|-------|-------|-----|
| Rosenborg vs Bodo/Glimt (A) | 尾段压迫 | 41.6% | 16.7% | 41.7% | 100.0% |
| TransINVEST vs Hegelmann Litauen (B) | 中段发力 | 28.6% | 42.8% | 28.6% | 100.0% |

## Time Distribution Note

Current distribution is normalized from per-bin hit rates because raw goal count breakdown is not available in the current scan output. Source: `normalized_from_per_bin_hit_rates`. Future enhancement: capture per-bin goal counts from the API for exact distribution.

## Forbidden Labels Removed

- 57白名单 → hidden from candidate cards (preserved in model for split stats)
- 全量合规 → hidden
- 正式候选 → hidden
- 候选剧本 → removed
- HT进球剧本 → removed

## Protection Gates

- [x] DEFAULT_RULES unchanged
- [x] A/B thresholds unchanged
- [x] validation not recomputed
- [x] live bet not modified
- [x] cron not modified
- [x] QQ not pushed
- [x] H2H post-2020 last-10 policy intact
