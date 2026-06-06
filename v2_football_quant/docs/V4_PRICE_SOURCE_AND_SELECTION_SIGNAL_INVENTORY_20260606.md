# V4 Price Source and Selection Signal Inventory

## Scope

This audit checks local V4 artifacts only. It does not call live API, execute a
scan, change official grades, change A/B thresholds, write pending records,
push QQ, or change cron/launchd.

The purpose is to separate real saved market fields from proxy arithmetic. Do
not use paper odds as real price evidence.

Machine-check policy: Do not use paper odds as real price evidence; historical official A/B cannot be rebuilt into a complete true price ledger; future scan/scout must persist price timing fields; historical form is auxiliary only.

## Artifacts Scanned

- `data/daily_reports/scan_perf_v4_*.json`
- `data/daily_reports/scout_v4_*.json`
- `data/daily_reports/v4_openclaw_brief_*.txt`
- `data/runtime/status/v4_official_candidate_view_*.json`
- `data/runtime/validation/*.json`
- validation / replay / dryrun status artifacts

## Price Sources Found

### Historical Official A/B Ledger

`data/runtime/validation/v4_ab_historical_ledger_20260526.json` contains 140
event rows. All 140 rows use:

`odds_source=paper_default_0.80`

That field is a paper proxy. It is not a saved bookmaker price, not a native
opening price, not a closing price, and not a last-pre-kickoff price.

The ledger rows can be joined to scout records by `fixture_id`, but the joined
historical scout rows do not provide usable real price fields,
`opening_market_snapshot_time`, `first_seen`, `last_seen`, or `closing` fields
for those official A/B events.

Conclusion: historical official A/B cannot be rebuilt into a complete true
price ledger from current local artifacts.

### Scout Artifacts

Some later `scout_v4_*.json` files contain market fields such as:

- `prematch_ht_line`
- `prematch_over_odds`
- `prematch_under_odds`
- `opening_market_bookmaker_used`
- `opening_market_market_name`
- `opening_market_snapshot_time`
- `opening_ht_ou_line`
- `opening_ht_ou_over_odds`
- `opening_ft_ou_line`
- `opening_ah_line`
- `opening_market_support_status`
- `opening_market_conflict_level`

These are useful for future price-aware work. They are not enough to prove the
old official A/B edge because they are not present for the corrected historical
A/B ledger sequence.

### Official Candidate View

The current `v4_official_candidate_view_YYYYMMDD.json` files keep fixture,
kickoff, grade/count, and display fields, but they do not persist real price
events. They also do not contain `first_seen`, `last_seen`,
`last_pre_kickoff`, or `closing` fields.

This means candidate_view is not currently an event-level price ledger.

### Brief and Scan Perf

Brief text sometimes includes market wording and line-like text, but it is not
structured enough to reconstruct event-level price history.

Scan perf files keep scan-level status/timing and sometimes market-related
summary fields, but they are not sufficient for per-event price replay.

## Field Coverage Summary

Available in useful form:

- `fixture_id`: available in scout, candidate_view, validation/replay artifacts
- `kickoff_time` / `kickoff_local`: available in scout and candidate_view
- `generated_at` / scan artifact timing: available at file or status level
- prematch/opening market fields: partially available in later scout files
- `result_hit`: available in validation ledger/status artifacts

Missing for true price-aware replay:

- event-level `selected_at` for historical official A/B
- event-level `first_seen_odds`
- event-level `last_seen_odds`
- event-level `last_pre_kickoff_odds`
- native `closing_odds`
- bookmaker/market/line persisted into validation ledger
- candidate_view price fields
- durable market movement timeline for V4 official selections

## Historical Ledger Possibility

Past data supports only a partial proxy audit. It cannot produce a complete
true event-level price ledger for the corrected official A/B record.

The prior price-aware replay ledger therefore remains a sensitivity proxy, not
edge proof. Its `1.80` odds proxy must stay labeled as proxy and must not be
used to justify real-time reminders or production promotion.

## Required Future Persistence Point

The future true ledger must start at scan/scout time and persist, per selected
fixture:

- `fixture_id`
- `selected_at`
- `scan_time`
- `kickoff_time`
- official grade
- bookmaker
- market type
- market name
- selection
- line / handicap / over-under
- first saved price
- last pre-kickoff saved price
- snapshot time
- source
- result settlement
- market conflict status
- data quality status

Without these fields, V4 should not claim sustainable price edge.

Guard wording: future scan/scout must persist price timing fields before any
true price-aware edge claim is allowed.

## New Selection Signal Framework

Freeze the next research direction around:

- `strength_gap`: clear team strength difference
- `market_confirmation`: line/price confirms or at least does not conflict
- `price_quality`: saved price clears break-even and is available before kickoff
- `data_quality`: league/sample/source coverage is strong enough
- `lineup/injury/fatigue/travel context`: only from explicit sources
- `historical_form`: auxiliary only, never enough by itself to create A/B

## Risk Guard

- B remains paused for real-time reminders.
- A+B remains daily-report only.
- A remains observation-only until true price-aware replay exists.
- C, SKIP, and shadow-only remain observation-only.
- RF shadow promotion remains blocked.

## Safety

This audit is observation-only. It does not change official logic or production
behavior.
