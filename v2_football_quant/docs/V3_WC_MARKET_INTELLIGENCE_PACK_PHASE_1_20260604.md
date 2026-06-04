# V3 WC Market Intelligence Pack Phase 1

Date: 2026-06-04

## Scope

This phase adds a 2026 World Cup odds snapshot timeline foundation for V3 observation work.
It is not connected to V4 grading, does not change scoring, and does not produce betting guidance.

## Inputs

- 2026 fixture source: `data/v3_wc2026/group_schedule.json`
- Existing API-Football mapping/cache reference: `data/runtime/v3_worldcup/apifootball_odds_freeze/20260604/`
- Current API source: API-Football is available through the existing provider routing.
- TheStatsAPI: no local key is configured for this phase.

## Runner

`tools/run_v3_worldcup_odds_snapshot_dryrun.py` supports:

- fixture id allow-list through `--fixture-id`
- `--limit` to cap one run
- dry-run by default, with explicit `--live` required before any API-Football odds call
- runtime JSON and CSV output under `data/runtime/v3_worldcup/odds_snapshot_dryrun/`
- no API key printing and no committed runtime output

## Quota Guard

Free plan default request ceiling is 80 requests per run.
If selected fixture count exceeds the effective request limit, the runner writes `QUOTA_GUARD_STOP`,
emits a quota warning, and executes zero remote requests.

## Market Normalization

The snapshot foundation standardizes these markets:

- `MATCH_WINNER_1X2`: 1X2 / Match Winner
- `ASIAN_HANDICAP`: Asian Handicap
- `GOALS_OVER_UNDER`: Goals Over/Under
- `BOTH_TEAMS_TO_SCORE`: BTTS
- `DOUBLE_CHANCE`: Double Chance
- `FIRST_HALF_WINNER`: 1st Half Winner

## Timeline Schema

The tracker template writes:

- `snapshot_time`
- `api_update_time`
- `fixture_id`
- `year`
- `home`
- `away`
- `bookmaker`
- `market_type`
- `market_name_raw`
- `selection`
- `line`
- `odds`
- `source`
- `is_current_snapshot=true`
- `has_native_opening=false`
- `has_native_closing=false`
- `movement_requires_timeline=true`

## Data Limits

A single snapshot has no native opening or closing price.
Any market movement analysis requires a self-built timeline from repeated snapshots.
This phase explicitly avoids steam, drift, and fund-flow labeling because one snapshot cannot support those claims.

## Safety

- `observation_only=true`
- `betting_recommendation=false`
- `affects_v4=false`
- `scoring_changed=false`
