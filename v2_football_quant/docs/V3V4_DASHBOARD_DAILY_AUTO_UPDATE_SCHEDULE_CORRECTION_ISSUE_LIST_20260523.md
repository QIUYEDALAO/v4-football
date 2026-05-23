# V3/V4 Dashboard Daily Auto Update Schedule Correction Issue List - 20260523

1. 12:00 is the V4 scan start time, not the dashboard refresh time.
2. The 12:00 scan needs completion buffer before dashboard candidate refresh.
3. after-scan refresh must be fixed at 13:00.
4. The 13:00 validation dry-run also needs completion buffer before validation dashboard refresh.
5. after-validation refresh must be fixed at 13:30.
6. after-scan must not update yesterday validation, cumulative validation, validation summary, attribution, or review.
7. after-validation must not update candidate source, brief source, candidate raw numbers, or V4 strategy.
8. Both refresh gates must never run capture, push, or cloud publish.
9. This phase is plan-only: cron is documented but not enabled or created.
10. Checkers must reject early dashboard refresh plans such as 12:10 and any phase-boundary mixing.

## Blocker Policy
Any plan that refreshes the dashboard at 12:10 or lets after-scan touch validation is BLOCKER.
