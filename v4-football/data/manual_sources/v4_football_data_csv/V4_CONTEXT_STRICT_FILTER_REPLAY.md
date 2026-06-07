# V4 Context Strict Filter Replay

## Scope

This pack reruns FT_OVER25 and ASIAN_HANDICAP context replay after strict risk filters. It is offline research only and has no production effect.

## Strict Filters

- exclude sample_count < 300 from candidates
- exclude EARLY_SEASON_INSUFFICIENT rows
- exclude SINGLE_CLUSTER_RISK buckets
- exclude HIGH_DRAWDOWN_RISK buckets
- exclude LOW_CONFIDENCE buckets
- exclude rows with missing price, line, or market fields

## Candidate Rule

A strict research candidate must have:

- sample_count >= 1000
- positive ROI proxy
- no single-cluster concentration
- no high drawdown risk
- no early-season source rows
- no missing price or line in the underlying rows

Positive ROI is still research-only and does not create an online action.

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
