# V2 Controlled Command Review / Dry-run Gate

> Phase D.8.22 — review-only gate, not execution

## Purpose

- Review the D.8.21 proposed command without executing it.
- Ensure all mandatory no-execution/no-production flags are present.
- Keep all production permissions blocked.

## Required Flags (must all exist)

- `OPENCLAW_NO_PUSH=1`
- `--single-window-only`
- `--no-supervisor`
- `--no-push`
- `--no-cron`
- `--no-verified-write`
- `--no-formal-state-write`
- `--watchdog-only-failure`
- `--manifest-required`

## Fixed Safety Output

- `execution_performed=false`
- `production_resume_executed=false`
- `production_resume_allowed_now=false`
- `cron_enable_allowed=false`
- `qq_push_allowed=false`
- `verified_write_allowed=false`
- `state_write_allowed=false`
- `pipeline_ready=false`
- `production_verified=false`

## Next Draft Gate

- `d823_draft.allowed_to_generate=true`
- `d823_draft.allowed_to_execute=false`
- D.8.23 is still no-op/shell-safe harness review.

## Boundary

- D.8.22 is not execution.
- D.8.22 is not production resume.
- D.8.22 does not auto-advance to D.8.23 execution.
- Phase E remains forbidden.
