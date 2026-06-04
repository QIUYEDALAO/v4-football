# V3 WC Market Intelligence Pack Phase 4 Second Snapshot Eligibility

Date: 2026-06-04

## Scope

Phase 4 manually captures a second API-Football snapshot and checks whether odds movement observation is eligible.
This is a timeline eligibility layer only.

## Eligibility

The checker reports `odds_observation_delta`.
It may compare odds values across multiple snapshot ids, count unchanged rows, and count added or removed market rows.
It does not label the result as steam, drift, fund flow, or any trading signal.

Eligibility statuses:

- `NOT_ELIGIBLE_SINGLE_SNAPSHOT`
- `ELIGIBLE_MULTIPLE_SNAPSHOTS_NO_CHANGE`
- `ELIGIBLE_MULTIPLE_SNAPSHOTS_WITH_CHANGE`

## Limits

The snapshot has no native opening line and no native closing line.
Multiple local snapshots allow odds delta observation, but they still do not prove money flow or betting opportunity.

## Deployment

No launchd job is enabled.
No production timed task is created.
The run remains manual and runtime-only.

## Safety

- `observation_only=true`
- `betting_recommendation=false`
- `affects_v4=false`
- `has_native_opening=false`
- `has_native_closing=false`
- `movement_requires_timeline=true`
