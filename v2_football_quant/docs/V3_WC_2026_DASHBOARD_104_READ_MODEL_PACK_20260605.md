# V3 WC 2026 Dashboard 104 Read Model Pack

Date: 2026-06-05

## Scope

This pack adds a V3 dashboard read model for the 2026 World Cup 104-card
canonical schedule. It does not fetch sources, call live APIs, infer knockout
teams, guess venues, create starting XI, evaluate injuries, predict outcomes,
or affect V4.

## Dashboard Read Model

The dashboard read model is:

- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_dashboard_104_read_model.json`

It reads:

- canonical source: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_cards_index_bridge.json`
- schedule index: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_schedule_index_104.json`
- group-stage view: `data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json`

## Counts

- canonical cards: 104
- group-stage view: 72
- knockout structural slots: 32
- full tournament match data complete: false

## Group-Stage View

The 72-card group-stage file remains available as a scoped view only. It is a
subset of the 104 canonical schedule and must not be used as a complete source.

## Knockout Slots

The 32 knockout entries are displayed as structural placeholders only:

- no teams generated
- no fixture IDs generated
- no odds fixture IDs generated
- no venues generated
- no starting XI, injury judgment, prediction, or betting content

## Double-Read Guard

Dashboard and index consumers must not merge the 104 canonical source and 72
group-stage view as independent complete sources.

Guard:

- `READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE`

## Validation

Run:

```bash
python3 tools/check_v3_worldcup_dashboard_104_read_model.py
python3 tools/check_v3_worldcup_104_cards_index_bridge.py
python3 tools/check_v3_worldcup_war_room_master_index.py
python3 tools/check_v3_worldcup_no_betting_words.py
python3 tools/check_working_tree_dirty_hygiene.py
```
