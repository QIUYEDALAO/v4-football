# V4 Scout Date Schema - 20260523

Phase: V4-SCOUT-DATE-INTEGRITY-REPAIR-AND-VALIDATION-REBASE-20260523

## Formal Fields

- `match_date`: actual kickoff local date. This is the only date field allowed for validator, attribution, review, and dashboard validation filtering.
- `date`: backward-compatible alias of `match_date`. It must equal `match_date` and must never be scan date.
- `scan_date`: scanner run date. This is audit-only and must not drive validation.
- `kickoff`: original kickoff timestamp from the source fixture.
- `kickoff_local`: parsed local kickoff timestamp after timezone normalization.
- `source_window`: scan source window such as early, midday, evening, night, or auto when available.
- `scout_file_date`: `YYYYMMDD` from the `scout_v4_YYYYMMDD.json` filename. This identifies the file generation date, not the match date.
- `timezone_policy`: prefer timezone embedded in `kickoff`; if kickoff is UTC, convert to UTC+8; if kickoff is local with no offset, treat as configured timezone only when explicitly allowed; unknown timezone is WARN/BLOCKER and must not be silently repaired.

## Validation Rule

`--date YYYYMMDD` must select records where `match_date == YYYY-MM-DD`. It must not select records by `scan_date` or `scout_file_date`.

## Deprecated C Rule

C is deprecated for active dashboard and active validation. A+B is A plus B only, never C.

## Safety

- brief_used_for_hit_rate=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false
- V2 restored=false
- V33 restored=false
