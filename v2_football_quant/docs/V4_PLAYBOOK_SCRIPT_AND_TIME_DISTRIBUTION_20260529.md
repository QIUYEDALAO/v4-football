# V4 Playbook Script & Time Distribution Fix

**Date**: 2026-05-29
**Status**: V4_PLAYBOOK_SCRIPT_AND_TIME_DISTRIBUTION_PASS
**Commit**: (see below)

## Root Cause Analysis

### Time Bins Were Hit Rates, Not Distribution
The original `time_bins` values were per-bin **hit rates**:
- Rosenborg: `0_15=0.5 + 16_30=0.2 + 31_45=0.5 = 1.2` (120%!)
- TransINVEST: `0_15=0.333 + 16_30=0.5 + 31_45=0.333 = 1.166` (117%!)

Each bin value represents "fraction of H2H games with at least one goal in this window" — a hit rate. Displaying these as percentages produced nonsense (e.g., "50% + 20% + 50%") that didn't sum to 100%.

### Playbook Script Was Missing
No playbook/script field existed. Previous labels like "正式候选" or "HT进球剧本" were placeholder strings unrelated to actual first-half goal timing patterns.

## Fix

### 1. Distribution Normalization
Hit rates are normalized to goal distribution percentages that sum to exactly 100%:
```
dist_pct = hit_rate / sum_of_all_bins * 100
```
Rounding adjusted so 0-15 + 16-30 + 31-45 = 100%.

### 2. Playbook Derivation
Based on normalized distribution:

| Script | Rule |
|--------|------|
| 开局冲击 | 0-15 is highest AND ≥40% |
| 中段发力 | 16-30 is highest AND ≥40% |
| 尾段压迫 | 31-45 is highest AND ≥40% |
| 双段压迫 | Two segments ≥35% AND diff ≤15% |
| 均衡压迫 | All three in 25%-40% range |
| 数据暂缺 | No time_bins data |

### Results

| Candidate | Playbook | Distribution |
|-----------|----------|-------------|
| Rosenborg (A) | **尾段压迫** | 0-15 41% · 16-30 17% · 31-45 42% |
| TransINVEST (B) | **中段发力** | 0-15 29% · 16-30 42% · 31-45 29% |

### Card Display (Final)
```
罗森博格 vs 博德闪耀                      A
挪超 · A · 05-30 01:00
剧本：尾段压迫
进球分布 0-15 41% · 16-30 17% · 31-45 42%
未投注
```

### Protection
| Check | Status |
|-------|--------|
| DEFAULT_RULES unchanged | ✓ |
| A/B thresholds unchanged | ✓ |
| Validation not recomputed | ✓ |
| Live bet unchanged | ✓ |
| Cron unchanged | ✓ |
| QQ not pushed | ✓ |
| No secrets | ✓ |
