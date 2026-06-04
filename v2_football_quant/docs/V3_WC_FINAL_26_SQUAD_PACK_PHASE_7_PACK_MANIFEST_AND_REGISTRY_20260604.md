# V3 WC Final 26 Squad Pack Phase 7

## Scope

Phase 7 adds a unified manifest and registry for the Final 26 Squad Pack.

The manifest records artifact paths, file sizes, SHA-256 hashes, record counts,
locked phase commits, summary counts, WC10 war room node presence, safety fields,
and the raw DOCX policy.

It does not add forecasts, formal recommendations, first-choice elevens, injury
or suspension judgments, stake outputs, fund-flow claims, or V4 grade inputs.

## Manifest

Output:

- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_pack_manifest.json`

The manifest includes:

- `pack_name=V3_WC_FINAL_26_SQUAD_PACK`
- `current_head`
- locked commits for Phases 2 through 6
- ten Final 26 artifacts with `path`, `artifact_type`, `exists`, `file_size`,
  `sha256`, and `record_count`
- counts for teams, players, coaches, complete 26-player squads, and position
  distribution
- WC10 nodes for `final_26_squad_observation` and
  `final_26_squad_profile_observation`
- `raw_docx_policy=ACCEPT_RAW_UNTRACKED`
- `final_pack_acceptance_ready=true`

## Safety Contract

The manifest carries:

- `observation_only=true`
- `no_starting_xi=true`
- `no_injury_judgment=true`
- `no_prediction=true`
- `betting_recommendation=false`
- `affects_v4=false`

## Verification

Run:

```bash
python3 tools/build_v3_worldcup_final_26_pack_manifest.py
python3 tools/check_v3_worldcup_final_26_pack_manifest.py
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
- `coach_count=48`
- `teams_with_26_players=48`
- `GK=145`, `DF=421`, `MF=371`, `FW=311`
