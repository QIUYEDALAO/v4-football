# V3 WC Match Card Pack Phase 2

Date: 2026-06-04

## Scope

This phase binds venue and odds status objects into every V3 World Cup match
card. It keeps the cards as observation-only summary objects and does not add
live calls, cron, launchd, V4 changes, roster selection, lineup claims, injury
evaluation, match outcome logic, or trading signals.

## Outputs

- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_card_summary.json`
- `tools/build_v3_worldcup_match_cards.py`
- `tools/check_v3_worldcup_match_cards.py`
- `tools/check_v3_worldcup_match_card_venue_odds_binding.py`

## Venue Binding

Every card now has `venue_binding`:

- `venue_name`
- `venue_slug`
- `venue_stress_status`
- `venue_stress_tags`
- `venue_stress_ref`
- `venue_mapping_status`
- `venue_gap_reason`

The current fixture source has no venue field, so the binding status is
`NOT_MAPPED` for all 72 cards. The venue stress layer remains ready and is
referenced as the source of venue stress tags.

## Odds Binding

Every card now has `odds_binding`:

- `odds_fixture_id`
- `odds_snapshot_status`
- `odds_available`
- `bookmaker_count`
- `market_type_count`
- `odds_observation_delta_status`
- `changed_odds_count`
- `odds_gap_reason`
- `no_money_flow_judgment=true`

The current odds snapshot is globally available, but the match cards do not yet
have a canonical mapping from TheStatsAPI match IDs to API-Football odds fixture
IDs. Per-card odds binding therefore remains `NOT_MAPPED`.

## Safety Contract

Every card keeps:

- `observation_only=true`
- `no_starting_xi_generated=true`
- `no_prediction=true`
- `no_injury_judgment=true`
- `betting_recommendation=false`
- `affects_v4=false`

Odds delta is kept as `odds_observation_delta` only. It is not interpreted as
money flow.

## Validation

Run:

```bash
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
