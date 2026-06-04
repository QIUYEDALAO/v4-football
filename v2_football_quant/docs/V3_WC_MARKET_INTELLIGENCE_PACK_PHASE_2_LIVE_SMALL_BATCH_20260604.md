# V3 WC Market Intelligence Pack Phase 2 Live Small Batch

Date: 2026-06-04

## Scope

Phase 2 validates that the Phase 1 odds snapshot runner can call API-Football in live mode for a controlled small batch.
The layer remains observation-only and does not affect V4.

## Live Availability

API-Football live odds access is available when the local private shell environment provides the key.
The runner never prints the key, never writes it to runtime output, and only reports boolean availability during manual verification.

## Quota Strategy

The current account budget is approximately 7500 requests per day.
The script still preserves a hard per-run quota guard.
Recommended polling strategy:

- small smoke test: 1 fixture
- batch sanity test: 5 fixtures
- controlled full group-stage snapshot: 72 fixtures
- production polling should keep per-run caps explicit and leave daily reserve for retries and unrelated production jobs

## Snapshot Limits

The current API snapshot is not an opening line and not a closing line.
`has_native_opening=false` and `has_native_closing=false` stay fixed.
Odds movement requires a self-built timeline from repeated snapshots.

## Parser Safety

Live parsing is null-safe.
Unknown market names are preserved as raw rows with `market_type=OTHER_MARKET`.
Missing odds or line values are WARN_ONLY data quality findings, not scoring signals.

## Safety

- `observation_only=true`
- `betting_recommendation=false`
- `affects_v4=false`
- `scoring_changed=false`
- no steam, drift, or fund-flow judgment is generated
