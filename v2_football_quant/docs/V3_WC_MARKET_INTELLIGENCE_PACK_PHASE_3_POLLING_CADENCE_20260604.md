# V3 WC Market Intelligence Pack Phase 3 Polling Cadence

Date: 2026-06-04

## Scope

Phase 3 adds the polling cadence foundation and append-only odds timeline writer.
It does not enable launchd, cron, or any production timed task.

## Snapshot Limits

The API-Football snapshot remains a current snapshot only.
It is not a native opening line and not a native closing line.
Movement can only be observed after multiple snapshots are appended into the self-built timeline.

## Timeline

`tools/append_v3_worldcup_odds_timeline.py` appends Phase 2 snapshot rows into runtime CSV and JSONL outputs under `data/runtime/v3_worldcup/odds_timeline/`.
The dedupe key includes fixture, bookmaker, normalized market, raw market name, selection, line, odds, API update time, and snapshot id.
Running the same snapshot again skips duplicates; a later snapshot with a new snapshot id can append new rows.

## Availability Monitor

`tools/check_v3_worldcup_odds_availability_monitor.py` reports fixture availability, bookmaker count, market type count, timestamp coverage, records added, duplicates skipped, and quota guard status.

## Disabled Claims

This phase cannot judge money flow.
It does not generate steam, drift, fund-flow, or line-movement claims.

## Safety

- `observation_only=true`
- `betting_recommendation=false`
- `affects_v4=false`
- `has_native_opening=false`
- `has_native_closing=false`
- `movement_requires_timeline=true`
