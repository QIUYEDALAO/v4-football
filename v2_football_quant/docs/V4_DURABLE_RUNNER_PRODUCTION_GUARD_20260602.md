# V4 Durable Runner Production Guard

## Scope

This change adds a template-only local durable runner for the 12:00 V4 daily
scan. It does not load launchd, write `~/Library/LaunchAgents`, modify OpenClaw
cron, run a real scan, or change V4 grading rules.

## Current State

The checker supports both lifecycle states:

- `--mode template`: deployment has not happened yet; launchd must not be
  loaded, and OpenClaw may still point at the old direct scan payload.
- `--mode deployed`: deployment has happened; launchd must be loaded, and
  OpenClaw 12:00 must be a read-only status check.
- `--mode auto`: infer the mode from local launchd/OpenClaw state.

Current deployed expectation:

- launchd loaded = true
- isolated session dependency = false
- OpenClaw 12:00 mode = read-only status check
- next action = `WAIT_NEXT_SCHEDULED_SCAN`

## Durable Runner Contract

`scripts/v4_daily_scan_runner.sh` is the stable local entrypoint. It invokes
`tools/run_v4_durable_daily_scan.py`, which provides:

- single-flight lock
- heartbeat status
- atomic status writes
- start, end, exit-code, and log-path status
- local timeout management
- separate scan and QQ notification failures
- no automatic rerun
- status-only `NEED_MANUAL_CATCHUP` detection
- BOSS-authorized manual oneshot gate

The future deployed OpenClaw job must only read durable status. It must not
carry the scan process lifetime.

## launchd Template

`deploy/launchd/com.openclaw.v4.daily_scan.plist.template` schedules the local
shell runner at 12:00 Asia/Shanghai machine time. This repository task submits
the template only. Deployment requires a separate BOSS approval.

## Verification Boundary

The checker is static and read-only. It does not call `launchctl`, mutate cron,
or execute `engine/v4_scan_and_brief.py`.
