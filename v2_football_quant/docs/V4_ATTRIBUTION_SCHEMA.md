# V4 Attribution Schema

Phase: V4-E
Date: 2026-05-19
Status: FINAL (contract only, not yet executing production attribution)

## Overview

V4 attribution schema for post-match attribution of V4 A/B/C/SKIP grades.

## Root Fields

| Field | Value |
|-------|-------|
| schema_version | "1.0" |
| system | "V4" |
| attribution_mode | "paper_only" |
| production_verified | false |
| phase_e_allowed | false |
| verified_write_allowed | false |
| rule_change_allowed | false |

## Match Attribution Item Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| fixture_id | int | yes | Fixture ID |
| date | str | yes | Match date YYYY-MM-DD |
| home | str | yes | Home team |
| away | str | yes | Away team |
| league | str | yes | League name |
| kickoff_time | str | no | Match kickoff time |
| original_grade | str | yes | A/B/C/SKIP |
| original_conclusion | str | no | Raw grade conclusion text |
| ht_goal_observed | bool\|str | yes | true/false/unknown |
| ht_score | str | yes | Half-time score |
| ft_score | str | yes | Full-time score |
| first_ht_goal_minute | int\|null | no | Minute of first HT goal |
| result_source | str | yes | Source of result data |
| result_source_trace | str | no | Trace breadcrumb |
| attribution_status | str | yes | HIT/MISS/VOID/UNKNOWN/SKIP_NOT_SCORED |
| attribution_bucket | str\|null | no | Hit/miss bucket |
| attribution_reason_codes | list[str] | no | Reason codes |
| failure_category | str\|null | no | Failure category |
| diagnosis | str\|null | no | Model diagnosis label |
| root_cause_dimension | str\|null | no | Root cause dimension |
| data_quality | str | yes | Data quality assessment |
| source_quality | str | no | Source quality |
| event_noise | list[str] | no | Event noise tags |
| weather_available | bool | no | Weather data available |
| guard_status | str | no | Guard validation status |
| attribution_allowed | bool | no | Attribution permitted |
| verified_write_allowed | bool | no | Always false for V4-E |
| rule_change_allowed | bool | no | Always false for V4-E |

## Allowed original_grade Values

- `A` - First-half strong recommendation
- `B` - First-half qualified recommendation
- `C` - First-half observation (not primary)
- `SKIP` - Not recommended for first half

## Allowed ht_goal_observed Values

- `true` - HT goal observed
- `false` - No HT goal observed
- `unknown` - Cannot determine

## Allowed attribution_status Values

- `HIT` - Grade matched outcome (A/B only for primary count)
- `MISS` - Grade did not match outcome (A/B only for primary count)
- `VOID` - Void/match occurred but attribution unclear (C allowed)
- `UNKNOWN` - Cannot determine attribution
- `SKIP_NOT_SCORED` - Skipped match, no score expected

## Attribution Rules

- A/B grades count in primary recommendation statistics
- C grades are observation-only, NOT counted in primary hit rate
- SKIP must always be SKIP_NOT_SCORED
- UNKNOWN must not be written as HIT or MISS
- Attribution does NOT equal verification
- Attribution must NOT trigger rule changes
- Single-day results must NOT trigger strategy modifications
