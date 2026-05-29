# V4 True Goal Time Distribution

**Date**: 2026-05-29
**Status**: V4_TRUE_GOAL_TIME_DISTRIBUTION_PASS
**HEAD**: 840b5a7 → (new commit)

## Summary

Replaced `normalized_from_per_bin_hit_rates` with real first-half goal event counts for V4 candidate card time distribution display.

## What Changed

### h2h_engine.py
- `_parse_goal_events()` now returns per-bin **goal counts** alongside boolean hit flags
- `evaluate_h2h_edge()` accumulates `fh_goals_0_15`, `fh_goals_16_30`, `fh_goals_31_45`, `fh_goals_total`
- New factors fields: `fh_goal_dist_source`, `fh_goal_dist_available`

### build_v4_control_center_model.py
- `_normalize_goal_distribution()` now reads real `fh_goals_*` from factors
- When events available: computes true goal distribution percentages (sum = 100%)
- When events unavailable: sets distribution to null, `fh_goal_dist_source=events_missing`
- Per-bin hit rates preserved as debug fields (`fh_bin_hit_rate_*_pct`)
- `playbook_script` derived from real distribution only; shows "数据暂缺" when unavailable

### Current Model State
- Both candidates show `events_missing` because existing scan data predates the h2h_engine changes
- `playbook_script: 数据暂缺` — correct fallback
- Next cron scan will populate real goal counts via `_parse_goal_events()`

## Field Taxonomy

| Field | Purpose | Display |
|-------|---------|---------|
| `fh_goal_dist_*_pct` | Real goal distribution | Candidate card main display |
| `fh_goal_dist_source` | `events_goal_counts` or `events_missing` | Audit |
| `fh_bin_hit_rate_*_pct` | Per-bin hit rate (debug) | Hidden from candidate card |
| `time_bins` | Legacy per-bin hit rates | Audit only |
