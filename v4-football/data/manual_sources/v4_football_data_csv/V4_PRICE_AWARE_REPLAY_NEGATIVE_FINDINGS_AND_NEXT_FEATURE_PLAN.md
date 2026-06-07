# V4 Price-Aware Replay Negative Findings And Next Feature Plan

## Source Artifacts

- processed/v4_price_aware_replay_core_summary.json
- processed/v4_price_aware_bucket_summary.json
- processed/v4_price_aware_bucket_drilldown.json

## Market-Level Findings

The current Football-Data replay does not support production use. Closing prices are already difficult to beat with only market, league, season, price band, and line bucket dimensions.

| market | sample_count | ROI proxy | decision |
| --- | ---: | ---: | --- |
| FT_OVER25 | 15448 | -0.0471 | Continue research with attack, defense, and tempo context |
| 1X2 | 46344 | -0.0800 | Downgrade to auxiliary context |
| ASIAN_HANDICAP | 30896 | -0.0245 | Continue research with stronger team and schedule context |
| DOUBLE_CHANCE_PROXY | 46344 | null | Hit-rate-only auxiliary context, no real ROI |

## Bucket Findings

- bucket_rows: 2683
- HIGH_CONFIDENCE: 0
- MEDIUM_CONFIDENCE: 135
- LOW_CONFIDENCE: 143
- SMALL_SAMPLE: 2405
- research_candidate: 0
- LOW_CONFIDENCE watchlist: 13

The bucket drilldown found no production-ready research candidate. Positive low-confidence rows remain watchlist-only. Small samples and high drawdown buckets are excluded.

## Negative Attribution

1. Market prices are broadly efficient at this coarse feature level.
2. League, season, price band, and handicap line buckets are not enough to isolate stable positive ROI.
3. 1X2 has the largest negative ROI and should be used only as background market context.
4. Asian Handicap is closest to flat, but still negative and needs more explanatory variables before further promotion.
5. FT Over 2.5 remains researchable, but only with attack, defense, tempo, shot, and game-state context.
6. Double Chance proxy has no real price and cannot be part of ROI analysis.

## Next Feature Plan

Priority 1: team strength context
- table rank and points gap
- home and away strength split
- recent form quality
- promoted or relegation-pressure context

Priority 2: price movement context
- opening to closing odds movement
- line movement
- market average versus best available price
- close-price quality band

Priority 3: tactical and stat context
- shots and shots on target trend
- corner profile
- goals for and goals against trend
- FT O/U tempo context

Priority 4: fatigue and schedule context
- rest days
- consecutive away matches
- fixture congestion
- travel placeholder until reliable source exists

Priority 5: exclusion filters
- low sample
- high drawdown
- extreme odds
- non-mainstream league
- missing real price or line

## Policy Lock

- cannot_online=true
- api_football_called=false
- v4_scan_executed=false
- official_grade_changed=false
- pending_written=false
- qq_sent=false
- cron_or_launchd_modified=false
- strategy_online=false
- recommendation_generated=false
- edge_claim_generated=false
