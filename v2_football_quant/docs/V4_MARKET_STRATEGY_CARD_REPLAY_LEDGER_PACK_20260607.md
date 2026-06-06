# V4 Market Strategy Card Replay Ledger Pack

Date: 2026-06-07

## Scope

This pack adds a read-only replay ledger for V4 market strategy research cards.
It uses local artifacts only and does not call live APIs, execute scans, alter
official grades, write pending candidates, send QQ messages, or modify
cron/launchd.

## Ledger Inputs

- `data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260607.json`
- `data/manual_sources/v4/five_dimension_lite/v4_five_dimension_lite_samples_20260607.json`
- local historical validation files under `data/daily_reports/`

## Ledger Outputs

- `data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_ledger_20260607.json`
- `data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_summary_20260607.json`

Each row keeps fixture identity, match context, league admission status, card
conclusion, covered directions, five-dimension gaps, price/line/market status,
and result availability.

## Result Policy

`RESULT_MISSING` is not counted in hit-rate calculations. Missing price, line,
or market context is retained as a gap and is never converted into an edge
statement. If the `OBSERVE` sample is too small, the summary marks
`OBSERVE_SAMPLE_INSUFFICIENT` as `WARN_ONLY`.

## Policy Lock

- Official grade unchanged.
- A/B/C/SKIP thresholds unchanged.
- Pending candidates untouched.
- QQ untouched.
- Cron and launchd untouched.
- B realtime reminder remains paused.
- RF shadow promotion remains blocked.
