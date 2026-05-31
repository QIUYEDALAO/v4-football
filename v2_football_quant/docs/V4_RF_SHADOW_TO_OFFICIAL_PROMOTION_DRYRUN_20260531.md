# V4 RF Shadow → Official Promotion Dry-Run (20260531)

> ⚠️ **IMPORTANT**: This is a dry-run simulation only. It does **NOT** represent an official recommendation.

## Purpose

Simulate what would happen if `market_adjusted_shadow_grade` (from the `rf_lazy_shadow` collection pipeline) were used as the official candidate recommendation entry, without actually changing any production systems.

## Scope

- **Date**: 2026-05-31
- **Source**: `data/daily_reports/scout_v4_20260531.json` (43 fixtures, `rf_lazy_shadow` mode)
- **No re-scan**: Only reads existing artifacts
- **No API calls**: All data already collected
- **No grade modification**: Official `grade` field remains empty (mapped to SKIP)
- **No candidate_view modification**: `v3v4_dashboard_candidate_view_20260531.json` unchanged
- **No pending_bet_candidates**: Dry-run output does not enter betting pipeline
- **No validation**: Dry-run not fed into validation
- **No QQ**: No recommendation pushed
- **No live bet modification**: Bet records untouched
- **No cron modification**: Schedule unchanged

## Methodology

1. Read `scout_v4_{date}.json` — each fixture has `rf_shadow_grade` and `market_adjusted_shadow_grade`
2. Compute `dryrun_grade` using `market_adjusted_shadow_grade` with safety filters:
   - `market_adjusted=A` → `DRYRUN_A`
   - `market_adjusted=B` → `DRYRUN_B`
   - `market_adjusted=C` → `DRYRUN_C_OBSERVE`
   - `market_adjusted=SKIP` → `DRYRUN_SKIP`
3. Safety filters applied:
   - `MARKET_HARD_VETO` → never promoted to dryrun A/B
   - `MARKET_NO_DATA` → not auto-promoted to A (downgraded to B)
   - `NO_MARKET` → not promoted to dryrun A/B
4. Output: JSON + Markdown report in `data/runtime/acceptance/`

## Results (20260531)

| Grade | Official | RF Shadow | Market Adjusted | Dry-Run |
|-------|----------|-----------|-----------------|---------|
| A | 0 | 2 | 0 | 0 |
| B | 0 | 29 | 3 | 3 |
| C | 0 | 12 | 23 | 4 |
| SKIP | 0 | 0 | 17 | 36 |

### Dry-Run B Candidates (3)

| Time | League | Match | Reason |
|------|--------|-------|--------|
| 13:00 | 日职联 | Shimizu S-pulse vs Yokohama F. Marinos | H2H strong bonus, balanced active, no opening market |
| 19:30 | 友谊赛 | Singapore vs Mongolia | RF near-5 all A, hot driver, no opening market (downgraded from A to B) |
| 22:30 | 友谊赛 | Cyprus U19 vs England U18 | RF B+hot driver, no opening market |

### Key Vetoes

- **25 shadow A/B** blocked by `MARKET_HARD_VETO` — initial market lines strongly opposed
- All 3 dryrun B candidates have `MARKET_NO_DATA` — no opening market → reduced confidence

## Authorized Use

This dry-run may be re-run for any future date (`--date YYYYMMDD`) as long as:
1. Scout artifact exists for that date
2. No API calls are made
3. No production data is modified

## Transition Path (Future)

If BOSS decides to transition to RF shadow as official entry, a **separate BOSS authorization** is required for:
1. Updating the scan pipeline to compute official grades from market-adjusted RF shadow grades
2. Updating candidate_view to reflect new grades
3. Updating QQ recommendation logic (if desired)
4. Updating validation pipeline to track new grade origin
5. Updating cron payloads
6. Running a backtest on historical data
7. Running a canary/rollout period

## Artifacts

- `tools/build_v4_rf_shadow_to_official_promotion_dryrun.py` — the dry-run generator
- `tools/check_v4_rf_shadow_to_official_promotion_dryrun.py` — safety checker
- `data/runtime/acceptance/v4_rf_shadow_to_official_promotion_dryrun_{date}.json` — JSON report (NOT committed)
- `data/runtime/acceptance/v4_rf_shadow_to_official_promotion_dryrun_{date}.md` — Markdown report (NOT committed)

## File Locations

- Tools: `/tools/build_v4_rf_shadow_to_official_promotion_dryrun.py`
- Checker: `/tools/check_v4_rf_shadow_to_official_promotion_dryrun.py`
- Runtime artifacts: `/data/runtime/acceptance/` (not committed)
- This document: `/docs/V4_RF_SHADOW_TO_OFFICIAL_PROMOTION_DRYRUN_20260531.md`
