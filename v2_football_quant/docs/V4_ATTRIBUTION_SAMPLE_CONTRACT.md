# V4 Attribution Sample Contract

Phase: V4-E
Date: 2026-05-19
Status: CONTRACT ONLY (no execution, no verified, no rule changes)

## Sample 1: Grade A → HT Goal

```
original_grade = "A"
ht_goal_observed = true
attribution_status = "HIT"
failure_category = null
rule_change_allowed = false
verified_write_allowed = false
```

Conclusion: Model correctly predicted HT goal. Counted as primary hit (A grade).

## Sample 2: Grade B → No HT Goal

```
original_grade = "B"
ht_goal_observed = false
attribution_status = "MISS"
failure_category = "no_ht_goal"
rule_change_allowed = false
verified_write_allowed = false
```

Conclusion: Model predicted HT goal but none occurred. Missed. Counted in primary stats.

## Sample 3: Grade C → Observation Only

```
original_grade = "C"
ht_goal_observed = true (or false)
attribution_status = "VOID" (or hit/miss tagged observation-only)
rule_change_allowed = false
verified_write_allowed = false
```

Conclusion: C is observation-only. NOT counted in primary hit rate.

## Sample 4: Grade SKIP → Not Scored

```
original_grade = "SKIP"
attribution_status = "SKIP_NOT_SCORED"
rule_change_allowed = false
verified_write_allowed = false
```

Conclusion: SKIP match. No recommendation expectation. NOT scored.

## Sample 5: Unknown Result → Unknown

```
ht_goal_observed = "unknown"
attribution_status = "UNKNOWN"
rule_change_allowed = false
verified_write_allowed = false
```

Conclusion: Cannot determine attribution. Not written as HIT or MISS.

## Contract Enforcement

- These samples are CONTRACT ONLY
- No files are written to verified paths
- No rolling or weekly stats are triggered
- No QQ push is triggered
- No rule changes are applied
- Grade A/B hit/miss enters primary attribution pool
- Grade C enters observation pool only
- Grade SKIP enters skip pool only
