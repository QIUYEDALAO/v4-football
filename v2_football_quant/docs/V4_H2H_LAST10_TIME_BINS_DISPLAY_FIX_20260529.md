# V4 H2H Last-10 Policy & Time-Bin Display Fix

**Date**: 2026-05-29
**Status**: V4_H2H_LAST10_TIME_BINS_DISPLAY_FIX_PASS
**Commit**: (see below)

## Problems Fixed

### 1. H2H Sample Count Display
**Before**: Dashboard showed `h2h_official_count=16` (all same-league post-2020 games), misleading about actual scoring sample.
**After**: Model now exposes layered H2H counts:
- `h2h_raw_count`: all games in database (24)
- `h2h_post2020_count`: post-2020 same-league (16)
- `h2h_valid_count`: official sample size (10)
- `h2h_used_count`: actually used for scoring, capped at 10 (10)
- `h2h_used_limit`: 10

The scoring engine already correctly caps samples at 10 (`h2h_sample_size=10`). The fix exposes these layered counts for audit and removes misleading aggregate display from cards.

### 2. Time-Bin Distribution Display
**Before**: Cards showed score summary (HT79 · H2H样本16场 · 11-45压力60%) — internal debug info.
**After**: Cards show first-half goal time distribution:
- Rosenborg: `进球时间分布 0-15 50% · 16-30 20% · 31-45 50%`
- TransINVEST: `进球时间分布 0-15 33% · 16-30 50% · 31-45 33%`

Data sourced from `score_pack/factors.time_bins` → flat model fields via `time_bin_0_15/16_30/31_45`.

### 3. Removed Internal Labels from Cards
- `57白名单` (source_group label) — removed from cards, kept in model for stats
- `全量合规` (fixture_universe label) — removed from cards, kept in model for stats  
- `正式候选` (script label) — removed from cards
- `评分摘要 HT...` (score summary) — replaced with time-bin distribution

### Files Changed
- `tools/build_v4_control_center_model.py` — added h2h layered fields, fixed time_bin flat extraction fallback
- `data/runtime/dashboard/v4_control_center.html` — replaced score summary with time-bin distribution, removed internal labels

### Candidate Cards Now Show
1. Team name + A/B badge
2. League · Grade · Kickoff time
3. Goal time distribution (0-15/16-30/31-45 percentages)
4. Status (未投注)
5. Bet form (盘口/水位/金额/分钟)

### Protection
| Check | Status |
|-------|--------|
| DEFAULT_RULES unchanged | ✓ |
| A/B thresholds unchanged | ✓ |
| H2H used ≤ 10 for all candidates | ✓ |
| source_group in model for stats | ✓ |
| fixture_universe in model for stats | ✓ |
| WHITELIST_57/OUTSIDE_57 split preserved | ✓ |
| No scan re-run | ✓ |
| Validation not recomputed | ✓ |
| Live bet unchanged | ✓ |
| Cron unchanged | ✓ |
| QQ not pushed | ✓ |
| No secrets | ✓ |
