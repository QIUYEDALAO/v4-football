# V4 Reporting Schema

Phase: V4-G
Date: 2026-05-19
Status: FINAL (contract only, not yet executing reports)

## Root Fields

| Field | Value |
|-------|-------|
| schema_version | "1.0" |
| system | "V4" |
| production_verified | false |
| phase_e_allowed | false |
| qq_push_allowed | false |
| verified_write_allowed | false |
| rule_change_allowed | false |

## Report Types

### Daily Report Fields
- date, window, total_matches
- A_count, B_count, C_count, SKIP_count
- unknown_count, api_disabled_count
- guard_summary, risk_summary
- attribution_summary, rolling_snapshot
- report_allowed, qq_allowed=false

### Weekly Report Fields
- week_start, week_end
- daily_summary
- A_B_primary_summary, C_observation_summary
- SKIP_behavior_summary
- unknown_excluded_summary, api_disabled_excluded_summary
- rolling_7d_summary
- rule_change_allowed=false

### Monthly Report Fields
- month
- rolling_30d_summary
- sample_size_summary
- league_split, grade_split
- source_quality_split, data_quality_split
- rule_change_recommendation_allowed=false
- verified_write_allowed=false

## Reporting Rules

- A/B only enter primary recommendation summary
- C only enters observation summary (never primary)
- SKIP only enters skip behavior summary (never recommendation)
- UNKNOWN excluded from hit/miss in reports
- API_DISABLED excluded from hit/miss in reports
- Daily reports must NOT trigger rule changes
- Weekly reports must NOT directly change rules
- Monthly reports may suggest review notes only
- Report output ≠ verified
- Report output ≠ QQ sent
