# V3 WC4G Formation Tactical Profile Layer Code Ready

## Scope

WC4G converts the WC4F tactical profile source pack into a repeatable V3 World Cup observation layer.

This layer is observation-only. It does not enter scoring, does not output recommendations, and does not affect V4.

## Inputs

- `reports/v3_wc4f_tactical_profiles.csv`
- `reports/v3_wc4f_formation_matchups.csv`
- `reports/v3_wc4f_observations.csv`
- `reports/v3_wc4f_tactical_profiles.md`

The local builder also supports the existing sibling runtime pack under `../v4-football/reports` when the repo-local reports directory has not been populated.

## Outputs

- `data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json`
- `data/runtime/status/v3_worldcup_tactical_profile_layer_20260604.json`

Each team profile includes:

- `team`
- `common_formation`
- `alternative_formations`
- `formation_data_source`
- `formation_sample_count`
- `tactical_tags`
- `observation_confidence`
- `data_quality`
- `no_scoring=true`
- `betting_recommendation=false`
- `affects_v4_grade=false`

## Observation Tags

- `LOW_BLOCK_WATCH`
- `COUNTER_ATTACK_WATCH`
- `OPEN_GAME_WATCH`
- `HIGH_PRESS_FATIGUE_WATCH`
- `MIDFIELD_CONGESTION_WATCH`
- `FORMATION_DATA_INSUFFICIENT`

## Acceptance

- 48 team profiles.
- 24 teams with real formation samples.
- 24 teams marked `FORMATION_DATA_INSUFFICIENT`.
- 72 historical formation matchup samples.
- 14 unique formations.
- War room displays the layer as tactical profile observation only.
