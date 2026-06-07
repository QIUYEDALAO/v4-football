# V4 Price-Aware Bucket Drilldown

## Scope

Offline drilldown of MEDIUM_CONFIDENCE and LOW_CONFIDENCE buckets from Football-Data price-aware replay. This is research-only and is not connected to V4 production.

## Input Summary

- bucket_rows: 2683
- confidence_counts: {'LOW_CONFIDENCE': 143, 'MEDIUM_CONFIDENCE': 135, 'SMALL_SAMPLE': 2405}
- source_top_research_candidates_count: 0

## Candidate Result

- research_candidate_count: 0
- watchlist_count: 13

No bucket is promoted from small sample or low confidence. Double Chance proxy has no real price and no ROI.

## Exclusion Counts

- small_sample: 2405
- low_confidence_not_candidate: 143
- medium_roi_not_positive: 135
- high_drawdown_risk: 15
- double_chance_no_real_roi: 135

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
