# V4 Match-Date Validation History Recovery Issue List - 20260523

1. Old validation summary was correctly marked stale after scout date contamination repair, but dashboard then displayed all validation rows as N/A.
2. API disabled prevents fresh remote re-attribution, but local trusted attribution history may still be usable.
3. Local `data/v4_archive/v4_result_attribution_*.jsonl` artifacts must be audited before declaring validation unavailable.
4. Stale polluted summary must be separated from trusted match_date attribution rows.
5. Old scan_date-based statistics must not be restored as active validation.
6. Records that reconnect by `fixture_id` to repaired scout `match_date` can enter cumulative validation.
7. Yesterday validation must be filtered by actual `match_date`, not scan date or scout file date.
8. Cumulative validation must be rebuilt from trusted local match_date attribution history.
9. C is deprecated and must not enter active validation, dashboard validation, or A+B.
10. Brief text must not participate in hit-rate calculation.

## Blocker Policy
Directly restoring the stale polluted summary is forbidden. Only trusted match_date attribution can recover active validation.
