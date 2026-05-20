# Intel Scheduler Migration Plan — Fixed-Delay → Completion-Based Refresh

> 生效日期：2026-05-21
> 版本：3.2

---

## 1. 迁移说明

### 旧机制（已废弃）

- 固定时间刷新（已废弃）：12:02 / 13:02 / 14:02 / 15:02 / 23:47
- 任务开始后固定 +2 分钟执行 refresh（已废弃）
- 未检查任务是否完成、output 是否新鲜、是否有 BLOCKER（已废弃）

### 新机制（3.2）

- 所有 refresh 基于任务完成事件触发
- 核心任务：after_success → 全量 refresh
- 高频任务：after_status_change + throttle
- 失败任务：only status/risk refresh (last_good_snapshot / DEGRADED)
- 兜底：15:10 fallback refresh（not only refresh）

---

## 2. 目标任务迁移明细

### V4_DAILY_SCAN_READONLY

| 字段 | 值 |
|:---|:---|
| schedule | 12:00 |
| command | `python3 engine/v4_scan_and_brief.py --date YYYY-MM-DD --review-only --no-push --no-state-write --no-verified-write --no-cron` |
| completion_condition | returncode=0 + watchdog/scout status DONE + output fresh + no partial + no BLOCKER |
| post_success_refresh | ✅ `intel_ops_refresh.py` + `intel_desk_html.py` |
| post_failure_status_refresh | ✅ 只刷 status/risk + last_good_snapshot |
| refresh_type | EVENT_REFRESH_AFTER_SUCCESS |
| refresh_trigger | after_success |
| fixed_delay_refresh | ❌ false |
| output_freshness_check | ✅ output_mtime >= task_started_at |
| partial_output_guard | ✅ no .partial / .tmp / incomplete output |
| safety_flags | `--no-push --no-state-write --no-verified-write --no-cron` |

### V4_VALIDATION_DRY_RUN

| 字段 | 值 |
|:---|:---|
| schedule | 13:00 |
| command | `python3 tools/v4_validate.py --date YYYY-MM-DD --dry-run` |
| completion_condition | returncode=0 + validation result fresh + no partial |
| post_success_refresh | ✅ `intel_ops_refresh.py` + `intel_desk_html.py` |
| post_failure_status_refresh | ✅ 只刷 status |
| refresh_type | EVENT_REFRESH_AFTER_SUCCESS |
| refresh_trigger | after_success |
| fixed_delay_refresh | ❌ false |
| output_freshness_check | ✅ |
| partial_output_guard | ✅ |
| safety_flags | `--dry-run --no-push --no-state --no-verified` |

### V2_DAILY_POOL_READONLY

| 字段 | 值 |
|:---|:---|
| schedule | 14:00 |
| command | `python3 engine/daily_runner.py --run_tag DAILY_POOL` |
| completion_condition | returncode=0 + pool summary fresh + no partial |
| post_success_refresh | ✅ `intel_ops_refresh.py` + `intel_desk_html.py` |
| post_failure_status_refresh | ✅ 只刷 status |
| refresh_type | EVENT_REFRESH_AFTER_SUCCESS |
| refresh_trigger | after_success |
| fixed_delay_refresh | ❌ false |
| output_freshness_check | ✅ |
| partial_output_guard | ✅ |
| safety_flags | `--run_tag DAILY_POOL --no-push --no-state --no-verified` |

### V2_WINDOW_CHECKER_READONLY

| 字段 | 值 |
|:---|:---|
| schedule | 14:30 → next 11:30 每 30 分钟 |
| command | `python3 tools/v2_window_checker_with_watchdog.py` |
| completion_condition | returncode=0 + status in DONE/SKIPPED |
| refresh_trigger | after_status_change |
| refresh_type | CONDITIONAL_EVENT_REFRESH |
| throttle | 30 分钟 |
| throttle_reason | 窗口检查频繁执行，但不必每次都刷新 dashboard |
| status_change_trigger | BET_LOCKED / WATCH / CANDIDATE / SKIP count 变化，active_window 变化 |
| fixed_delay_refresh | ❌ false |

### V4_LIVE_SNAPSHOT_FOR_ATTRIBUTION

| 字段 | 值 |
|:---|:---|
| schedule | 每 3 分钟（仅匹配日活跃时） |
| command | `python3 tools/v4_live_stats_snapshot.py --watch` |
| completion_condition | snapshot created |
| refresh_trigger | after_new_snapshot |
| refresh_type | CONDITIONAL_EVENT_REFRESH |
| throttle | 15 分钟 |
| throttle_reason | 3 分钟一个 snapshot，但 15 分钟才刷新一次 dashboard |
| status_change_trigger | new goal / decision_log / shadow / sim |
| fixed_delay_refresh | ❌ false |

### FALLBACK_INTEL_REFRESH_HTML

| 字段 | 值 |
|:---|:---|
| schedule | 15:10 |
| command | `python3 tools/intel_ops_refresh.py && python3 tools/intel_desk_html.py` |
| fallback_only | ✅ true |
| not_only_refresh | ✅ true（不是唯一 refresh） |
| completion_condition | N/A（兜底） |
| fixed_delay_refresh | ✅ true（但仅限于 fallback_role） |
| refresh_trigger_scan | ❌ false |

### QQ_PREVIEW_ONLY_READS_LATEST

| 字段 | 值 |
|:---|:---|
| schedule | 15:15 |
| command | 只读 latest dashboard |
| trigger_scan | ❌ false |
| trigger_validation | ❌ false |
| send | ❌ false（仅预览） |

### DAILY_STATUS_SUMMARY

| 字段 | 值 |
|:---|:---|
| schedule | 23:45 |
| command | `python3 engine/sys_daily_settlement_summary.py` |
| completion_condition | returncode=0 + summary generated |
| post_success_refresh | ✅ `intel_ops_refresh.py` + `intel_desk_html.py` |
| refresh_type | EVENT_REFRESH_AFTER_DAILY_SUMMARY |
| refresh_trigger | after_success |
| fixed_delay_refresh | ❌ false |

---

## 3. 迁移检查清单

- [x] 删除固定 12:02 refresh
- [x] 删除固定 13:02 refresh
- [x] 删除固定 14:02 refresh
- [x] 删除固定 15:02 refresh
- [x] 删除固定 23:47 refresh
- [x] 新增 V4 scan after_success refresh
- [x] 新增 V4 validation after_success refresh
- [x] 新增 V2 pool after_success refresh
- [x] 新增 V2 validation after_success refresh
- [x] V2 window checker → after_status_change + throttle 30min
- [x] V4 live snapshot → after_new_snapshot + throttle 15min
- [x] 15:10 → fallback_only + not_only_refresh
- [x] QQ preview 只读 latest dashboard
- [x] Failure status refresh 定义
- [x] Output freshness check 定义
- [x] Partial output guard 定义
- [x] Last good snapshot policy 定义
- [x] Degraded status policy 定义

---

## 4. 安全边界

```
REFRESH_TRIGGERS_SCAN=false
REFRESH_TRIGGERS_VALIDATION=false
QQ_PREVIEW_TRIGGERS_SCAN=false
QQ_PREVIEW_TRIGGERS_VALIDATION=false
CRON_MODIFIED=false
GATEWAY_CRON_MODIFIED=false
QQ_SENT=false
STATE_WRITTEN=false
VERIFIED_WRITTEN=false
D13_EXECUTE=false
PHASE_E=false
```

---

## 5. 合规标记

```
SCHEDULER_USES_COMPLETION_BASED_REFRESH=true
NO_FIXED_DELAY_REFRESH=true
ALL_CORE_TASKS_HAVE_COMPLETION_CONDITION=true
ALL_CORE_TASKS_HAVE_OUTPUT_FRESHNESS_CHECK=true
ALL_CORE_TASKS_HAVE_PARTIAL_OUTPUT_GUARD=true
FALLBACK_REFRESH_ONLY=true
HIGH_FREQ_TASKS_HAVE_THROTTLE=true
V2_WINDOW_REFRESH_AFTER_STATUS_CHANGE=true
V4_LIVE_SNAPSHOT_REFRESH_AFTER_NEW_SNAPSHOT=true
D13=false
PHASE_E=false
```
