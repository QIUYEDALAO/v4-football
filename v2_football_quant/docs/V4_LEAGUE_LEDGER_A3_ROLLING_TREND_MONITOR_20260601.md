# V4 League Ledger A3 Rolling Trend Monitor

Date: 2026-06-01

## Scope

A3 adds a rolling trend monitor layer on top of A2 watchlist outputs.

This layer is observation-only and does not change recommendation, grading, or default rule logic.

## What A3 Adds

1. `tools/build_v4_league_watchlist_trend_report.py`
- Reads current watchlist snapshot from A2 output (or triggers A2 dryrun when missing).
- Builds runtime snapshot and trend outputs:
  - `data/runtime/league_watchlist_snapshots/v4_league_watchlist_snapshot_YYYYMMDD.json`
  - `data/runtime/league_watchlist_trends/v4_league_watchlist_trend_latest.json`
  - `data/runtime/league_watchlist_trends/v4_league_watchlist_trend_latest.txt`
- Supports baseline-only mode when only one snapshot exists:
  - `baseline_only=true`
  - `baseline_only_reason="当前仅有 baseline 快照，不能判断趋势。"`
- Emits trend fields for:
  - trust tag distribution current/previous/delta
  - changed trust tags
  - improved/worsened leagues
  - pending to validated conversion
  - sample and hit-rate delta top lists

2. `tools/check_v4_league_watchlist_trend_report.py`
- Runs trend builder in dryrun mode and validates output integrity.
- Validates:
  - baseline-only behavior and reason
  - distribution delta consistency
  - action hint whitelist
  - safety guard fields
  - policy note presence
- Verifies source safety boundary (no scan/API/QQ/pending/validation/live bet/cron/sent-marker writes).

3. `engine/v4_weekly_report.py`
- Keeps existing weekly report sections and logic unchanged.
- Adds observation-only section:
  `九、联赛 Watchlist 趋势变化`
- If trend file is missing, degrades to WARN_ONLY and keeps weekly report generation non-blocking.

## Policy and Safety

- Trend monitor is for observation only; it does not auto-change official grade.
- LOW_TRUST_ALERT remains observation-only, not auto-exclusion.
- PENDING_ONLY remains excluded from denominator.
- Baseline-only means no trend conclusion is made.
- Official grade is unchanged.
- `73.5` is unchanged.
- `DEFAULT_RULES` and A/B thresholds are unchanged.
- No QQ push, no pending write, no validation recompute.
- No live bet changes, no cron changes.

## Runtime Artifact Boundary

The following are runtime artifacts and should not be committed:
- `data/runtime/league_watchlist_snapshots/*.json`
- `data/runtime/league_watchlist_trends/*.json`
- `data/runtime/league_watchlist_trends/*.txt`
- `data/weekly_reports/v4_league_watchlist_report_*.json`
- `data/monthly_reports/v4_league_watchlist_report_*.json`

