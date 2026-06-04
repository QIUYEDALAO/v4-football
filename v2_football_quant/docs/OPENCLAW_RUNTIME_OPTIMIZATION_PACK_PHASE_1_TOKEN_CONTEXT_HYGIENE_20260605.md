# OpenClaw Runtime Optimization — Phase 1: Token / Context Hygiene

**Created**: 2026-06-05 01:06 CST
**Workspace**: v4-football / v2_football_quant

---

## 1. Motivation

Recent token growth root cause:

```
Main session context:
├── API-Football raw odds JSON        ~300K
├── agent-browser DOM/snapshot/HTML   ~200K
├── Checker full JSON                  ~360K
├── OCR/PDF full text                  ~200K
├── Multi-stage long reports           ~100K
└── Total                             ~1.1M input tokens
```

The fix is **not** a smaller model — it's **structural context separation**.

## 2. Main Session Responsibilities

The main (coordinator) session does **only**:

| Step | Action | Example |
|------|--------|---------|
| 1 | Read current memory/status | `memory_get(MEMORY.md)` |
| 2 | Write task brief to memory | `memory/2026-06-05-task.md` |
| 3 | Spawn child session | `sessions_spawn(task=..., mode="run")` |
| 4 | Wait for child | `sessions_yield()` |
| 5 | Read child summary artifact | `read(child_output_path)` |
| 6 | Write memory summary | `edit(MEMORY.md)` |
| 7 | Stage/commit/push | `git add {files}; git commit; git push` |
| 8 | Report to BOSS | `<10 line summary` |

**Never** in main session:
- Raw API responses
- Browser HTML/DOM
- Checker full JSON
- OCR full text
- Long `git diff`

## 3. Child Session Responsibilities

Child (worker) sessions are:

- Launched with `lightContext=true`
- Do **not** inherit main session history
- Execute heavy work (API, browser, OCR, checker)
- Write large outputs to `data/runtime/` artifacts
- Return only a short summary JSON/text
- `cleanup="delete"` — destroyed after completion
- Do **not** commit, push, or modify production config

## 4. Applicable Scenarios

| Scenario | Child session | Artifact output |
|----------|--------------|-----------------|
| API batch query (192 fixtures) | ✅ | `data/runtime/.../coverage_summary.json` |
| Odds snapshot | ✅ | `data/runtime/.../snapshot_*.json` |
| Browser rendering | ✅ | `screenshot.png`, `rendered.html` |
| OCR / PDF | ✅ | `ocr_output.json`, `ocr_summary.json` |
| Checker matrix (6+ checkers) | ✅ | `data/runtime/status/*.json` |
| Large JSON validation | ✅ | `summary.json` |
| War room rebuild | ✅ | `processed/*.json` paths |
| Match card rebuild | ✅ | `match_card_*.json` |
| Dashboard content check | ✅ | `check_summary.json` |

## 5. Forbidden Content in Main Session

The following must **never** be returned to the main session:

- ❌ Raw API response body
- ❌ Raw odds JSON (only summary)
- ❌ Browser DOM / snapshot / HTML
- ❌ OCR full text
- ❌ Checker full JSON (only name + PASS/FAIL)
- ❌ Runtime/log full text
- ❌ Long git diff
- ❌ Full dataframe / full table

## 6. Allowed Content in Main Session

Only the following should return:

- ✅ STATUS: DONE / FAILED / BLOCKED
- ✅ Counts (records, fixtures, teams)
- ✅ PASS / FAIL / BLOCKER
- ✅ Top 10 error samples (max)
- ✅ Artifact file paths
- ✅ Checker names + PASS/FAIL
- ✅ Commit hash
- ✅ Push status
- ✅ Next action

## 7. Memory Bridge Rules

**Allowed writes:**
- task name
- status
- commit hash
- artifact paths
- counts
- checker summary
- next action

**Forbidden writes:**
- ❌ secrets / env / key / token
- ❌ raw API response
- ❌ raw HTML / DOM
- ❌ OCR full text
- ❌ full checker JSON
- ❌ large runtime / log

## 8. Artifact Summary Rules

Every child session must write:

```
data/runtime/.../{task_name}_summary.json
data/runtime/.../{task_name}_summary.md
data/runtime/status/{task_name}_status.json
```

Each summary must contain:
- `status`
- `counts`
- `checker_summary`
- `warnings`
- `blockers`
- `artifact_paths`
- `token_hygiene` fields (see section 10)

## 9. High-Risk STOP Rules

Child session must **stop and report** immediately on encountering:

| Rule | Trigger |
|------|---------|
| **STOP_CRON** | Any cron/launchd modification |
| **STOP_QQ_PUSH** | Any QQ recommendation push |
| **STOP_LIVE_SCAN** | Any live scan execution |
| **STOP_PROD_CONFIG** | Any production config change |
| **STOP_SECRETS** | Any secrets/env/key/token access |
| **STOP_DELETE** | Any delete/reset/clean operation |
| **STOP_BETTING** | Any betting/funds/trading output |
| **STOP_V4_GRADE** | Any V4 official grade change |
| **STOP_VALIDATION** | Any validation rewrite |

## 10. Token Hygiene Self-Check Fields

Every output must declare:

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

## 11. Execution Flow Diagram

```
MAIN SESSION                    CHILD SESSION(S)              RUNTIME / GIT
─────────────                   ────────────────              ─────────────
read memory
write task brief
spawn child ─────────────────▶  load task brief
                               execute heavy work
                               write artifact ───────────▶   summary.json
                               return summary                   summary.md
sessions_yield() ◀─────────────
read artifact ───────────────▶                             read summary
write memory summary
stage/commit/push ──────────▶                              git push
report to BOSS
```
