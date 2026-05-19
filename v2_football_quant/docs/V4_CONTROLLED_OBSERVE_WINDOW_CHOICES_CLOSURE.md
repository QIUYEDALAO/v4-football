# V4 Controlled Observe Runner Window Choices Closure

Phase: V4-I.1.2  
Date: 2026-05-19  
Status: CLOSED (window choices hardening complete, observe still blocked)

## Window Choices Lock

`--window` choices are strictly limited to:
- `early`
- `midday`
- `evening`
- `night`

Any illegal value (e.g. `invalid`) must be rejected by argparse with exit code `2`.

## Verification Summary

- Legal preview (`--window midday`) returns `runner_status=REVIEW_ONLY_READY`.
- Missing `--date` negative test: `exit code 2`.
- Missing `--window` negative test: `exit code 2`.
- Invalid `--window` negative test: `exit code 2`.

## Safety Locks (Unchanged)

- `observe_execution_allowed=false`
- `command_must_not_execute=true`
- `v4_i2_allowed_to_generate=true`
- `v4_i2_allowed_to_execute=false`
- `v4_j_allowed_to_generate=true`
- `v4_j_allowed_to_execute=false`
- `production_verified=false`
- `phase_e_allowed=false`

No real observe execution was performed in this phase.
