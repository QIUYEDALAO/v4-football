# V4 Controlled Observe Runner Hardening Closure

Phase: V4-I.1.1 / V4-I.1.2  
Date: 2026-05-19  
Status: CLOSED (hardening complete, window choices locked, no execution)

## Hardening Scope

- Fixed legacy wrong-phase fields in runner output to the V4-I.2 namespace:
  - `v4_i2_allowed_to_generate`
  - `v4_i2_allowed_to_execute`
- Preserved phase safety gates:
  - `v4_i2_allowed_to_generate=true`
  - `v4_i2_allowed_to_execute=false`
  - `v4_j_allowed_to_generate=true`
  - `v4_j_allowed_to_execute=false`
- Enforced `--date` and `--window` as required inputs in runner.
- Locked `--window` choices to:
  - `early`
  - `midday`
  - `evening`
  - `night`
- Hardened runner checker from static-only scan to:
  - execute runner preview command,
  - parse runner JSON output,
  - verify phase/safety fields in runtime output,
  - verify missing `--date` or `--window` fails as expected,
  - verify invalid `--window` is rejected with exit code `2`.
- Clarified command draft phase wording:
  - `runner_defined=true`
  - `runner_exists=true`
  - `runner_execution_authorization_required=true`
  - `observe_execution_allowed=false`

## Safety Status (Still Locked)

- observe execution: false
- qq push: false
- state write: false
- verified write: false
- production_verified: false
- phase_e_allowed: false
- command_must_not_execute: true

## Next-Phase Gate

- V4-I.2 allowed_to_generate: true
- V4-I.2 allowed_to_execute: false
- V4-J allowed_to_generate: true
- V4-J allowed_to_execute: false

No real observe execution was performed in this phase.
