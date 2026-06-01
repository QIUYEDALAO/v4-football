# V4 League Ledger A2 Weekly/Monthly Report Layer

Date: 2026-06-01

## Scope

A2 adds a weekly/monthly observation layer based on League Performance Ledger.

This layer is read-only and does not change recommendation or grading logic.

## What A2 Adds

1. `tools/build_v4_league_watchlist_report.py`
- Reads `data/runtime/validation/v4_league_performance_ledger_latest.json`
- Produces watchlist JSON/TXT for weekly/monthly/dryrun views
- Outputs KEEP / WATCH / LOW_TRUST_ALERT / LOW_SAMPLE_ONLY / DO_NOT_CONCLUDE / PENDING_ONLY / DATA_GAP groups
- Enforces safe `action_hint` values only

2. `tools/check_v4_league_watchlist_report.py`
- Validates watchlist outputs and safety boundaries
- Verifies 阿根廷杯 remains pending-only with `PENDING_ONLY_NO_DENOMINATOR`
- Verifies baseline and trend anchor integrity

3. `engine/v4_weekly_report.py`
- Keeps original validation/attribution/calibration logic unchanged
- Adds section:
  `八、联赛长期观察（League Ledger）`
- Shows read-only counts and trend anchor
- Degrades to WARN_ONLY if ledger/watchlist is missing, without blocking weekly report generation

## Policy and Safety

- LOW_TRUST_ALERT is observation-only, not auto-exclusion.
- PENDING_ONLY does not enter denominator.
- DO_NOT_CONCLUDE means sample-insufficient observation, not negative grading.
- Weekly report adds observation text only; original validation summary is unchanged.
- Official grade is unchanged.
- `73.5` is unchanged.
- `DEFAULT_RULES` and A/B thresholds are unchanged.
- No QQ push, no pending write, no validation recompute.
- No live bet changes, no cron changes.

## Future Boundary

If league tags should influence strategy or grading in the future, that must be a separate BOSS-approved task with explicit policy authorization.
