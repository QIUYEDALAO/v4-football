# V4 Control Center D4 League Intelligence Panel

Date: 2026-06-01

## Scope

D4 adds a dashboard-only league intelligence panel for centralized observation of:
- A1 long-term league performance ledger
- A2 watchlist observation layer
- A3 rolling trend monitor layer

## Data Sources

- `data/runtime/validation/v4_league_performance_ledger_latest.json`
- `data/weekly_reports/v4_league_watchlist_report_*.json` (or monthly fallback)
- `data/runtime/league_watchlist_trends/v4_league_watchlist_trend_latest.json`

All reads are read-only. No strategy writeback is added.

## D4 UI/Model Additions

- `league_intelligence_panel`
- `league_watchlist_counts`
- `league_watchlist_preview`
- `league_watchlist_trend_summary`
- `league_watchlist_policy_note`
- `league_watchlist_safety_guard`
- `league_trend_baseline_only`
- `league_trend_self_reference_guard_status`
- `league_trend_warn_only_items`

Dashboard includes:
- count summary cards
- watchlist preview groups (max 5 with `+N more`)
- trend summary and baseline/self-reference guard handling
- safety policy notes

## Policy Boundary

- D4 does not affect official grade.
- `73.5` unchanged.
- `DEFAULT_RULES` unchanged.
- A/B thresholds unchanged.
- no QQ push.
- no pending write.
- no validation recompute.
- no live bet mutation.
- no cron change.

Interpretation safety:
- `LOW_TRUST_ALERT` is not auto-exclude.
- `DO_NOT_CONCLUDE` is sample-insufficient observation, not negative grading.
- `PENDING_ONLY` is excluded from denominator.
- trend baseline-only means trend cannot be concluded.
- self-reference guard must be PASS before normal trend display.

## Out-of-Scope

`26_QQ_push_disabled` remains `NON_A3_EXISTING_WARN_ONLY` and is not in D4 fix scope.

If league tags should influence strategy/rating later, that requires a separate BOSS-approved task.
