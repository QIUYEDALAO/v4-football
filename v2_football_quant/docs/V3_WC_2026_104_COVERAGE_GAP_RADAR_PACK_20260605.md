# V3 WC 2026 104 Coverage Gap Radar Pack

## Scope

This pack adds a coverage and gap radar for the V3 World Cup 2026 104-card canonical schedule chain.

- Canonical source: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_cards_index_bridge.json`
- Coverage rows: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_coverage_gap_radar.json`
- Coverage summary: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_coverage_gap_radar_summary.json`
- Group-stage view: `GROUP_STAGE_ONLY_72`
- Knockout slots: `STRUCTURAL_PLACEHOLDER`

## Coverage Fields

The radar tracks each canonical card across:

- team
- venue
- fixture_id
- odds_fixture_id
- final26
- lineup
- war_room
- dashboard

Group-stage cards use local 72-card schedule data. Knockout cards remain structural placeholders and do not generate teams, fixtures, odds IDs, venues, lineups, or final 26 bindings.

## Read Model Integration

The War Room master index registers `coverage_gap_radar_104`.

The dashboard 104 read model exposes `coverage_gap_summary` so the UI/API read surface can show 104 coverage and gaps without treating the 72-card group-stage view as a complete tournament source.

## Safety

- observation_only=true
- no_starting_xi_generated=true
- no_prediction=true
- no_injury_judgment=true
- betting_recommendation=false
- affects_v4=false

No live API call, network access, V4 change, runtime submission, team prediction, venue guessing, or betting output is part of this pack.
