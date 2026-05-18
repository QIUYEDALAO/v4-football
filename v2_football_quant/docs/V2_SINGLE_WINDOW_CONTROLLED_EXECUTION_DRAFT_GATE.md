# V2 Single-window Controlled Execution Draft Gate

> Phase D.8.21 — draft gate only, not execution

## Core Position

- D.8.21 is a **single-window controlled execution draft gate**.
- D.8.21 is **not execution** and **not production resume**.
- This phase only generates a D.8.22 reviewable command draft.
- `accepted_risks_do_not_grant_execution=true`.

## Fixed Safety State

- `current_level=CODE_READY`
- `PIPELINE_READY=false`
- `PRODUCTION_VERIFIED=false`
- `production_resume_allowed_now=false`
- `cron_enable_allowed=false`
- `qq_push_allowed=false`
- `verified_write_allowed=false`
- `state_write_allowed=false`

## D.8.22 Draft Policy

- `d822_allowed_to_generate=true`
- `d822_allowed_to_execute=false`
- D.8.22 still requires a separate BOSS instruction.
- D.8.21 must not auto-advance to D.8.22.

## Single-window Scope

- `single_window_only=true`
- `window=midday`
- `full_day_resume_allowed=false`
- `multi_window_resume_allowed=false`
- `cron_resume_allowed=false`
- `qq_push_allowed=false`
- `verified_write_allowed=false`
- `formal_state_write_allowed=false`
- `supervisor_allowed=false`

## Evidence Constraints

Proven:
- `no_state_case_proven=true`
- `synthetic_state_file_read_proven=true`
- `synthetic_state_present_no_write_proven=true`

Not proven:
- `real_state_present_case_proven=false`
- `synthetic_active_window_mutation_proven=false`
- production QQ/cron/verified/formal-state live paths remain unproven and disabled

## Required Guards

- no-supervisor
- no-push
- `OPENCLAW_NO_PUSH=1`
- no-cron
- no-verified-write
- no-formal-state-write
- preflight-required
- watchdog-only-failure
- rollback-required
- manifest-gate-required
- stop-on-any-marker-mismatch
- no-ai-kill-retry
- preserve-logs

## Rollback / Stop Rules

- `no_ai_kill_retry=true`
- `report_watchdog_only=true`
- `preserve_logs=true`
- `stop_on_any_push_state_verified_cron=true`
- `stop_on_any_marker_mismatch=true`
- `disable_cron_if_modified=true`

## Prohibited Escalation

- Do not mark as `PIPELINE_READY`.
- Do not write `PRODUCTION_VERIFIED`.
- Do not enter Phase E automatically.
