# V4 Football-Data Price-Aware Bucket Analysis

## Scope

This pack splits the offline Football-Data replay core into research buckets for:

- FT_OVER25
- 1X2
- ASIAN_HANDICAP
- DOUBLE_CHANCE_PROXY

It uses only the committed Football-Data CSV replay dataset and the derived replay core ledger. It does not call api-football, run V4 scan, alter official grade rules, write pending candidates, send QQ, or modify cron/launchd.

## Bucket Dimensions

- market
- league_code
- season
- close_odds_band
- asian_handicap_line_bucket
- over25_price_band
- home_away_side
- sample_size_bucket

Each bucket records sample count, settled count, hit rate, average close odds, flat 1u ROI proxy when real close odds exist, max fail streak, drawdown proxy, missing price count, uncertain settlement count, confidence flag, and risk flags.

## Confidence Rules

- sample_count < 100: SMALL_SAMPLE
- sample_count 100-299: LOW_CONFIDENCE
- sample_count 300-999: MEDIUM_CONFIDENCE
- sample_count >= 1000: HIGH_CONFIDENCE

Positive ROI in a small or noisy bucket is not treated as an advantage claim. Buckets with high drawdown are marked HIGH_DRAWDOWN_RISK for further review only.

## Double Chance Proxy Policy

DOUBLE_CHANCE_PROXY keeps hit rate and sample count only. It has no real Double Chance odds in this dataset, so ROI and drawdown fields stay blank and the bucket is marked NO_REAL_DC_ODDS.

## Safety Lock

This output is an offline research artifact only:

- api_football_called=false
- v4_scan_executed=false
- official_grade_changed=false
- pending_written=false
- qq_sent=false
- cron_or_launchd_modified=false
- strategy_online=false
- recommendation_generated=false
- edge_claim_generated=false
