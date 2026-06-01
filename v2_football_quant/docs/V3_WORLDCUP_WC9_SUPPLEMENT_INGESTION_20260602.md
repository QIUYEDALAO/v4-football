# V3 World Cup WC9 Supplement Ingestion Layer

Date: 2026-06-02

## Scope

WC9 provides supplement ingestion capability and coverage reporting for V3 World Cup intelligence.

This phase is ingestion/coverage only, not recommendation logic.

## Current Constraints

1. No external API calls.
2. No web fetching.
3. Template files are placeholders, not real supplement data.
4. `TEMPLATE_ONLY` cannot be used for final conclusions.
5. Supplements do not modify roster baseline.
6. Supplements do not override baseline outcomes.
7. Supplements do not affect V4.
8. No betting recommendation output.

## Coverage Model

Categories:
- caps/goals/minutes
- injuries
- friendly form
- market baseline
- club form
- coach profiles
- WC history

Status model:
- `SUPPLEMENT_LAYER_READY_TEMPLATE_ONLY` when only templates exist
- `SUPPLEMENT_LAYER_PARTIAL_READY_WITH_WARN_ONLY` when partial real files exist

## Safety Boundary

- no QQ push
- no pending write
- no validation recompute
- no live bet change
- no cron change
- no default rules change
- no A/B thresholds change

`26_QQ_push_disabled` remains out of scope for this phase.

## Next Step

Real supplement ingestion requires explicit BOSS authorization of approved data sources for injuries/friendlies/market/caps and related fields.
