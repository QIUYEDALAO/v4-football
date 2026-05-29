# V4 Dashboard Score Summary Display Fix

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_SCORE_SUMMARY_DISPLAY_FIX_PASS
**Commit**: (see below)

## Problem

Candidate cards on restored V4 control center dashboard only showed:
- `H2H样本16场`
- `H2H样本6场`

HT score and 11-45 late first-half pressure data were available in `score_pack.scores.HT_LIVE_OVER` and `factors.late_fh_pressure` but were not rendered because the `renderCandidate` function in the dashboard HTML was reading `x.ht_score` (which was `None` at the candidate level) instead of the real HT score location.

## Root Cause

The `renderCandidate` JS function read HT score from `x.ht_score` — the flat candidate field. After the V4 parallel adapter score fields fix, `score_pack`, `factors`, and `market_scores` are correctly forwarded to the model, but the candidate-level `ht_score` remained `None` because the scan/brief layer stores the computed score inside `score_pack.scores`, not as a flat field.

## Fix

Modified `data/runtime/dashboard/v4_control_center.html` — the `renderCandidate` function:

1. Extract HT score from `x.score_pack.scores.HT_LIVE_OVER` (fallback to `x.ht_score`)
2. Extract `late_fh_pressure` from `x.late_fh_pressure` (fallback to `x.factors.late_fh_pressure`)
3. Build summary parts array and join with ` · `
4. Fallback to `评分摘要暂缺` when no data

### Summary format

| Priority | Display | Example |
|----------|---------|---------|
| Full | `评分摘要 HT{score} · H2H样本{n}场 · 11-45压力{p}%` | Rosenborg |
| Full | `评分摘要 HT{score} · H2H样本{n}场 · 11-45压力{p}%` | TransINVEST |
| Minimal | `评分摘要 H2H样本{n}场` | Only H2H available |
| None | `评分摘要暂缺` | No data |

### Actual results

- **Rosenborg (A)**: `评分摘要 HT79 · H2H样本16场 · 11-45压力60%`
- **TransINVEST (B)**: `评分摘要 HT62 · H2H样本6场 · 11-45压力67%`

## Protection Checklist

| Check | Status |
|-------|--------|
| DEFAULT_RULES unchanged | ✓ |
| A/B thresholds unchanged | ✓ |
| Candidate rating rules unchanged | ✓ |
| Validation not recomputed | ✓ |
| Live bet raw records unchanged | ✓ |
| Cron unchanged | ✓ |
| QQ not pushed | ✓ |
| No secrets committed | ✓ |
| Candidate count preserved (A1/B1/SKIP240) | ✓ |
| TODO count preserved (2) | ✓ |
| Unbet amount empty | ✓ |
| Unbet entry minute empty | ✓ |
| No fake 0% | ✓ |
| No undefined | ✓ |
| No N/A in candidate cards | ✓ |
| No raw JSON | ✓ |
