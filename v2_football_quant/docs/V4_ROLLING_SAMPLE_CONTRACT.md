# V4 Rolling Validation Sample Contract

Phase: V4-F
Date: 2026-05-19
Status: CONTRACT ONLY (no execution, no verified, no rule changes)

## Sample Classification Rules

| # | original_grade | attribution_status | Rolling result | Primary hit/miss |
|---|---------------|-------------------|---------------|------------------|
| 1 | A | HIT | A hit_count | Yes |
| 2 | B | MISS | B miss_count | Yes |
| 3 | C | HIT | c_observation_samples | No |
| 4 | C | MISS | c_observation_samples | No |
| 5 | SKIP | SKIP_NOT_SCORED | skip_samples | No |
| 6 | A | UNKNOWN | unknown_samples | No |
| 7 | B | result_source=API_DISABLED | api_disabled_samples | No |
| 8 | A | result_known=false | excluded_samples | No |

## Sample 1: A / HIT

```
original_grade = "A"
attribution_status = "HIT"
result_known = true
→ Rolling: A hit_count +1
→ Primary recommendation: Yes
```

## Sample 2: B / MISS

```
original_grade = "B"
attribution_status = "MISS"
result_known = true
→ Rolling: B miss_count +1
→ Primary recommendation: Yes
```

## Sample 3: C / HIT

```
original_grade = "C"
attribution_status = "HIT"
result_known = true
→ Rolling: c_observation_samples +1
→ Primary recommendation: NO (observation only)
```

## Sample 4: SKIP / SKIP_NOT_SCORED

```
original_grade = "SKIP"
attribution_status = "SKIP_NOT_SCORED"
→ Rolling: skip_samples +1
→ Primary hit/miss: NO
```

## Sample 5: UNKNOWN

```
attribution_status = "UNKNOWN"
result_known = false
→ Rolling: unknown_samples +1
→ Primary hit/miss: NEVER
```

## Sample 6: API_DISABLED

```
result_source = "API_DISABLED"
→ Rolling: api_disabled_samples +1
→ Primary hit/miss: NEVER
```

## Contract Enforcement

- These samples are CONTRACT ONLY
- No rolling execution in this phase
- No verified files are written
- No rule changes are applied
