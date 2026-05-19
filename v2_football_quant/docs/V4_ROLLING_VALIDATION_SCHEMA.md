# V4 Rolling Validation Schema

Phase: V4-F
Date: 2026-05-19
Status: FINAL (contract only, not yet executing rolling validation)

## Root Fields

| Field | Value |
|-------|-------|
| schema_version | "1.0" |
| system | "V4" |
| rolling_mode | "paper_only" |
| production_verified | false |
| phase_e_allowed | false |
| verified_write_allowed | false |
| rule_change_allowed | false |

## Window Fields

| Field | Type | Description |
|-------|------|-------------|
| window_days | int | Rolling window (7/14/30) |
| sample_start | str | Window start date |
| sample_end | str | Window end date |
| total_matches | int | All matches in window |
| scored_samples | int | Samples with known result |
| excluded_samples | int | Excluded (UNKNOWN/VOID/API_DISABLED) |
| unknown_samples | int | attribution_status=UNKNOWN |
| api_disabled_samples | int | result_source=API_DISABLED |
| skip_samples | int | original_grade=SKIP |
| c_observation_samples | int | original_grade=C (observation) |
| a_samples | int | original_grade=A |
| b_samples | int | original_grade=B |

## Grade Bucket Fields

| Field | Type | Description |
|-------|------|-------------|
| grade | str | A/B/C/SKIP |
| sample_count | int | Samples in this grade |
| hit_count | int | HIT (A/B only; C observation only) |
| miss_count | int | MISS (A/B only) |
| void_count | int | VOID |
| unknown_count | int | UNKNOWN |
| hit_rate | float | hit_count / (hit_count + miss_count) |
| miss_rate | float | miss_count / (hit_count + miss_count) |
| min_sample_met | bool | Sample threshold reached |
| confidence_level | str | HIGH/MEDIUM/LOW/INSUFFICIENT |
| notes | str | Warnings/observations |

## Attribution Status → Rolling Mapping

| attribution_status | Rolling bucket | Counted in hit/miss |
|-------------------|----------------|---------------------|
| HIT | A/B: hit_count; C: observation_only | A/B only |
| MISS | A/B: miss_count; C: observation_only | A/B only |
| VOID | void_count | no |
| UNKNOWN | unknown_samples | no |
| SKIP_NOT_SCORED | skip_samples | no |

## Exclusion Rules

- `attribution_status=UNKNOWN` → excluded from hit/miss
- `result_source=API_DISABLED` → excluded from hit/miss
- `result_known=false` → excluded from hit/miss
- `attribution_status=VOID` → excluded from hit/miss
- `original_grade=SKIP` → skip_samples, not recommendation
- `original_grade=C` → observation_only, not primary recommendation

## Minimum Sample Rules

- A/B combined < 10 → confidence = INSUFFICIENT
- A/B combined 10-29 → confidence = LOW
- A/B combined 30-99 → confidence = MEDIUM
- A/B combined >= 100 → confidence = HIGH
- Rolling must NOT trigger rule changes on small samples
