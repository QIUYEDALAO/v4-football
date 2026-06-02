# V4 Dashboard After-Scan Brief Resolver Fix 20260602

## Scope

Fix the after-scan dashboard refresh path only:

- `tools/v3v4_dashboard_brief_resolver.py`
- `tools/generate_intel_desk_html.py`
- `tools/check_v3v4_dashboard_after_scan_refresh.py`

No candidate_view JSON is manually edited. Runtime artifacts are regenerated only by the resolver/dashboard refresh commands.

## Root Cause

The 20260602 formal brief used the compact header `🟢 B级达标推荐`, while the dashboard brief resolver split B sections only by the older fixed text `🟢 B级上半场达标推荐`.

As a result, the brief showed one B recommendation, `Rops vs OLS`, but `v3v4_dashboard_candidate_view_20260602.json` was rebuilt as A0/B0/SKIP0.

The second issue was scan total precedence: dashboard refresh used the scouted row count or A+B+C+SKIP sum instead of `scan_perf_v4_20260602.json.total_fixtures`. For 20260602 the correct total is 10, with only 1 scouted candidate.

The third issue was dashboard build source gating: `tools/generate_intel_desk_html.py` still loaded the fixed 20260525 active source allowlist. That allowlist rejected `v3v4_dashboard_candidate_view_20260602.json`, so the dashboard build marker was written from an empty fail-closed model as A0/B0/SKIP0 even after candidate_view was corrected.

## Contract

- Grade headers are parsed by grade semantics, not one exact sentence.
- Supported A/B headers include:
  - `A级强推荐`
  - `A级上半场强推荐`
  - `B级达标推荐`
  - `B级上半场达标推荐`
- A/B/C counts come from the formal brief parse.
- `scan_total` prefers `scan_perf.total_fixtures`.
- `SKIP = scan_total - A - B - C`.
- Dashboard HTML/build markers read the same date-keyed canonical candidate_view as after-scan.
- After-scan apply also rebuilds the read-only V4 control-center model so dashboard API/model and ops console markers share the same candidate source.
- For 20260602 the expected dashboard structure is `A0 / B1 / C0 / SKIP9`.

## Verification

`tools/check_v3v4_dashboard_after_scan_refresh.py` now verifies:

- B count is 1.
- `Rops vs OLS` is present in B candidates.
- `scan_total` is 10.
- SKIP is 9.
- dashboard model/API is sourced from `v3v4_dashboard_candidate_view_20260602.json`.
- dashboard build marker is sourced from `v3v4_dashboard_candidate_view_20260602.json`.
- Legacy fallback does not overwrite an effective parsed scan result with empty candidates.
