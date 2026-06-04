# V3 WC War Room Master Index Pack Phase 1

Date: 2026-06-04

## Scope

This phase adds a master index and gap radar for the V3 World Cup war room.
It registers existing observation-only modules and makes their readiness,
source files, checker, data status, and next action visible in one place.

This phase does not add live API calls, cron, launchd, V4 changes, roster
selection, injury evaluation, or match outcome logic.

## Outputs

- `data/manual_sources/v3_worldcup/war_room/v3_wc_war_room_master_index.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc_war_room_gap_radar.json`
- `tools/build_v3_worldcup_war_room_master_index.py`
- `tools/check_v3_worldcup_war_room_master_index.py`

## Registered Modules

1. `venue_stress_layer`
2. `perception_gap_dryrun`
3. `tactical_profile_layer`
4. `closing_1x2_market_structure`
5. `odds_snapshot_timeline`
6. `odds_observation_delta`
7. `final_26_squad_pack`
8. `final_26_squad_profile`
9. `wc10_war_room`
10. `lineup_readiness_pending`

## Safety Contract

Every registered module keeps:

- `observation_only=true`
- `betting_recommendation=false`
- `affects_v4=false`

The global safety block also keeps:

- `no_starting_xi=true`
- `no_prediction=true`

## Gap Radar

The gap radar intentionally keeps the following gaps visible:

- `missing_starting_xi=true`
- `missing_official_matchday_lineup=true`
- `missing_native_opening_odds=true`
- `missing_native_closing_odds=true`
- `missing_odds_movement_conclusion=true`
- `missing_injury_suspension_official_feed=true`

The next data needed remains official matchday lineup, later odds snapshots,
and official injury/suspension source if available.

## Validation

Run:

```bash
python3 tools/build_v3_worldcup_war_room_master_index.py
python3 tools/check_v3_worldcup_war_room_master_index.py
python3 tools/check_v3_worldcup_final_26_pack_manifest.py
python3 tools/check_v3_worldcup_wc10_war_room.py
python3 tools/check_v3_worldcup_no_betting_words.py
```

From the repository root, also run:

```bash
python3 v2_football_quant/tools/check_working_tree_dirty_hygiene.py
```
