# V4 Scout Date Integrity Repair Issue List - 20260523

Phase: V4-SCOUT-DATE-INTEGRITY-REPAIR-AND-VALIDATION-REBASE-20260523

## Status

- issue_list_status: PASS
- current_scope: V3/V4 only
- V2 restored: false
- V33 restored: false
- capture_ran: false
- QQ_push: false
- cloud_publish: false

## Issues

1. `scan_date` and `match_date` are mixed in historical V4 scout files.
2. Night scans using `--lookahead-hours 24` can include next-day fixtures in the scan-day scout file.
3. The scout `date` field was written from scan date instead of actual kickoff date, contaminating downstream validators.
4. Dashboard yesterday validation is not trustworthy until the scout date field is repaired and validation is rebased.
5. Last-7-day and cumulative validation may be polluted by historical rows whose `date` does not match kickoff date.
6. Formal daily brief may only drive candidate display; it must not be used to recompute hit rates.
7. Validation, attribution, review, and dashboard validation must filter by actual kickoff `match_date`.
8. Historical `scout_v4_*.json` files require repair with backup before any overwrite.
9. A dedicated checker must prevent `date` from being contaminated by `scan_date` again.
10. Before repair, dashboard validation must be treated as untrusted/stale, not as production truth.

## Blocker Policy

- BLOCKER if any active path continues defining `date` as scan date.
- BLOCKER if validation filters by `scan_date` or scout file date instead of `match_date`.
- BLOCKER if C is reintroduced as active candidate or active validation.
- BLOCKER if capture, QQ push, cloud publish, cron creation, V2, or V33 is restored.
