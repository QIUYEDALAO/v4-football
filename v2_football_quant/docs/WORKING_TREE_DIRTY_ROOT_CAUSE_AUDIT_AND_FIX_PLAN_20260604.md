# Working Tree Dirty Root Cause Audit And Fix Plan

## Repo Boundary

- Repo root: `/Users/liudehua/.openclaw/workspace`
- Active project path: `/Users/liudehua/.openclaw/workspace/v2_football_quant`

The dirty tree is caused by a shared workspace root that also tracks parent
workspace metadata and historical runtime files under `v2_football_quant`.

## Dirty Categories

| Category | Count | Action |
| --- | ---: | --- |
| `G. PARENT_WORKSPACE_METADATA` | 32 | WARN_ONLY, do not touch in project tasks |
| `C. TRACKED_RUNTIME_SHOULD_UNTRACK` | 9 | report only; requires BOSS approval before `git rm --cached` |
| `F. V4_DIRTY_EXISTING` | 11 | WARN_ONLY, do not touch outside V4-scoped tasks |
| `H. DOCS_OR_CODE_LEGIT_CHANGE` | 3 | out of scope, do not stage |

No current dirty file is classified as a tracked secret/env/key/token blocker.

## Tracked Runtime Candidates

The current dirty runtime candidates are tracked historical status files under:

- `v2_football_quant/data/runtime/status/`

They should not be removed from the index without explicit BOSS approval because
untracking already committed runtime files changes repository history behavior.

## Gitignore Gaps Fixed

The root and project `.gitignore` files now include missing local-only patterns:

- `*.env`
- `runtime/`
- `logs/`
- `log/`
- `cache/`
- `tmp/`
- `*.lock`
- `*.pid`
- local `.config/` and `.learnings/`
- selected OpenClaw wiki cache/log metadata paths

Existing tracked files remain tracked until BOSS explicitly authorizes an
untrack-only cleanup.

## Guard

`tools/check_working_tree_dirty_hygiene.py` checks staged files only and blocks:

- runtime/cache/log/status/tmp files staged by mistake
- secrets/env/key/token paths or secret-like literals
- V4 files staged during non-V4 hygiene work

The checker writes a status JSON under `data/runtime/status/`; that output is
ignored and must not be committed.

## Prohibited Actions

This audit did not run and must not run without explicit BOSS scope:

- `git clean -fd`
- `git reset --hard`
- deleting dirty files
- cleaning parent workspace metadata
- cleaning V4 runtime
- `git rm --cached` for tracked runtime
- `git add .`
- `git add -A`
