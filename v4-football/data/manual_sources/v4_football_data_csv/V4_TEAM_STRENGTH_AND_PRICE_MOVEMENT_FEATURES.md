# V4 Team Strength And Price Movement Features

## Scope

This pack enriches the offline Football-Data replay dataset with two research-only feature groups:

- team_strength_context
- price_movement_context

It uses only committed Football-Data CSV fields. It does not call api-football, run V4 scan, change official grade rules, write pending candidates, send QQ, or modify cron/launchd.

## Team Strength Context

The strength features are built with pre-match accumulation inside each league and season. The current match result is applied only after the row's features are written.

Fields include:

- home_points_before_match
- away_points_before_match
- home_rank_before_match
- away_rank_before_match
- rank_gap
- points_gap
- home_goal_diff_before_match
- away_goal_diff_before_match
- home_recent_5_points
- away_recent_5_points
- recent_5_points_gap
- home_home_points_before_match
- away_away_points_before_match
- home_advantage_context_flag

Early rounds are marked `EARLY_SEASON_INSUFFICIENT`, and opening rows with no prior team sample are marked `NO_PRIOR_MATCH_SAMPLE`.

## Price Movement Context

The price movement features use open-close differences only:

- odds_1x2_home_move
- odds_1x2_draw_move
- odds_1x2_away_move
- odds_over25_move
- odds_under25_move
- ah_home_move
- ah_away_move
- over25_close_implied_prob
- ah_home_close_implied_prob
- price_move_direction_flag
- line_movement_flag

The source does not provide market-wide average or max price, so `market_home_avg_vs_b365_close` and `market_home_max_vs_b365_close` remain blank and are marked `MARKET_AVG_MAX_SOURCE_MISSING`.

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
