# V4 Daily Scan Notification Routing Fix

## Scope

This pack fixes notification semantics for the 12:00 V4 daily scan routing.
It does not run a live scan, send QQ, change official grade, rewrite pending
records, recompute validation, mutate live bet records, or load/unload cron or
launchd jobs.

## Root Cause

The 12:00 flow has two different processes:

1. OpenClaw cron status check.
2. macOS launchd durable scan.

The OpenClaw job is currently a read-only launchd/watchdog status check, but
the old task name and completion notifier could still be interpreted as scan
completion. The durable runner also used the legacy scan task name when sending
its post-scan notification.

That made two different events share one label:

- watchdog/status check completed
- real scan completed

## New Notification Tasks

`V4_DAILY_SCAN_WATCHDOG_CHECK`

- Meaning: OpenClaw isolated session checked launchd/durable runner status.
- It must not say scan completed.
- It must not include A/B/C/SKIP scan results.
- It is a status-only watchdog message.

`V4_DAILY_SCAN_REAL_COMPLETED`

- Meaning: the local durable launchd scan process finished.
- It is the only task allowed to report real V4 scan completion.
- It must be artifact-aware before reporting PASS.

## Artifact Guard

Real scan completion requires these local artifacts:

- `data/daily_reports/scan_perf_v4_YYYYMMDD.json`
- `data/daily_reports/scout_v4_YYYYMMDD.json`
- `data/daily_reports/v4_openclaw_brief_YYYYMMDD.txt`
- `data/runtime/status/v4_official_candidate_view_YYYYMMDD.json`
- `data/runtime/status/v4_durable_daily_scan_status.json`

If any required artifact is missing, empty, date-mismatched, or the durable
status does not show a completed zero-exit scan, the notification must be
`FAIL` and use the failure/no-artifact wording.

## Message Semantics

Allowed labels:

- `V4值守检查完成`
- `V4真实扫描完成`
- `V4扫描失败/超时/无产物`

Real scan completion may include compact numeric summaries:

- actual duration
- total/scouted
- A/B/C/SKIP counts
- API call count
- artifact guard status

It must not include shadow-only rows, C/SKIP long tables, betting language, QQ
recommendation content, secrets, or API keys.

## Current Cron Note

This code pack does not mutate `~/.openclaw/cron/jobs.json`. The active 12:00
OpenClaw job may still have the historical name `V4_DAILY_SCAN_READONLY` until
a separately authorized cron-source update renames it to
`V4_DAILY_SCAN_WATCHDOG_CHECK`.

The routing guard still blocks the dangerous part now: watchdog payloads must
not call `V4_DAILY_SCAN_REAL_COMPLETED`, and the durable runner must no longer
call legacy `V4_DAILY_SCAN_READONLY` as a scan-completion task.

## Checker

`tools/check_v4_daily_scan_notification_routing.py` verifies:

- watchdog and real scan task names are distinct
- legacy `V4_DAILY_SCAN_READONLY` is not a scan-completion notify task
- durable runner calls `V4_DAILY_SCAN_REAL_COMPLETED`
- real scan notification reads required artifacts
- watchdog payload does not call real scan completion notify
- message text distinguishes watchdog, real completion, and failure/no-artifact
- no secrets are embedded in notification code

## Follow-Up

After this code pack is accepted, the safe production follow-up is a separate
cron-source-only update:

1. Rename active OpenClaw job `V4_DAILY_SCAN_READONLY` to
   `V4_DAILY_SCAN_WATCHDOG_CHECK`.
2. Keep the payload read-only.
3. Do not call `V4_DAILY_SCAN_REAL_COMPLETED` from the watchdog payload.
4. Leave launchd as the only real scan owner.
