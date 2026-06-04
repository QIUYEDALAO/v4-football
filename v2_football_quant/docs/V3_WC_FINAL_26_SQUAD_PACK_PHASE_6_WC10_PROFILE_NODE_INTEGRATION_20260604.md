# V3 WC Final 26 Squad Pack Phase 6

## Scope

Phase 6 integrates the Phase 5 squad profile derived observation layer into the
V3 WC10 war room JSON summary.

This is a display and JSON aggregation layer only. It does not create match
forecasts, formal recommendations, first-choice elevens, injury or suspension
judgments, stake outputs, fund-flow claims, or V4 grade inputs.

## Inputs

- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_observation.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_team_cards.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_war_room_ui_payload.json`

## WC10 Node

The WC10 war room JSON now includes:

- `final_26_squad_profile_observation`

Node fields:

- `module=final_26_squad_profile_observation`
- `source_profile_observation`
- `source_profile_team_cards`
- `team_count`
- `total_players`
- `position_distribution`
- `age_profile`
- `height_profile`
- `club_profile`
- `position_group_profiles`
- `observation_rankings`
- `team_profile_refs`
- `safety`

Observation rankings are named only as `roster_observation_ranking`.

## Safety Contract

The node carries:

- `observation_only=true`
- `no_starting_xi=true`
- `no_injury_judgment=true`
- `no_prediction=true`
- `betting_recommendation=false`
- `affects_v4=false`

## Verification

Run:

```bash
python3 tools/build_v3_worldcup_final_26_squad_profile_observation.py
python3 tools/check_v3_worldcup_final_26_squad_profile_observation.py
python3 tools/build_v3_worldcup_wc10_war_room.py
python3 tools/check_v3_worldcup_wc10_war_room.py
python3 tools/check_v3_worldcup_final_26_war_room_ui_payload.py
python3 tools/check_v3_worldcup_final_26_war_room_observation_layer.py
python3 tools/check_v3_worldcup_final_26_squads.py
python3 tools/check_v3_worldcup_no_betting_words.py
```

Expected profile counts:

- `team_count=48`
- `total_players=1248`
- `GK=145`, `DF=421`, `MF=371`, `FW=311`
