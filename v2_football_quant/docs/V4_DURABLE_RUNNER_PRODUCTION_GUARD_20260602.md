# V4 Durable Runner Production Guard

## Scope

This change adds a template-only local durable runner for the 12:00 V4 daily
scan. It does not load launchd, write `~/Library/LaunchAgents`, modify OpenClaw
cron, run a real scan, or change V4 grading rules.

## Current State

- runner installed/template only
- launchd loaded = false
- isolated session dependency = true
- OpenClaw 12:00 job unchanged
- next action = `DEPLOY_APPROVAL_REQUIRED`

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
