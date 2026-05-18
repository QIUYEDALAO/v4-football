# V2 Single-window No-op / Shell-safe Dry-run Harness

> Phase D.8.23 — no-op harness only, no execution

## Goal

- Print the reviewed command for audit visibility.
- Never execute shell command.
- Fail-closed if any mandatory guard flag is missing.

## Mandatory Guards

- `OPENCLAW_NO_PUSH=1`
- `--single-window-only`
- `--no-supervisor`
- `--no-push`
- `--no-cron`
- `--no-verified-write`
- `--no-formal-state-write`
- `--watchdog-only-failure`
- `--manifest-required`

## Hard Constraints

- `command_executed=false`
- `execution_performed=false`
- `production_resume_executed=false`
- `production_resume_allowed_now=false`
- `cron_enable_allowed=false`
- `qq_push_allowed=false`
- `verified_write_allowed=false`
- `state_write_allowed=false`
- `pipeline_ready=false`
- `production_verified=false`

## Next Draft

- `d824_draft.allowed_to_generate=true`
- `d824_draft.allowed_to_execute=false`
- D.8.24 remains dry-run wrapper review only.

## Boundary

- D.8.23 is not production execution.
- D.8.23 is not resume.
- D.8.23 does not enter Phase E.
