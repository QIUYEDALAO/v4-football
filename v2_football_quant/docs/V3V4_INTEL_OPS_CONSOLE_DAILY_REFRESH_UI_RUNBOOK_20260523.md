# V3/V4 Intel Ops Console Daily Refresh UI Runbook - 2026-05-23

## Purpose

Daily refresh must rebuild the same V3/V4-only Intel Ops Console UI that is served at `intel_ops_console.html`.

## Entrypoint

`tools/run_v3v4_intel_ops_console_daily_refresh.py`

## Modes

- `--mode dry-run`: render preview metadata and source hash only.
- `--mode apply`: rebuild `data/runtime/dashboard/intel_ops_console.html`, `index.html`, and `intel_desk.html` through `tools/generate_intel_desk_html.py`.

## Source Contract

- Read V3 readiness status if present; otherwise render V3 readiness as reserved.
- Read V4 active candidate model only.
- Do not read retired module markers.
- Do not read archive or quarantine as current.
- Preserve V4 A/B/C/SKIP counts and time bins.

## Safety Contract

- `capture_ran=false`.
- `QQ_push=false`.
- `cloud_publish=false`.
- `cron_enabled=false`.
- `strategy_changed=false`.
- `v4_candidate_numbers_changed=false`.
- Runner exposes lock and last_good contracts, but this phase does not create cron.
