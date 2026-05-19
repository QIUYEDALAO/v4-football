# V4 Rolling Validation Guard

Phase: V4-F
Date: 2026-05-19
Status: FINAL

## 1. Input Requirements

- Must use V4 attribution records (engine/v4_result_attribution.py output)
- Must preserve original_grade (A/B/C/SKIP)
- Must preserve attribution_status (HIT/MISS/VOID/UNKNOWN/SKIP_NOT_SCORED)
- Must preserve result_known (true/false)
- Must preserve result_source (API enabled/API_DISABLED)
- Must preserve guard_status

## 2. Classification Rules

| original_grade | attribution_status | Rolling classification |
|---------------|-------------------|----------------------|
| A | HIT | recommendation hit |
| A | MISS | recommendation miss |
| B | HIT | recommendation hit |
| B | MISS | recommendation miss |
| C | any | observation-only, NOT primary |
| SKIP | SKIP_NOT_SCORED | skip behavior, NOT recommendation |
| any | UNKNOWN | excluded from hit/miss |
| any | VOID | excluded from hit/miss |
| any | result_source=API_DISABLED | excluded from hit/miss |
| any | result_known=false | excluded from hit/miss |

## 3. Threshold Rules

- A/B combined < 10 → INSUFFICIENT confidence
- Minimum 7-day window for any conclusion
- 14-day window recommended for trend analysis
- 30-day window required for rule change suggestions
- Single-day results must NOT change rules

## 4. Prohibited Actions

| Action | Reason |
|--------|--------|
| UNKNOWN counted as MISS | Data contamination |
| API_DISABLED counted as MISS | False negative |
| SKIP counted as recommendation | Scope breach |
| C counted as primary hit | Misrepresentation |
| Single-day rule change | Insufficient sample |
| Rolling writes PRODUCTION_VERIFIED | Scope breach |
| Rolling triggers QQ push | Delivery breach |
| Rolling calls API | Security breach |
| Rolling modifies strategy | Algorithmic safety |
