# V3/V4 Dashboard Validation Visibility Recovery Issue List - 20260523

Phase: V3V4-DASHBOARD-VALIDATION-VISIBILITY-RECOVERY-20260523

## Issues

1. Dashboard validation data appears invisible after scout date repair.
2. Validation summary may be stale/rebased with API disabled, causing display rows to look empty.
3. Validation module must remain visible even when every metric is N/A.
4. Yesterday validation and cumulative validation must be fixed visible blocks.
5. C validation must not be restored.
6. Last-7-day validation must not be restored.
7. Formal brief must not be used for hit-rate calculation.
8. Unknown/no-result states must not be rendered as fake 0% hit rates.
9. Checkers must fail if the validation card disappears from file or served HTML.
10. Git commit remains blocked until validation visibility is restored.

## Required Display Contract

- Always render `V3/V4 比赛验证`.
- Always render `昨日验证` and `累计验证` in one card.
- Always render A, B, A+B rows.
- If results are unavailable, show `N/A` and an explicit reason.
- Put source files, unknown counts, stale/API-disabled details in the audit fold.

## Forbidden

- V2/V33 restore.
- C validation or last-7-day validation return.
- Brief-derived hit rate.
- Fake 0% rate.
- capture / QQ push / cloud publish / cron / git commit / git push.
