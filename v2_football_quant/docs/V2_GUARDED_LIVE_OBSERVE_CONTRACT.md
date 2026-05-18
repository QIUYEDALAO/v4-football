# V2 Guarded Live Observe Contract

> Phase D.8.12.3 — separates default production path from guarded observe path

## Two Paths

| Path | Status | Meaning |
|:-----|:------:|:--------|
| **Default live** | ❌ **blocked forever** | Production code has write/push — must NOT execute |
| **Guarded live** | ✅ **ready for BOSS review** | All guard hooks available, requires explicit flags |

## Guarded Path Required Flags

The guarded path must be invoked with ALL of:
```bash
--observe-only
--no-formal-state-write
--no-push
--no-verified-write
--no-supervisor
OPENCLAW_NO_PUSH=1
```

## Guarded Path ≠ Execution

`guarded_live_path_ready=true` only means the hooks exist.
It does NOT mean execution is allowed.
D.8.14 requires separate BOSS approval.

## Current State

- `live_worker_execution_allowed: false`
- `supervisor_execution_allowed: false`
- `formal_state_write_allowed: false`
- `qq_push_allowed: false`
- `verified_write_allowed: false`
- `cron_enable_allowed: false`
- `production_verified: false`
