# V4 Market Strategy Research Card Pack

Date: 2026-06-07

## Scope

This pack converts the locked five-dimension Lite skeleton into readable V4
market strategy research cards. It is still a local, observation-only research
layer. It does not call live APIs, execute scans, alter official grades, write
pending candidates, send QQ messages, modify cron/launchd, or restore realtime
reminders.

## Source

The builder reads:

- `data/manual_sources/v4/five_dimension_lite/v4_five_dimension_lite_samples_20260607.json`
- existing league admission and price-field policy through the checker suite

The output is written under:

- `data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260607.json`
- `data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_summary_20260607.json`

## Covered Directions

- `FULLTIME_OVER`
- `HANDICAP_HOME_AWAY`
- `DOUBLE_CHANCE_STRONG_SIDE`
- `HT_OVER_AUXILIARY`

HT Over remains auxiliary only. It cannot independently create A/B, realtime
alerts, or an `OBSERVE` card.

## Missing Context Rules

- `PRICE_MISSING`: market edge is `NOT_EVALUABLE`.
- `LINE_MISSING`: line confirmation is `NOT_EVALUABLE`.
- `MARKET_MISSING`: card conclusion can only be `WAIT` or `PASS`.
- `STANDINGS_MISSING` plus `TEAM_STATS_MISSING`: strength gap cannot pass.
- `LINEUP_WAIT_EVENT`: squad context stays waiting.
- `INJURY_SOURCE_MISSING`: the card must not assume there are no injuries.
- `EXTERNAL_CONTEXT_PENDING`: external risk cannot be a positive conclusion.

Allowed research conclusions are only `OBSERVE`, `WAIT`, and `PASS`.

## Policy Lock

- Official grade unchanged.
- A/B/C/SKIP thresholds unchanged.
- Pending candidates untouched.
- QQ untouched.
- Cron and launchd untouched.
- B realtime reminder remains paused.
- RF shadow promotion remains blocked.
