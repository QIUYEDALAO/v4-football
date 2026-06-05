# OpenClaw Repo Hygiene And Runbook Learning Pack

## Scope

This document freezes the repository hygiene rules for OpenClaw execution.
It is a process and checklist artifact only. It does not change V3 or V4
business logic, runtime behavior, cron, launchd, QQ, pending, validation, or
rating rules.

## Git State Basics

`staged` means a file is already selected for the next commit. Only staged
files are committed.

`working tree dirty` means tracked files have local edits, deletions, or
generated changes that are not staged. These can be legitimate user state,
checker side effects, runtime status, or existing production changes. Dirty
does not automatically mean safe to commit.

`untracked` means Git sees a file that is not in the index. It can be a new
document, a runtime output, a local cache, parent workspace metadata, a copied
reference file, or a private artifact. Untracked files must be classified
before staging.

## Why Tracked Runtime Is Dangerous

Runtime, cache, log, status, lock, and generated timestamp files change because
tools run. If they are tracked, every checker or dry-run can create new dirty
diffs. That makes the worktree noisy and can hide real code changes.

Tracked runtime is also dangerous because it can accidentally commit local
machine state, stale status, transient scan output, or private operational
metadata. Runtime files should normally be ignored, and already tracked runtime
files require explicit BOSS approval before an untrack-only cleanup with
`git rm --cached`.

## Generated Timestamp Dirty

Many V3 and V4 builders write summaries with `generated_at`, timestamps,
status counters, or checker result JSON. These files may become dirty even when
the semantic data did not change.

Generated timestamp dirty must not be staged just to make `git status` clean.
Only stage generated files when the current BOSS task explicitly requires the
updated artifact and the diff has been reviewed as part of that task.

## What Can Be Cleaned Or Preserved

Safe automatic action is narrow:

- Add or update process documentation requested by BOSS.
- Add or update checker code requested by BOSS.
- Stage only the exact files required by the active task.
- Run checkers and leave ignored runtime output untracked.

Actions requiring explicit BOSS approval:

- Untracking already tracked runtime with `git rm --cached`.
- Removing stale generated artifacts from Git.
- Changing V4 production runner, cron, launchd, QQ, pending, or validation
  behavior.
- Touching parent workspace metadata.

Must preserve unless specifically authorized:

- Parent workspace memory and heartbeat files.
- Existing V4 dirty code or docs outside a V4-scoped task.
- Runtime/cache/log/status files created by checkers.
- Manual source packs and generated data locked by previous phases.

## Why `git add -A` Is Forbidden

`git add -A` stages every tracked deletion, every modified file, and every
untracked file under the current repository. In this workspace that can mix:

- Parent metadata changes.
- V3 generated timestamp dirty.
- V4 existing dirty files.
- Runtime/cache/log/status outputs.
- Local reference files.
- Private environment or operational artifacts.

OpenClaw tasks must use exact path staging, for example:

```bash
git add -- docs/OPENCLAW_REPO_HYGIENE_AND_RUNBOOK_LEARNING_PACK_20260605.md
```

Before commit, always verify:

```bash
git diff --cached --name-only
```

## Why Reset, Clean, And Delete Are Forbidden

`git reset --hard` can destroy user or production edits that Codex did not
make.

`git clean -fd` can remove untracked local source packs, manually supplied
documents, reports, or workspace metadata.

Deleting dirty files can remove runtime evidence needed for diagnosis, or
erase parent workspace state outside the current project scope.

These commands are only allowed when BOSS explicitly requests them for a
specific file set and the blast radius is clear.

## Dirty Classification Policy

| Class | Name | Examples | Default action |
| --- | --- | --- | --- |
| A | Checker side-effect | Generated summaries, status JSON, timestamp-only checker output | WARN_ONLY. Do not stage unless required by active task. |
| B | Parent metadata / memory | `../HEARTBEAT.md`, `../MEMORY.md`, parent `memory/` files | WARN_ONLY. Do not clean, reset, delete, or stage from project tasks. |
| C | V4 existing dirty | Existing V4 runner/checker/docs changes outside current scope | WARN_ONLY unless the task is explicitly V4-scoped. |
| D | Runtime/cache/log/secrets | `data/runtime/`, logs, cache, tmp, env/key/token paths | BLOCK if staged. Runtime stays untracked; secrets never staged. |
| E | Unknown requiring BOSS | Any file whose source, owner, or safety is unclear | BLOCK and ask BOSS decision. |

## V3 And V4 Exact Staging Rules

For V3 tasks:

- Stage only the V3 builder/checker/doc/data artifacts named by the active
  BOSS task.
- Do not stage V4 files, parent metadata, runtime output, or unrelated
  generated summaries.
- If a checker rewrites unrelated timestamp summaries, classify them as
  Class A WARN_ONLY.

For V4 tasks:

- Stage only the V4 UI/checker/runner/doc files named by the active BOSS task.
- Do not stage V3 runtime output or parent metadata.
- Do not change V4 official rating logic unless BOSS explicitly authorizes it.
- Do not stage QQ, pending, validation, launchd, cron, or live-bet mutations
  unless they are the named task target.

## Pre-Execution Checklist

Run before changing files:

```bash
pwd
git rev-parse --show-toplevel
git rev-parse --short HEAD
git rev-parse --short origin/main
git status --short
git diff --cached --name-only
```

Checklist:

- Repo root is known.
- HEAD and origin are understood.
- Staged files are empty, or already approved by BOSS.
- Dirty files are classified as A, B, C, D, or E.
- No secrets/env/key/token paths are staged.
- The active task scope is clear.
- Exact files to stage are known before editing.

## Post-Execution Checklist

Run after edits and before commit:

```bash
git status --short
git diff --cached --name-only
python3 tools/check_working_tree_dirty_hygiene.py
```

Checklist:

- Staged files contain only active-task files.
- Runtime/cache/log/status output is not staged.
- Secrets/env/key/token are not staged and are not printed.
- V4 files are not staged during non-V4 tasks.
- Final 26, validation, pending, QQ, cron, launchd, and live-bet files are not
  staged unless explicitly in scope.
- Checker side effects are classified but not cleaned.
- If any Class E unknown appears, stop and request BOSS decision.

## Commit Checklist

Only commit after:

- Required checker commands pass.
- `git diff --cached --name-only` matches the allowed file list.
- No runtime or secrets are staged.
- Dirty WARN_ONLY files are left untouched.

Use a scoped commit message that matches the active pack. Push only after the
commit succeeds and no forbidden files were included.
