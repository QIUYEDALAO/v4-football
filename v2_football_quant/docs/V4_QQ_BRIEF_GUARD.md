# V4 QQ Brief Guard

## Scope

- System: `V4` QQ brief output only.
- This guard controls formatting and route readiness, not production execution.
- Phase V4-C remains non-production: `qq_push_allowed=false`, `production_verified=false`, `phase_e_allowed=false`.

## QQ Brief Content Requirements

- Must be iPhone-readable.
- Must avoid long tables.
- Formal grade vocabulary must be only: `A/B/C/SKIP`.
- `SKIP is not recommendation`.
- `C is not main recommendation`.
- Must not output `V33/V38` as active wording.
- Must not output non-standard grade words in formal brief:
  - `WATCH`, `CANDIDATE`, `S`, `S+`, `D`, `BET`, `STRONG`, `主推`.
- Must show:
  - `guard_status`
  - `schema_guard_status`
  - `no_push` status

## QQ Brief Structure (Recommended)

- Title
- Review date/window
- A/B counts
- C count
- SKIP count
- Key risk notes
- Guard status
- No-push status

## Hard Prohibitions

- No guard PASS -> no route.
- No route marker -> no sent marker.
- No sent marker -> no delivery-success claim.
- Do not phrase `SKIP` as recommendation.
- Do not phrase `C` as main recommendation.

## Route Preconditions (V4-C)

- `schema_guard_status=PASS`
- `renderer_guard_status=PASS`
- `qq_guard_status=PASS`
- `OPENCLAW_NO_PUSH=1` (or equivalent explicit no-push policy)

## Phase Gate

- `qq_push_allowed=false`
- `production_verified=false`
- `phase_e_allowed=false`
- `v4_d_allowed_to_generate=true`
- `v4_d_allowed_to_execute=false`
