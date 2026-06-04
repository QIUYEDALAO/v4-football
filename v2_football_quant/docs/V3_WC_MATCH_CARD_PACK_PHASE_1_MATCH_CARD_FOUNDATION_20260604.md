# V3 WC Match Card Pack Phase 1

Date: 2026-06-04

## Scope

This phase creates match-level war room cards from existing V3 observation
layers. The cards summarize fixture identity, Final 26 profile references,
lineup readiness, historical formation observation, venue layer readiness,
odds snapshot status, odds observation delta status, and data gaps.

No live API call, cron, launchd, V4 change, roster selection, injury
evaluation, match outcome logic, or trading signal is added.

## Outputs

- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_card_summary.json`
- `tools/build_v3_worldcup_match_cards.py`
- `tools/check_v3_worldcup_match_cards.py`

## Source Inputs

- `data/manual_sources/v3_worldcup/war_room/v3_wc_war_room_master_index.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc_war_room_gap_radar.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_pack_manifest.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_team_cards.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_lineup_readiness_team_status.json`
- `data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json`
- `data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json`
- `data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json`

## Current Data Limits

The current 2026 fixture source has 72 group-stage matches only. This is not the
complete 2026 World Cup match set; the full tournament is expected to contain
104 matches. The remaining knockout-stage teams and pairings are not generated
or inferred by this pack.

The current source does not include venue mapping. Therefore each match card
keeps `venue=VENUE_NOT_MAPPED` and a data gap named
`match_venue_not_mapped_to_fixture`.

Odds snapshots exist globally, but current IDs are not mapped to these match
cards, so per-card odds fields stay status-only.

## Safety Contract

Each card keeps:

- `observation_only=true`
- `no_starting_xi_generated=true`
- `no_prediction=true`
- `no_injury_judgment=true`
- `betting_recommendation=false`
- `affects_v4=false`

The odds observation delta status is not interpreted as money flow.

## Validation

Run:

```bash
python3 tools/build_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_war_room_master_index.py
python3 tools/check_v3_worldcup_lineup_readiness_schema.py
python3 tools/check_v3_worldcup_final_26_pack_manifest.py
python3 tools/check_v3_worldcup_wc10_war_room.py
python3 tools/check_v3_worldcup_no_betting_words.py
```

From the repository root, also run:

```bash
python3 v2_football_quant/tools/check_working_tree_dirty_hygiene.py
```
