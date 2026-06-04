# OpenClaw Memory Bridge Template

**Version**: 1.0
**Status**: template

---

## 1. Purpose

The memory bridge ensures that when work is split across multiple child sessions, **key state survives between sessions** without relying on main session context.

## 2. When to Write Memory

| Event | What to Write |
|-------|--------------|
| Before spawning child session | Task brief with key context, file paths, expected outputs |
| After child session completes | Status, counts, artifact paths, checker summary |
| Before commit | What was changed and why |
| After commit | Commit hash, push status, next action |

## 3. Template: Task Brief Memory (before child)

**File**: `memory/{date}_{task_name}_task_brief.md`

```markdown
# Task Brief — {task_name}

**Status**: IN_FLIGHT
**Parent session**: {session_id or description}
**Source commit**: {commit_hash}

## Context
- Known facts relevant to this task
- File paths to read
- File paths to write
- Parameters / limits

## Expected Outputs
- `data/runtime/{task_name}/{date}/summary.json`
- `data/runtime/{task_name}/{date}/summary.md`
- `data/runtime/status/{checker_name}_{date}.json`

## Safety
- STOP_CRON
- STOP_QQ_PUSH
- STOP_LIVE_SCAN
- STOP_PROD_CONFIG
- STOP_SECRETS
- STOP_DELETE
- STOP_BETTING
- STOP_V4_GRADE
- STOP_VALIDATION
```

## 4. Template: Result Memory (after child)

**File**: `memory/{date}_{task_name}_result.md`

```markdown
# Task Result — {task_name}

**Status**: {DONE / FAILED / BLOCKED}
**Child session**: {session_id}
**Execution time**: {duration}

## Counts
- records: {n}
- fixtures: {n}
- ...

## Checker Summary
| Checker | Result |
|---------|--------|
| checker_a | PASS |
| checker_b | PASS |

## Warnings
- {if any}

## Blockers
- {if any, otherwise "none"}

## Artifacts
- `{path}`

## Next Action
- {next step}
```

## 5. Forbidden in Memory

Never write:
- ❌ secrets / env / keys / tokens
- ❌ raw API responses
- ❌ raw HTML / DOM
- ❌ OCR full text
- ❌ full checker JSON
- ❌ large runtime / log content

## 6. Token Hygiene Check

All memory entries must include `token_hygiene` self-check:

```json
{
  "token_hygiene": {
    "raw_json_pasted": false,
    "raw_html_pasted": false,
    "browser_snapshot_pasted": false,
    "api_response_pasted": false,
    "ocr_fulltext_pasted": false,
    "checker_full_json_pasted": false,
    "runtime_log_fulltext_pasted": false,
    "output_lines_under_120": true,
    "artifact_paths_reported": true,
    "secrets_printed": false
  }
}
```

After writing memory, verify:
- [ ] `token_hygiene` fields present
- [ ] No secret/API key present
- [ ] No raw JSON pasted
- [ ] No raw HTML pasted
- [ ] Summary only (not full output)
- [ ] Paths reported (not content)
