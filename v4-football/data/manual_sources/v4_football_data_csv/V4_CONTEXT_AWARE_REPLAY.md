# V4 Context-Aware Replay

## Scope

This pack runs an offline context-aware replay on the enriched Football-Data dataset. It only covers:

- FT_OVER25
- ASIAN_HANDICAP

It does not call api-football, run V4 scan, change official grade rules, write pending candidates, send QQ, or modify cron/launchd.

## Context Filters

FT_OVER25 filters:

- strength_gap_bucket
- recent_5_points_gap_bucket
- over25_close_implied_prob_bucket
- odds_over25_move_direction
- early_season_status
- league_code
- season

ASIAN_HANDICAP filters:

- rank_gap_bucket
- points_gap_bucket
- recent_5_points_gap_bucket
- ah_home_close_implied_prob_bucket
- ah_move_direction
- asian_handicap_line_bucket
- home_away_side
- early_season_status
- league_code
- season

## Risk Rules

- sample_count < 300: SMALL_SAMPLE, not candidate
- sample_count 300-999: MEDIUM_RESEARCH_ONLY
- sample_count >= 1000: HIGH_CONFIDENCE
- early season insufficient buckets are not main candidates
- positive ROI with high drawdown is marked HIGH_DRAWDOWN_RISK

Positive ROI buckets remain research-only and are not treated as an advantage claim.

## Safety Lock

- api_football_called=false
- v4_scan_executed=false
- official_grade_changed=false
- pending_written=false
- qq_sent=false
- cron_or_launchd_modified=false
- strategy_online=false
- recommendation_generated=false
- edge_claim_generated=false
