# V4 Path Canonicalization

Phase: V4-D.1
Date: 2026-05-19
Status: FINAL

## Repository Structure

```
repo_root = /Users/liudehua/.openclaw/workspace  (git root)
module_root = repo_root / v2_football_quant      (V4 module root)
```

## Canonical Paths (V4 Module)

| Artifact Type | Canonical Path |
|---------------|----------------|
| V4 docs | `v2_football_quant/docs/` |
| V4 tools/checkers | `v2_football_quant/tools/` |
| V4 engine | `v2_football_quant/engine/` |
| V4 templates | `v2_football_quant/templates/` |
| V4 config | `v2_football_quant/config/` |
| V4 data output | `v2_football_quant/data/` |
| V4 marker status | `v2_football_quant/data/runtime/status/` |

## Root-Level Exceptions (System-Level Only)

These files/artifacts are system-level, not V4-module-level, and remain at repo root:

| Path | Purpose |
|------|---------|
| `docs/SYSTEM_LEGACY_INVENTORY.md` | System-wide legacy inventory |
| `docs/V4_FORMAL_FILE_WHITELIST.md` | V4 formal file whitelist (cross-module reference) |
| `docs/archive/system_legacy/` | System legacy archive directory |
| `tools/check_system_legacy_purge.py` | System-wide legacy purge checker |

## Historical Path Deviation

The V4-D phase originally created new docs and checkers at the repo root level:
- `docs/V4_WATCHDOG_STATE_LOCK.md` → MOVED to `v2_football_quant/docs/`
- `docs/V4_STATE_LIFECYCLE_CONTRACT.md` → MOVED to `v2_football_quant/docs/`
- `docs/V4_WATCHDOG_STATE_LOCK_CLOSURE.md` → MOVED to `v2_football_quant/docs/`
- `tools/check_v4_watchdog_contract.py` → MOVED to `v2_football_quant/tools/`
- `tools/check_v4_lock_timeout_contract.py` → MOVED to `v2_football_quant/tools/`

These have been canonically migrated. No further V4 artifacts should be placed at repo root.

## Execution Contract (V4-E+)

For all V4 checker execution from V4-E onward:

1. **Default cwd**: `repo_root/v2_football_quant`
2. **Checker invocation**: `python3 tools/check_xxx.py`
3. **System-level checker** (if needed from module scope):
   - `python3 ../tools/check_system_legacy_purge.py` (from v2_football_quant cwd)
   - `python3 tools/check_system_legacy_purge.py` (from repo root cwd)
4. **Not allowed**: hardcoding `/Users/liudehua/...` absolute paths

## Checker Entrypoints (v2_football_quant/tools/)

| Checker | Status |
|---------|--------|
| `check_v4_boundary_contract.py` | CANONICAL |
| `check_v4_active_contamination.py` | CANONICAL |
| `check_v4_output_schema.py` | CANONICAL |
| `check_v4_renderer_guard.py` | CANONICAL |
| `check_v4_qq_guard.py` | CANONICAL |
| `check_v4_no_push_enforcement.py` | CANONICAL |
| `check_v4_watchdog_contract.py` | CANONICAL (migrated V4-D) |
| `check_v4_lock_timeout_contract.py` | CANONICAL (migrated V4-D) |
| `check_v4_path_canonicalization.py` | CANONICAL (this phase) |
