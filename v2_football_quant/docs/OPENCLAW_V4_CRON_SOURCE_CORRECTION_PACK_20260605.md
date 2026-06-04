# OpenClaw V4 Cron Source Correction Pack

Date: 2026-06-05

## Scope

This correction pack restores the active OpenClaw cron source file for the V4
durable runner deployment check. It does not rewrite git history, restore backup
payloads, start or stop jobs, run a V4 scan, push QQ, or expose secrets.

## Root Cause

`tools/check_v4_durable_runner.py --mode deployed` reads the active cron source
from:

- `~/.openclaw/cron/jobs.json`

That file was missing, while the migrated cron source existed at:

- `~/.openclaw/cron/jobs.json.migrated`

Because the active source file was absent, the checker could not find the
single read-only `V4_DAILY_SCAN_READONLY` OpenClaw 12:00 job and reported:

- `openclaw_1200_job_singleton`
- `openclaw_1200_job_agentturn_status_shell`
- `openclaw_1200_read_only_status_check`

## Correction

`~/.openclaw/cron/jobs.json` was generated from
`~/.openclaw/cron/jobs.json.migrated`.

The active V4 12:00 job is now:

- exactly one `V4_DAILY_SCAN_READONLY`
- `agentTurn`
- read-only durable runner status check
- contains no direct `engine/v4_scan_and_brief.py` scan invocation

`~/.openclaw/cron/jobs.json.bak` remains a historical backup and is not treated
as the active cron source.

## Git History Policy

No reset, rebase, cherry-pick, amend, or force push was performed. Existing
mixed-history commits remain intact. This document records the correction
instead of rewriting published history.

## Validation

Required checks:

- `python3 tools/check_v4_durable_runner.py --mode deployed`
- `python3 tools/check_working_tree_dirty_hygiene.py`

Expected result:

- durable runner deployed mode PASS
- active cron source read-only
- no direct scan payload
- no staged runtime, V4 code, or secrets

## Safety

- No secrets are printed.
- No live API call is made.
- No launchd task is loaded, unloaded, started, or stopped.
- No V4 scan is started.
- No QQ push is performed.
