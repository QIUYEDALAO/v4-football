# V4 Price-Aware Replay Ledger

## Scope

This pack builds a replay-only, price-aware proxy ledger for V4 official A/B.
It does not call live API, execute scan, change official grade, alter A/B
thresholds, write pending candidates, push QQ, change cron/launchd, or release
RF shadow promotion.

## Source Policy

The corrected official aggregate record is fixed as:

- A: 30/49
- B: 54/95, pending 1
- A+B: 84/144, pending 1

The available historical event ledger has 140 rows and does not itself contain
the corrected 144-row event-level sequence. Therefore the builder reconciles
the legacy event rows to the BOSS aggregate with four explicit aggregate
reconciliation rows. These rows have no fixture id and are marked:

`AGGREGATE_RECONCILIATION_NO_EVENT_SOURCE`

This prevents fake fixture attribution while still making the ROI/drawdown
proxy arithmetic transparent.

## Output

- `data/manual_sources/v4/price_aware_replay/v4_official_ab_price_aware_replay_ledger_20260606.json`
- `data/manual_sources/v4/price_aware_replay/v4_official_ab_price_aware_replay_summary_20260606.json`

## Price Proxy

The only stable local price proxy in the historical ledger is
`paper_default_0.80`, represented as decimal odds `1.80`.

This is a proxy, not a real closing price and not a last-pre-kickoff price.
It is good enough to show sensitivity and drawdown shape, not enough to prove
live edge.

## Risk Conclusion

- A: `OBSERVE_ONLY_PRICE_GUARD_REQUIRED`
- B: `PAUSE_REALTIME_REMINDER`
- A+B: `DAILY_REPORT_ONLY`
- Shadow/C/SKIP: observation-only

Forbidden real-time buckets remain:

- SKIP
- C
- shadow-only
- MARKET_NO_DATA
- MARKET_EXTREME
- H2H_LOW_SAMPLE
- weak/stale/unknown recent form

## Next Step

Replace proxy rows with a true event-level price ledger once local artifacts
contain reliable first-seen and last-pre-kickoff odds. Until then, do not use
this ledger as proof of sustainable betting edge.
