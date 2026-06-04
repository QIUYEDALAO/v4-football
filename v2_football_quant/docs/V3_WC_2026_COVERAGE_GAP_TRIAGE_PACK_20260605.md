# V3 WC 2026 Coverage Gap Triage Pack

## Scope

This pack triages the `final26` and `lineup` gaps reported by the 104 coverage gap radar.

No live API, venue guessing, lineup generation, betting output, runtime submission, or V4 change is included.

## Finding

The three `final26` and `lineup` gaps were deterministic team key mapping gaps, not true roster or lineup source gaps.

Affected group-stage cards:

- `wc2026_104_017`: Curaçao vs Côte D'Ivoire
- `wc2026_104_039`: Germany vs Côte D'Ivoire
- `wc2026_104_062`: Côte D'Ivoire vs Ecuador

The match-card source used:

- `cote_divoire`

The final 26 and lineup readiness canonical sources use:

- `cote_d_ivoire`

## Fix

`tools/build_v3_worldcup_104_coverage_gap_radar.py` now applies a local deterministic alias:

- `cote_divoire -> cote_d_ivoire`

The radar keeps the original source slug and records:

- `home_canonical_team_slug`
- `away_canonical_team_slug`
- `team_slug_alias_applied`

## Result

- `final26_gap_card_count=0`
- `lineup_gap_card_count=0`
- `team_slug_alias_applied_count=3`
- `venue_source_required_count=72` remains unchanged

Venue gaps remain `VENUE_SOURCE_REQUIRED`; no venue was filled or guessed.
