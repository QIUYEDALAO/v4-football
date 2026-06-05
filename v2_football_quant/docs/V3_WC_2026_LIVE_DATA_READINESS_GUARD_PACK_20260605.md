# V3 WC 2026 Live Data Readiness Guard Pack

## Scope

This pack locks the current live-data readiness posture for the V3 World Cup war room. It is an observation-only guard layer.

It does not call live APIs, generate starting lineups, generate knockout teams, make injury or suspension judgments, create betting recommendations, or affect V4.

## Guard Rules

1. Official lineup guard
   - Group-stage cards must remain `WAIT_OFFICIAL_LINEUP` until an official matchday lineup source is available.
   - No starting XI, predicted XI, or confirmed lineup may be generated from final 26 squad data.

2. Knockout structural guard
   - The 32 knockout cards must remain `STRUCTURAL_PLACEHOLDER`.
   - Knockout team, fixture id, and odds fixture id fields must remain ungenerated until official bracket data exists.
   - Venue fields may remain bound from the locked `wikipedia_snapshot` schedule source.

3. Odds conclusion guard
   - With native opening and closing odds missing, the system may only show gap or readiness status.
   - Timeline deltas may be labeled only as `odds_observation_delta`.
   - The system must not generate movement, steam, drift, sharp, or fund-flow conclusions.

## Locked Current State

- `venue_104=104`
- `group_72 venue_source_required=0`
- `group_72 lineup_wait_official=72`
- `knockout_32 structural_placeholder=32`
- `has_native_opening=false`
- `has_native_closing=false`
- `odds_movement_conclusion_missing=true`

## Checker

`tools/check_v3_worldcup_live_data_readiness_guard.py` verifies:

- coverage radar keeps group lineups at `WAIT_OFFICIAL_LINEUP`
- knockout rows remain structural placeholders with no generated teams
- dashboard read model and war room gap radar expose wait/gap state
- odds status has no native opening or closing odds
- odds output does not claim movement, steam, drift, sharp, or fund-flow conclusions
- runtime/cache/log, V4, and secrets are not staged

The checker writes only a runtime status file under `data/runtime/status/`; that output must not be committed.
