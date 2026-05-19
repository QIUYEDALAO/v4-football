# V4 QQ Route/Sent Marker Contract

## Scope

- Defines marker semantics for V4 QQ review pipeline.
- Phase V4-C is no-push only.

## Route Marker Contract

Route marker fields are required:

- `route_marker_required=true`
- `guard_status`
- `schema_guard_status`
- `renderer_guard_status`
- `qq_guard_status`
- `route_allowed`
- `route_marker_written`
- `sent_marker_written`
- `no_push`
- `qq_sent`
- `production_verified=false`
- `phase_e_allowed=false`

Rules:

- `route_allowed` may be true only after all guard checks pass.
- `route_allowed=false` when `OPENCLAW_NO_PUSH=1`.
- `route` does **not** mean `sent`.

## Sent Marker Contract

Sent marker fields are required:

- `sent_marker_required=true`
- `guard_status`
- `schema_guard_status`
- `renderer_guard_status`
- `qq_guard_status`
- `route_allowed`
- `route_marker_written`
- `sent_marker_written`
- `no_push`
- `qq_sent`
- `production_verified=false`
- `phase_e_allowed=false`

Rules:

- Sent marker may be marked success only after real outbound delivery success.
- In this phase: `sent_marker_written=false` (delivery not executed).
- In no-push mode: `sent_marker_written=false`, `qq_sent=false`.
- Route marker must never be used as proof of sent success.

## V4-C Gate

- `qq_push_allowed=false`
- `production_verified=false`
- `phase_e_allowed=false`
- `v4_d_allowed_to_generate=true`
- `v4_d_allowed_to_execute=false`
