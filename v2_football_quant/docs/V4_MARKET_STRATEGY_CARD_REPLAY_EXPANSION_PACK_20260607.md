# V4 Market Strategy Card Replay Expansion Pack

Date: 2026-06-07

## Scope

This pack expands the read-only V4 market strategy card replay ledger using
local historical artifacts only. It does not call live APIs, execute scans,
alter official grades, write pending candidates, send QQ messages, modify
cron/launchd, or restore realtime reminders.

## Sources

- Local scout artifacts under `data/daily_reports/`
- Local candidate view artifacts under `data/runtime/status/`
- Locked five-dimension Lite builder
- Locked market strategy research card builder
- Historical validation files under `data/daily_reports/`

## Outputs

- `data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_expansion_20260607.json`
- `data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_expansion_summary_20260607.json`

The expansion keeps `PRICE_MISSING`, `LINE_MISSING`, `MARKET_MISSING`, and
`DATA_INSUFFICIENT` as explicit gaps. It does not fill missing price, line, or
market data with paper values.

## Result Policy

`RESULT_MISSING` rows are excluded from hit-rate calculations. If the
`OBSERVE` bucket remains too small, the summary marks
`OBSERVE_SAMPLE_INSUFFICIENT` as `WARN_ONLY`.

## Policy Lock

- Official grade unchanged.
- A/B/C/SKIP thresholds unchanged.
- Pending candidates untouched.
- QQ untouched.
- Cron and launchd untouched.
- B realtime reminder remains paused.
- RF shadow promotion remains blocked.
