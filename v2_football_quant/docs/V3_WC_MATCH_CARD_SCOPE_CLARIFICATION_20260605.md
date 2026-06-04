# V3 WC Match Card Scope Clarification

Date: 2026-06-05

## Scope Lock

The current V3 World Cup match card pack is **group stage only**.

- Current match cards: 72
- Current teams covered: 48
- 2026 total expected tournament matches: 104
- Full tournament complete: false

The current 72 cards are not the complete 2026 World Cup match set. They must
not be reported as the complete 2026 World Cup match set. They represent only
the group-stage fixtures available in the local source set.

## Knockout Stage Boundary

The remaining 32 expected matches are knockout-stage fixtures. They are not
generated in this pack because the actual knockout teams and pairings are not
known from the current local source data.

This pack must not:

- generate knockout teams
- infer knockout pairings
- guess venues
- create starting XI or predicted XI
- create injury or suspension judgment
- create prediction, recommendation, or betting content
- affect V4

## Venue Boundary

Venue mapping remains source-bound. The current local source set does not
provide per-match venue allocation for the 72 group-stage cards, so venue
mapping remains:

- `venue_mapped=0`
- `manual_template=72`
- reason: `VENUE_SOURCE_REQUIRED`

## Checker Guard

`tools/check_v3_worldcup_match_cards.py` now treats `72` as the locked current
scope count for group-stage-only cards and records the 2026 total expected
tournament count as `104`. The checker must fail if this pack is presented as a
complete World Cup match set.
