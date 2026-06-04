# V3 WC 2026 War Room 104 Bridge Pack

Date: 2026-06-05

## Scope

This pack connects the V3 World Cup 2026 104-card canonical schedule index to
the War Room master index. It does not fetch sources, call live APIs, infer
knockout teams, guess venues, create starting XI, evaluate injuries, predict
outcomes, or affect V4.

## War Room 104 Source

The War Room master index registers:

- module: `match_card_104_canonical_index`
- canonical source: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_cards_index_bridge.json`
- schedule index: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_schedule_index_104.json`

The canonical source has:

- `canonical_card_count=104`
- `group_stage_view_count=72`
- `knockout_slot_count=32`
- `full_tournament_match_data_complete=false`
- `knockout_slot_policy=STRUCTURAL_ONLY_NO_TEAM_GENERATED`

## Group-Stage View

The existing 72-card match-card file remains the group-stage view:

- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json`

Consumers may use it for group-stage pages, but must not report it as the full
tournament source.

## Knockout Slots

The 32 knockout entries are structural slots only. They intentionally do not
contain teams, fixture IDs, odds fixture IDs, venues, lineup claims, injury
judgments, predictions, or recommendations.

## Dashboard / Index Read Policy

Consumers must use either:

- the 104 canonical source for full-tournament navigation, or
- the 72 group-stage view for group-stage-only pages.

They must not merge both as complete independent sources.

Guard:

- `READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE`

## Validation

Run:

```bash
python3 tools/check_v3_worldcup_104_cards_index_bridge.py
python3 tools/check_v3_worldcup_war_room_master_index.py
python3 tools/check_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_no_betting_words.py
python3 tools/check_working_tree_dirty_hygiene.py
```
