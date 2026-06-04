# V3 WC Starting XI Formation Observation Pack Phase 1

## Scope

Phase 1 freezes the source strategy and schema for a future formation and role
pool observation layer.

This phase does not output an eleven-player lineup, does not infer injury or
suspension status, does not forecast matches, does not create formal advice, and
does not affect V4.

## Inputs

- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_players.csv`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_players.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_teams.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_observation.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_team_cards.json`
- `data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json`

## Source Strategy

- Final 26 canonical files are the official squad boundary.
- Tactical profile and historical formation samples are observation inputs only.
- Matchday lineup source is reserved for a future official source and is not
  available in Phase 1.
- Role pools are not lineup selections; they are schema slots for later
  observation data.

## Frozen Schema

Schema file:

- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_starting_xi_formation_observation_schema.json`

The schema defines:

- `source_strategy`
- `team_observation_schema`
- `player_role_pool_schema`
- `formation_observation_schema`
- `safety`

## Safety

The schema carries:

- `observation_only=true`
- `no_starting_xi_generated=true`
- `no_injury_judgment=true`
- `no_prediction=true`
- `betting_recommendation=false`
- `affects_v4=false`

## Verification

Run:

```bash
python3 tools/check_v3_worldcup_starting_xi_formation_observation_design.py
python3 tools/check_v3_worldcup_final_26_pack_manifest.py
python3 tools/check_v3_worldcup_final_26_squad_profile_observation.py
python3 tools/check_v3_worldcup_wc10_war_room.py
python3 tools/check_v3_worldcup_no_betting_words.py
python3 tools/check_working_tree_dirty_hygiene.py
```
