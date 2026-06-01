# V3 World Cup WC8 Final Squad Canonicalization Layer

Date: 2026-06-02

## Scope

WC8 builds the final squad canonicalization layer for V3 World Cup readiness.

This phase is coverage/canonicalization only, not prediction and not betting.

## Current Baseline Reality

1. Current baseline is `46 teams / 1375 players`.
2. This is not the 48-team final squad universe.
3. `1375` is a baseline pool, not final 23-26 man squads.

## WC8 Output Boundary

1. Build canonical schema and template placeholders.
2. Build report for expected `48` vs detected baseline teams.
3. Report missing teams, underfull/overfull checks, and goalkeeper checks.
4. Do not auto-fill missing teams with fake data.
5. Do not auto-trim baseline pool into fake final 26.
6. No betting recommendation output.
7. No impact on V4.

## Data Constraint

Without real final squad source files, status must remain template/missing warn-only.

No conclusion that final squads are complete is allowed at this phase.

## Safety Boundary

- observation-only
- no QQ push
- no pending write
- no validation recompute
- no live bet change
- no cron change
- no default rules change
- no A/B thresholds change
- no V4 logic changes

`26_QQ_push_disabled` remains out of scope for WC8.

## Next Step

Real final squad ingestion requires WC7 source authorization gate PASS plus explicit BOSS authorization of trusted final squad data sources.
