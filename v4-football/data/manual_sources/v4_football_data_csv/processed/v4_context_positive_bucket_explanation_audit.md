# V4 Context Positive Bucket Explanation Audit

## Scope

Offline explanation audit for positive ROI context buckets. This audit is research-only and has no online action.

## Summary

- context_bucket_count: 85
- positive_roi_bucket_count: 2
- research_candidate_count: 0

## Audited Buckets

### Bucket 1

- market: ASIAN_HANDICAP
- context_filter: ah_home_close_implied_prob_bucket
- context_value: LT_0_40
- sample_count: 6
- hit_rate: 0.5
- roi_proxy_flat_1u: 1.008333
- max_drawdown_proxy: -1.0
- early_season_share: 0.333333
- risk_flags: EARLY_SEASON_RISK, NOT_HIGH_CONFIDENCE, POSITIVE_ROI_RESEARCH_ONLY, SMALL_SAMPLE_NO_CANDIDATE

### Bucket 2

- market: FT_OVER25
- context_filter: odds_over25_move_direction
- context_value: MOVE_MISSING
- sample_count: 52
- hit_rate: 0.846154
- roi_proxy_flat_1u: 0.148095
- max_drawdown_proxy: -4.0
- early_season_share: 0.076923
- risk_flags: NOT_HIGH_CONFIDENCE, POSITIVE_ROI_RESEARCH_ONLY, SINGLE_CLUSTER_RISK, SMALL_SAMPLE_NO_CANDIDATE

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
