# V4 Context Positive Bucket Explanation Audit

## Scope

This pack audits the two positive ROI buckets from the context-aware replay output. The purpose is to explain whether those buckets are stable research signals or structural noise.

The audit is offline only. It does not call api-football, run V4 scan, change official grade rules, write pending candidates, send QQ, or modify cron/launchd.

## Classification Rules

- SINGLE_CLUSTER_RISK: concentrated in one league or one season.
- EARLY_SEASON_RISK: high early-season share.
- NOT_HIGH_CONFIDENCE: sample_count below 1000.
- HIGH_DRAWDOWN_RISK: drawdown too large for the sample.
- STRUCTURAL_NOISE: no cross-league or cross-season explanation.

No classification creates an online action.

## Required Output

Each audited bucket includes:

- market
- context_filter
- sample_count
- hit_rate
- average close odds
- ROI proxy
- max fail streak
- max drawdown proxy
- league distribution
- season distribution
- early season share
- price movement direction
- strength context
- risk flags

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
