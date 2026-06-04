# V3 WC Market Intelligence Pack Phase 5 Third Snapshot Delta Observation

Date: 2026-06-04

## Scope

Phase 5 manually captures a third API-Football snapshot and appends it to the local runtime timeline.
This phase only checks whether `odds_observation_delta` can be observed across repeated snapshots.

## Observation Rules

The only permitted delta label is `odds_observation_delta`.
If odds values change, the system may report changed and unchanged record counts.
If odds values do not change, the system reports `ELIGIBLE_MULTIPLE_SNAPSHOTS_NO_CHANGE`.

## Disabled Claims

This phase does not judge money flow.
It does not identify steam, drift, sharp action, or any betting signal.
It does not claim a wagering opportunity.

## Snapshot Limits

API-Football snapshots are current snapshots only.
They do not provide native opening or native closing lines.
Opening and closing remain unavailable unless a source explicitly provides them later.

## Deployment

No launchd job is enabled.
No production timed task is created.
This remains a manual observation-only phase.

## Safety

- `observation_only=true`
- `betting_recommendation=false`
- `affects_v4=false`
- `has_native_opening=false`
- `has_native_closing=false`
- `movement_requires_timeline=true`
