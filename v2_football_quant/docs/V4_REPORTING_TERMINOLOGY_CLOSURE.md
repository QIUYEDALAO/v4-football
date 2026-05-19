# V4 Reporting Terminology Guard — Phase Closure

Phase: V4-G.1
Date: 2026-05-19
Status: CLOSED (ready for V4-H)

## Background

V4-G established reporting schema/guard but the reporting module contained
`A/B主推` (a V2-era wagering term) in the mobile QQ brief output,
and the full template contained `A+B主推荐`.

These terms are prohibited in V4 formal output because:
- V4 uses A/B/C/SKIP grading only
- "主推" implies wagering recommendation, not analytical conclusion
- Report is post-match attribution, not betting advice
- C is observation-only, SKIP is not recommendation

## Fix Applied

1. **`engine/v4_reporting.py`**: `A/B主推` → `A/B正式结论`
2. **`docs/V4_REPORT_SAMPLE_CONTRACT.md`**: `A/B主推` → `A/B正式结论`
3. **`templates/v4_daily_review_full_template.md`**: `A+B主推荐` → `A+B正式结论`
4. **`tools/check_v4_reporting_guard.py`**: Added comprehensive forbidden term list
   including 主推/强推/重点推荐/重注/必选/投注建议/稳胆/梭哈/WATCH/CANDIDATE/STRONG/V33/V38

## Verification

| Check | Value |
|-------|-------|
| Forbidden output terms in module | 0 |
| Forbidden terms in sample contract | 0 |
| Forbidden terms in templates | 0 |
| C observation-only | True |
| SKIP not recommendation | True |
| Report module no-write safe | True |
| Production verified | False |
| Phase E allowed | False |
| V4-H allowed_to_generate | True |
| V4-H allowed_to_execute | False |
