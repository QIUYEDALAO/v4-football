# OpenClaw Child Session Task Template

**Version**: 1.0
**Status**: template

---

## 1. When to Use

Use this template whenever:
- API batch query
- odds snapshot
- browser rendering
- OCR / PDF
- checker matrix
- large JSON validation
- war room rebuild
- match card rebuild
- dashboard content check

## 2. Template Text

```
任务目标：
{clear one-line objective}

执行边界：
- read-only unless authorized
- write outputs to data/runtime/{task_name}/{date}/
- not commit / push
- not modify production config
- not call cron/launchd
- not QQ push
- not live scan
- not read/print secrets
- stop on STOP_* rules
- cleanup=delete after return

已知上下文（由主 session 提供）：
{key facts from memory, prior commits, relevant file paths}

执行步骤：
Step 1: {step}
Step 2: {step}
Step 3: {step}
...

每一步验收标准：
{per-step pass criteria}

自动推进规则：
PASS 自动下一步
FAIL/BLOCKER/不确定，停止并报告

最终输出：
STATUS: DONE / FAILED / BLOCKED

output:
{
  "status": "...",
  "counts": {...},
  "checker_summary": "...",
  "warnings": [...],
  "blockers": [...],
  "artifact_paths": [...],
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

## 3. Main Session Snippet

```python
# Main session:
# 1. Write task brief to memory
write("memory/20260605_task_brief.md", task_brief)

# 2. Spawn child
sessions_spawn(
    task=task_template,
    mode="run",
    cleanup="delete",
    lightContext=True
)

# 3. Wait
sessions_yield()

# 4. Read artifact
import json
artifact = json.loads(read(f"data/runtime/{task_name}/{date}/summary.json"))

# 5. Write memory summary
edit(MEMORY.md, old=..., new=...)
```

## 4. Forbidden Content in Child Output

Child session must NOT return to main session:
- raw API responses
- raw HTML/DOM/snapshot
- checker full JSON
- OCR full text
- runtime/log full text
- secrets/env/funds

Allowed to return: STATUS, counts, PASS/FAIL/blockers, artifact paths, next action.

## 5. Safety Reminder

Always include STOP_* rules in child session boundary:
- STOP_CRON
- STOP_QQ_PUSH
- STOP_LIVE_SCAN
- STOP_PROD_CONFIG
- STOP_SECRETS
- STOP_DELETE
- STOP_BETTING
- STOP_V4_GRADE
- STOP_VALIDATION
