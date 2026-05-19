# V2 Window Scheduler Diagnostic — 2026-05-19

## Step 1: State Files
| Date | selected_fixtures | Status |
|------|-------------------|--------|
| 2026-05-19 | **MISSING** | NO_POOL_DATA |
| 2026-05-18 | **MISSING** | NO_POOL_DATA |
| 2026-05-17 | EXISTS (155 fixtures, 2 selected) | LAST_RUN |

**PASS**: state files correctly identified.

## Step 2: Window Summary
| Stage | 05/19 count | 05/18 count |
|-------|-------------|-------------|
| All stages | **0 fixtures** | **0 fixtures** |

No fixtures available for stage analysis — NO_POOL_DATA for both dates.

## Step 3: active_window=false Root Cause

**reason_enum: NO_POOL_DATA**

解释：
1. DAILY_POOL has not run since 2026-05-17.
2. Without DAILY_POOL, `selected_fixtures_YYYYMMDD.json` is never created.
3. Without selected fixtures, `v2_window_checker_with_watchdog.py` finds nothing to evaluate.
4. The checker correctly returns SKIPPED_NO_ACTIVE_WINDOW.
5. This is NOT a checker bug. It is NOT a timing issue. It is a data pipeline gap.

## Step 4: Auto-Scan Status
- auto_scan_enabled: **false**
- cron_status: **removed** (not paused, not broken — removed)
- last_scan_time: N/A (window checker runs on-demand only)
- scheduler: **disabled**

BOSS 不应被要求盲等。没有自动扫描，active_window 不会自己出现。

## Step 5: Checker Parse Quality
- CHECKER_PARSE_WEAK: **false**
- Method: string match against window checker output ("SKIPPED_NO_ACTIVE_WINDOW")
- The string match is correct and consistent with actual window checker output.
- Active window detection logic is adequate given the upstream data gap.

## Step 6: Web Page Update
- v2_today.html updated with: active_window=false reason, NO_POOL_DATA, auto_scan=disabled
- BOSS can see the specific reason on the web page.

## Step 7: Conclusion
**WINDOW_DIAG_READY**

### 回答
| 问题 | 答案 |
|------|------|
| 到底在等什么？ | 等 DAILY_POOL 运行，产出 selected_fixtures |
| 是否自动扫描？ | 否（cron 已移除） |
| 下一场什么时候进入窗口？ | 无 fixtures 可判断 |
| 为什么现在没有推荐？ | 无建池数据，窗口检查器无可评估比赛 |

### Required Action
To advance beyond READY_WAIT_ACTIVE_WINDOW:
1. Run DAILY_POOL (readonly mode) via `v2_daily_pool_readonly_runner.py`
2. This creates selected_fixtures_YYYYMMDD.json
3. Then window checker can evaluate active windows
4. Cron recovery is a separate BOSS decision

