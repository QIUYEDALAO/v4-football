# V3/V4 Dashboard Dynamic Date Marker + Match-Date TZ Hotfix Issue List - 20260524

Phase: V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX-20260524

## P0 Issues

1. `tools/run_v3v4_dashboard_daily_update.py` still resolves after-scan markers from fixed 20260523 paths.
2. 20260524 V4 daily scan produced formal scan outputs, but after-scan could still report `SCAN_NOT_READY` because the runner was bound to stale marker paths.
3. The 20260524 `v3v4_dashboard_brief_resolution_20260524.json` marker was either missing or could be stale/regenerated with an incorrect today flag.
4. The 20260524 `v3v4_dashboard_candidate_view_20260524.json` marker was either missing or could be stale/regenerated with stale source metadata.
5. 13:30 after-validation runner has the same class of date marker risk if validation summary paths are not derived from `--date`.
6. 14:00 final validation/dashboard runner has the same class of source-hash risk if previous validation markers or summaries are not derived from `--date`.
7. V4 scout `match_date` can still be wrong if kickoff is truncated in operator CST rather than the actual match-local timezone.
8. Djurgardens-related A-grade expectation must be audited as a filter/source issue only; no manual insertion into the brief is allowed.
9. MLS conservatism and H2H vs `recent_last_n` conflicts are observation-only items; no strategy, whitelist, threshold, or recency-rule changes are allowed in this hotfix.
10. This hotfix must not run a full scan, capture, QQ push, cloud publish, or mutate raw candidate/validation/attribution results.

## Required Closure

- Replace active hardcoded dashboard marker dates with `--date`-scoped marker resolution.
- Rebuild 20260524 dashboard markers from existing formal scout, brief, and scan performance outputs.
- Keep `scan_date` audit-only and validate with `match_date`.
- Add checker coverage so stale fixed-date markers cannot pass again.
