# V4 Controlled Observe Runner Contract

Phase: V4-I.1.1
Date: 2026-05-19
Status: HARDENED (runner defined, no-exec harness only)

## Runner Identity

- File: `engine/v4_observe_runner.py`
- Type: controlled observe harness (no-exec)
- Default: execution_allowed=false
- Default: command_must_not_execute=true

## Required CLI Flags

| Flag | Required | Purpose |
|------|----------|---------|
| `--observe-only` | yes | Observe mode only |
| `--dry-run` | yes | No side effects |
| `--single-window-only` | yes | One window only |
| `--no-push` | yes | No QQ push |
| `--no-state-write` | yes | No state file writes |
| `--no-verified-write` | yes | No verified writes |
| `--no-cron` | yes | No cron enable |
| `--no-api` | yes | No API calls |
| `--no-key-read` | yes | No key access |
| `--no-supervisor` | yes | No supervisor mode |
| `--watchdog-only-failure` | yes | Watchdog reports only |
| `--no-ai-kill-retry` | yes | No AI kill/retry |
| `--preserve-logs` | yes | Preserve all logs |
| `--manifest-required` | yes | Manifest gate required |
| `--review-only` | yes | Review/approval mode only |
| `--date` | yes (required) | Run date |
| `--window` | yes (required) | Window (early/midday/evening/night) |

## Prohibited Actions

- ❌ Call API
- ❌ Read keys
- ❌ Push QQ
- ❌ Write state
- ❌ Write verified
- ❌ Write PRODUCTION_VERIFIED
- ❌ Create route marker
- ❌ Create sent marker
- ❌ Create lock
- ❌ Kill/retry processes
- ❌ Auto-restore production

## Runner Output

- Only stdout JSON / structured preview
- Local runtime markers OK (not committed)
- No formal state/verified writes

## Guard Status

| Guard | Value |
|-------|-------|
| production_verified | false |
| phase_e_allowed | false |
| v4_i2_allowed_to_generate | true |
| v4_i2_allowed_to_execute | false |
| v4_j_allowed_to_generate | true |
| v4_j_allowed_to_execute | false |
| observe_executed | false |
