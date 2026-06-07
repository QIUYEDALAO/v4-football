# V4 Price-Aware Bucket Drilldown

## Purpose

This pack reviews MEDIUM_CONFIDENCE and LOW_CONFIDENCE buckets from the Football-Data price-aware bucket analysis. It is offline research only and does not connect to V4 production.

## Inputs

- processed/v4_price_aware_bucket_analysis.csv
- processed/v4_price_aware_bucket_summary.json
- processed/v4_price_aware_replay_core_ledger.csv

## Focus Order

1. ASIAN_HANDICAP
2. FT_OVER25
3. 1X2 as exclusion or auxiliary context
4. DOUBLE_CHANCE_PROXY as hit-rate-only context

## Candidate Rules

A bucket can enter `research_candidate` only when all conditions hold:

- confidence_flag is MEDIUM_CONFIDENCE
- sample_count >= 300
- ROI proxy is positive
- no HIGH_DRAWDOWN_RISK
- fail streak is not extreme
- similar positive direction appears across at least two seasons or two leagues

LOW_CONFIDENCE buckets can only be listed as watchlist. SMALL_SAMPLE buckets are excluded.

## Double Chance Proxy Policy

DOUBLE_CHANCE_PROXY has no real Double Chance price in the Football-Data source. It keeps hit rate and sample count only. ROI stays null and the output is marked `NO_REAL_DC_ODDS`.

## Current Result

The current drilldown finds no research candidates. It preserves 13 watchlist rows and excludes small-sample, low-confidence, high-drawdown, and non-positive medium-confidence buckets.

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
