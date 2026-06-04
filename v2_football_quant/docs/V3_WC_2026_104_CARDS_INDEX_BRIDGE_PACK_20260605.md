# V3 WC 2026 104 Cards Index Bridge Pack

Date: 2026-06-05

## Scope

This pack creates the V3 World Cup 2026 full-tournament match-card index bridge.
It does not fetch new sources, call live APIs, infer knockout teams, guess
venues, create lineups, evaluate injuries, predict outcomes, or affect V4.

## Canonical Source

The canonical full-tournament source is:

- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_cards_index_bridge.json`

It contains 104 canonical index rows:

- 72 group-stage match rows that reference the existing group-stage card view
- 32 structural knockout slots waiting for official fixture/team sources

The 32 knockout rows intentionally keep team, fixture, odds, and venue fields
empty. They are structural tournament slots only, not generated fixtures.

## Group-Stage View

The existing 72-card file remains the group-stage view:

- `data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json`

It must not be reported as the complete 2026 World Cup match set.

## Schedule Index

The schedule index file is:

- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_schedule_index_104.json`

It points to the 104 canonical index and preserves the 72 group-stage view as a
subset. Dashboard or index consumers must read either the 104 canonical index or
the 72 group-stage view for a scoped page, but must not merge both as complete
sources.

## Double-Read Guard

The read policy is:

- canonical reader: `v3_wc2026_104_cards_index_bridge.json`
- group-stage view reader: `v3_wc_match_cards.json`
- duplicate guard: `READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE`

## Validation

Run:

```bash
python3 tools/build_v3_worldcup_104_cards_index_bridge.py
python3 tools/check_v3_worldcup_104_cards_index_bridge.py
python3 tools/check_v3_worldcup_match_cards.py
python3 tools/check_v3_worldcup_no_betting_words.py
python3 tools/check_working_tree_dirty_hygiene.py
```
