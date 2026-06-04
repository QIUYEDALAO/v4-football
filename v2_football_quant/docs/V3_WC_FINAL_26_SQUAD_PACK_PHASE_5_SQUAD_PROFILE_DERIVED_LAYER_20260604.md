# V3 WC Final 26 Squad Pack Phase 5

## Scope

Phase 5 adds a squad profile derived observation layer from the official FIFA
final 26 canonical files and the existing war room UI payload.

This layer is observation-only. It does not create a starting XI, injury or
suspension judgment, match forecast, formal recommendation, or V4 grade input.

## Inputs

- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_players.csv`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_players.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_teams.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_team_observation_cards.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_war_room_ui_payload.json`

## Outputs

- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_observation.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_team_cards.json`

## Profile Fields

The global observation and each team card include:

- team and player counts
- position distribution
- age profile with average, median, buckets, youngest player, and oldest player
- height profile with average, median, buckets, tallest player, and shortest player
- club profile with club count and top clubs
- position-group profiles for GK, DF, MF, and FW average age and height
- roster observation rankings for oldest, youngest, tallest, and shortest squad averages

Domestic and foreign club counts are left as not derivable because the current
canonical layer does not include a reliable team country code for every squad.
Club country suffix counts are retained as observation data.

## Safety Contract

Every output carries:

- `observation_only=true`
- `no_starting_xi=true`
- `no_injury_judgment=true`
- `no_prediction=true`
- `betting_recommendation=false`
- `affects_v4=false`

Observation rankings are roster-profile rankings only. They are not strength,
forecast, or formal recommendation rankings.

## Verification

Run:

```bash
python3 tools/build_v3_worldcup_final_26_squad_profile_observation.py
python3 tools/check_v3_worldcup_final_26_squad_profile_observation.py
python3 tools/check_v3_worldcup_final_26_war_room_ui_payload.py
python3 tools/check_v3_worldcup_final_26_war_room_observation_layer.py
python3 tools/check_v3_worldcup_final_26_squads.py
python3 tools/check_v3_worldcup_wc10_war_room.py
python3 tools/check_v3_worldcup_no_betting_words.py
```

Expected counts:

- `team_count=48`
- `total_players=1248`
- every team has `player_count=26`
- `GK=145`, `DF=421`, `MF=371`, `FW=311`
