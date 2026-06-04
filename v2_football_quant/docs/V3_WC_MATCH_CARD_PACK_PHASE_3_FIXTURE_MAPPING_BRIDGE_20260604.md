# V3 WC Match Card Pack Phase 3

Date: 2026-06-05

## Scope

This phase adds a fixture mapping bridge for the V3 World Cup match cards. It
maps each match card to locally available fixture metadata only when the source
supports an exact home/away pair match. It does not call live APIs, enable
automation, modify V4, add lineup claims, evaluate injuries, or create trading
signals.

## Outputs

- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_fixture_mapping_bridge.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_fixture_mapping_bridge_summary.json`
- `tools/build_v3_worldcup_fixture_mapping_bridge.py`
- `tools/check_v3_worldcup_fixture_mapping_bridge.py`

Updated:

- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_card_summary.json`
- `tools/build_v3_worldcup_match_cards.py`
- `tools/check_v3_worldcup_match_cards.py`
- `tools/check_v3_worldcup_match_card_venue_odds_binding.py`

## Mapping Sources

- `data/v3_wc2026/group_schedule.json`
- `data/runtime/v3_worldcup/thestatsapi_cache/20260602/world_cup_2026/matches_2026_all.json`
- `data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json`
- `data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json`

## Mapping Rules

The bridge maps fixture IDs only through exact canonical home/away pairs. Team
name aliases are limited to known source-name differences such as `Ivory Coast`
to `Côte D'Ivoire`, `Cape Verde Islands` to `Cabo Verde`, and `Czech Republic`
to `Czechia`.

Venue mapping stays unmapped when the fixture source has no venue name. No venue
is inferred from country, team, kickoff date, or host assumptions.

Odds fixture IDs reuse the mapped API-Football fixture IDs. Odds availability is
true only when the mapped fixture appears in the existing local live snapshot
success list.

## Safety Contract

Every bridge row keeps:

- `observation_only=true`
- `no_prediction=true`
- `betting_recommendation=false`
- `affects_v4=false`

The bridge does not contain starting XI, injury judgment, or money-flow labels.

## Validation

Run:

```bash
python3 tools/build_v3_worldcup_fixture_mapping_bridge.py
python3 tools/check_v3_worldcup_fixture_mapping_bridge.py
python3 tools/build_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_match_card_venue_odds_binding.py
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
