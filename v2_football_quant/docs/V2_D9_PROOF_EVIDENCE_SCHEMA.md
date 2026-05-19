# V2 D9 Proof Evidence Schema

> Phase D.9.2 — evidence schema definition only, no execution

## Purpose

- Define a unified evidence record for future production-proof runs.
- Keep D.9.2 strictly at schema level; no proof execution is allowed.

## Required Schema Fields

- `proof_id`
- `proof_target`
- `run_date`
- `window`
- `pre_state_hash`
- `post_state_hash`
- `pre_state_mtime`
- `post_state_mtime`
- `pre_state_size`
- `post_state_size`
- `command_template`
- `command_executed=false`
- `supervisor_executed=false`
- `live_worker_executed=false`
- `cron_modified=false`
- `qq_sent=false`
- `verified_written=false`
- `formal_state_written=false`
- `api_called=false`
- `key_read=false`
- `watchdog_status`
- `marker_status`
- `rollback_status`
- `evidence_status`
- `proof_result=UNPROVEN|PASS|FAIL|BLOCKER`
- `proof_current_status=UNPROVEN`

## Output Contract

- `d9_evidence_schema_status=WARN/READY_FOR_BOSS_REVIEW`
- `schema_complete=true`
- `schema_execution_performed=false`
- `proof_result_default=UNPROVEN`
- `d9_3_allowed_to_generate=true`
- `d9_3_allowed_to_execute=false`
- `pipeline_ready=false`
- `production_verified=false`

## Boundary

- D.9.2 does not execute proof commands.
- D.9.2 does not authorize production execution.
