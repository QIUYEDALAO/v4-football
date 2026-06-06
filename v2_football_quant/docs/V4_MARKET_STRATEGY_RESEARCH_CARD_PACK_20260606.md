# V4 Market Strategy Research Card Pack

Status: CODE_READY  
Date: 2026-06-06

This pack creates a research-card layer only. It does not change V4 official grades, thresholds, QQ, pending state, cron, launchd, validation, or live bet records.

## Card Fields

Each card includes:

- `match_info`
- `league_admission_status`
- `strategy_directions`
- `strength_gap`
- `market_confirmation`
- `price_quality`
- `data_quality`
- `missing_context`
- `conclusion`

Allowed conclusions are only:

- `OBSERVE`
- `WAIT`
- `PASS`

## Covered Market Directions

- `FULLTIME_OVER`
- `HANDICAP_HOME_AWAY`
- `DOUBLE_CHANCE_STRONG_SIDE`
- `HT_OVER_AUXILIARY`

`HT_OVER_AUXILIARY` is auxiliary context only. It cannot create an official A/B state and cannot be the sole reason for `OBSERVE`.

## Missing Context Tags

The builder must explicitly show missing fields:

- `PRICE_MISSING`
- `LINE_MISSING`
- `MARKET_MISSING`
- `INJURY_SOURCE_MISSING`
- `LINEUP_MISSING`
- `LINEUP_WAIT_EVENT`
- `DATA_INSUFFICIENT`

If price or line context is absent, the card must stay `WAIT` or `PASS`.

## Outputs

- `data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260606.json`
- `data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_summary_20260606.json`

These are manual-source research artifacts, not runtime outputs.

## Policy Locks

- B realtime reminder remains paused.
- C/SKIP/shadow-only remain quiet.
- RF shadow promotion remains blocked.
- No live API call is made.
- No real scan is executed.
- No official grade or threshold is changed.
