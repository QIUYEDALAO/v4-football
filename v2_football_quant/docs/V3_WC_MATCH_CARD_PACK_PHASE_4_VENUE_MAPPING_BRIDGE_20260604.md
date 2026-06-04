# V3 WC Match Card Pack Phase 4

Date: 2026-06-05

## Scope

This phase adds a venue mapping bridge for the V3 World Cup match cards. It
searches only local repository sources and binds match venues only when a local
per-match venue source exists. It does not call live APIs, use network sources,
enable automation, modify V4, create lineup claims, evaluate injuries, or create
outcome logic.

Current match cards cover the 72 group-stage fixtures only. They are not the
complete 2026 World Cup match set; the full tournament is expected to contain
104 matches. This phase does not generate knockout teams, infer knockout
pairings, or guess venues.

## Outputs

- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_venue_mapping_bridge.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_venue_mapping_bridge_summary.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_venue_mapping_manual_template.csv`
- `tools/build_v3_worldcup_venue_mapping_bridge.py`
- `tools/check_v3_worldcup_venue_mapping_bridge.py`

Updated:

- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_card_summary.json`
- `tools/build_v3_worldcup_match_cards.py`
- `tools/check_v3_worldcup_match_cards.py`
- `tools/check_v3_worldcup_match_card_venue_odds_binding.py`

## Venue Source Audit

Local sources checked:

- `data/v3_wc2026/group_schedule.json`
- `data/runtime/v3_worldcup/thestatsapi_cache/20260602/world_cup_2026/matches_2026_all.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_fixture_mapping_bridge.json`
- `data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json`
- `data/runtime/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json`
- `v4-football/reports/v3_wc_venue_stress_pack.csv`

The venue stress layer provides the 16 host venues, but no local source provides
the per-match venue allocation for the 72 group-stage fixtures. The bridge
therefore keeps all rows unmapped with `VENUE_SOURCE_REQUIRED`.

## Manual Template

`v3_wc2026_venue_mapping_manual_template.csv` has one row per match card and is
ready for later manual review. Empty venue fields are intentional until an
approved source is added.

## Safety Contract

Every venue bridge row keeps:

- `observation_only=true`
- `no_prediction=true`
- `betting_recommendation=false`
- `affects_v4=false`

Venue stress remains an observation field only and is not an outcome or trading
signal.

## Validation

Run:

```bash
python3 tools/build_v3_worldcup_venue_mapping_bridge.py
python3 tools/check_v3_worldcup_venue_mapping_bridge.py
python3 tools/build_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_match_card_venue_odds_binding.py
python3 tools/check_v3_worldcup_fixture_mapping_bridge.py
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
