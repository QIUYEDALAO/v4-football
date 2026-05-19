# V4 Controlled Observe Runner — Phase Closure

Phase: V4-I.1 / V4-I.1.1 / V4-I.1.2 / V4-I.2
Date: 2026-05-19
Status: CLOSED (runner hardened + I.2 review package generated; V4-J execute still blocked)

## Scope

This phase defined the V4 controlled observe no-exec runner:
- Runner contract doc
- engine/v4_observe_runner.py (no-exec harness)
- Runner checker
- Updated V4-I docs for runner existence

## Operational Status

| Item | Status |
|------|--------|
| Runner defined | ✅ (engine/v4_observe_runner.py) |
| All required flags | ✅ 17/17 (`--date` and `--window` are required) |
| Window choices | ✅ `early/midday/evening/night` only |
| Invalid window negative test | ✅ PASS (exit code 2) |
| Runner no-exec | ✅ (observe_execution_allowed=false) |
| No API/key/QQ/state/verified | ✅ |
| Runner checker | ✅ CREATED + preview execution JSON parse + invalid-window negative test |
| Four-window preview review | ✅ early/midday/evening/night all REVIEW_ONLY_READY |

## Safety Verification

| Check | Value |
|-------|-------|
| Observe executed | false |
| QQ pushed | false |
| API called | false |
| Key read | false |
| State written | false |
| Verified written | false |
| PRODUCTION_VERIFIED | false |
| Route marker written | false |
| Sent marker written | false |
| Lock created | false |
| AI kill/retry | false |

## Phase Guards

| Guard | Value |
|-------|-------|
| production_verified | false |
| phase_e_allowed | false |
| V4-I.2 allowed_to_generate | true |
| V4-I.2 allowed_to_execute | false |
| V4-J allowed_to_generate | true |
| V4-J allowed_to_execute | false |

## V4-I.2 Review Boundary

- V4-I.2 generated execution review artifacts only.
- No real observe execution was performed.
- `command_must_not_execute=true` remains enforced.
- V4-J remains generate-only for now (`allowed_to_execute=false`).

## Modified Files (this phase)

- `engine/v4_observe_runner.py` (new, no-exec harness)
- `tools/check_v4_controlled_observe_runner.py` (new)
- `docs/V4_CONTROLLED_OBSERVE_RUNNER_CONTRACT.md` (new)
- `docs/V4_CONTROLLED_OBSERVE_RUNNER_CLOSURE.md` (this file)
- `docs/V4_CONTROLLED_OBSERVE_COMMAND_DRAFT.md` (updated: runner execution authorization wording)
- `docs/V4_CONTROLLED_OBSERVE_APPROVAL_CLOSURE.md` (updated: V4-I.2 generate-only + V4-J still blocked)
