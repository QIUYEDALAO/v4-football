# Intel Task Completion Refresh Contract

> 生效日期：2026-05-21
> 版本：3.2

---

## 1. 刷新类型总览

| 类型 | 事件 | 适用场景 |
|:---|:---|:---|
| A | EVENT_REFRESH_AFTER_SUCCESS | 核心任务完成后立即刷新 |
| B | EVENT_REFRESH_AFTER_STATUS_CHANGE | 高频任务状态变化后条件刷新 |
| C | EVENT_REFRESH_AFTER_FAILURE_STATUS | 任务失败只刷新 status/risk 区 |
| D | FALLBACK_REFRESH | 15:10 固定兜底刷新 |
| E | QQ_PREVIEW_READS_LATEST | QQ 预览只读最新 dashboard |

---

## 2. A: EVENT_REFRESH_AFTER_SUCCESS

### 触发命令

```bash
python3 tools/intel_ops_refresh.py
python3 tools/intel_desk_html.py
```

### 触发条件（全部必须满足）

- `returncode == 0`
- `status_marker` in `DONE` / `PASS` / `REVIEW_ONLY_READY`
- `output_file_fresh == true`
  - `output_mtime >= task_started_at`
  - output file 存在且非空
- `no partial file` — 无 `.partial` / `.tmp` 残留
- `no BLOCKER` — 任务日志/状态中无 BLOCKER
- `no forbidden guard true` — 禁止标记未被误设为 true

### 适用任务

| 任务 | 完成后 refresh |
|:---|:---|
| V4_DAILY_SCAN_READONLY | ✅ EVENT_REFRESH_AFTER_V4_SCAN |
| V4_VALIDATION_DRY_RUN | ✅ EVENT_REFRESH_AFTER_V4_VALIDATION |
| V2_DAILY_POOL_READONLY | ✅ EVENT_REFRESH_AFTER_V2_POOL |
| V2_VALIDATION_DRY_RUN | ✅ EVENT_REFRESH_AFTER_V2_VALIDATION |
| DAILY_STATUS_SUMMARY | ✅ EVENT_REFRESH_AFTER_DAILY_SUMMARY |

---

## 3. B: EVENT_REFRESH_AFTER_STATUS_CHANGE

### 触发方式
高频任务（窗口检查器、live snapshot）每次完成后检查是否有状态变化：
- 有变化 → 触发 refresh
- 无变化 → 跳过（受 throttle 约束）

### 适用高频任务

#### V2_WINDOW_CHECKER_READONLY

| 条件 | 说明 |
|:---|:---|
| 触发条件 | BET_LOCKED_count 变化 / WATCH_EARLY_count 变化 / CANDIDATE_count 变化 / HT_SKIP_count 变化 / active_window 状态变化 |
| Throttle | 距上次 refresh ≥ 30 分钟 |
| 无变化 | 跳过 refresh，仅记录 |

#### V4_LIVE_SNAPSHOT_FOR_ATTRIBUTION

| 条件 | 说明 |
|:---|:---|
| 触发条件 | 新 snapshot 创建 / 新 goal event 检测 / 新 decision_log 行 / 新 shadow_backtest 行 / 新 execution_sim 行 |
| Throttle | 距上次 refresh ≥ 15 分钟 |
| 无变化 | 跳过 refresh，仅记录 |

---

## 4. C: EVENT_REFRESH_AFTER_FAILURE_STATUS

### 定义
如果任务失败，允许刷新 dashboard 的 status/risk 区，但必须明确显示失败。

### 触发条件

- `task_returncode != 0` OR `status == FAILED/BLOCKER/TIMEOUT`
- 只刷新 status section + risk indicator
- output data section 必须：
  - 保留 `last_good_snapshot`（上一次成功的完整数据），或
  - 标记 `DEGRADED`，明确告知数据可能过时
- 禁止把半成品作为成功结果推送
- 禁止发送 QQ

### Display

| 区域 | 行为 |
|:---|:---|
| Status | 显示 FAILED / BLOCKER / TIMEOUT + 原因 |
| Risk | 黄色/红色指示器 + 任务失败时间 |
| Data | 保留 last_good_snapshot 或显示 DEGRADED |

---

## 5. D: FALLBACK_REFRESH

| 项目 | 值 |
|:---|:---|
| 固定时间 | 15:10 |
| 类型 | fallback_only |
| 是否为唯一 refresh | ❌ 否 (`not_only_refresh=true`) |
| 是否触发 scan/validation | ❌ 否 |
| 是否覆盖 task failure 状态 | ❌ 否 |

### 作用
- 兜底刷新当天 dashboard
- 如果当天所有 refresh 都因失败跳过，15:10 至少让 dashboard 更新一次（哪怕显示 DEGRADED）
- 不得标记为唯一刷新机制

---

## 6. E: QQ_PREVIEW_READS_LATEST

| 项目 | 值 |
|:---|:---|
| QQ preview 来源 | 只读 latest dashboard |
| 是否触发 V4 scan | ❌ 否 |
| 是否触发 validation | ❌ 否 |
| 是否发送 | ❌ 否（仅预览） |

---

## 7. 禁止

- ❌ 固定 +2 分钟延迟刷新（12:02/13:02/14:02/15:02）
- ❌ 读取半成品作为成功结果
- ❌ 任务失败后刷新全量数据
- ❌ 15:10 作为唯一 refresh 机制
- ❌ refresh 触发 scan/validation
- ❌ QQ preview 触发 scan/validation
- ❌ refresh 推 QQ / 写 state / 写 verified

---

## 8. 合规标记

```
COMPLETION_REFRESH_DEFINED=true
EVENT_REFRESH_AFTER_SUCCESS_DEFINED=true
EVENT_REFRESH_AFTER_STATUS_CHANGE_DEFINED=true
EVENT_REFRESH_AFTER_FAILURE_DEFINED=true
FAILURE_REFRESH_STATUS_ONLY=true
LAST_GOOD_SNAPSHOT_POLICY_DEFINED=true
DEGRADED_STATUS_POLICY_DEFINED=true
FALLBACK_REFRESH_TIME=15:10
FALLBACK_REFRESH_ONLY=true
FALLBACK_REFRESH_NOT_ONLY_REFRESH=true
OUTPUT_FRESHNESS_CHECK_DEFINED=true
PARTIAL_OUTPUT_GUARD_DEFINED=true
QQ_PREVIEW_READS_LATEST=true
QQ_PREVIEW_NO_SCAN=true
REFRESH_NO_SCAN=true
REFRESH_NO_VALIDATION=true
REFRESH_NO_PUSH=true
REFRESH_NO_STATE_WRITE=true
REFRESH_NO_VERIFIED_WRITE=true
PHASE_E=false
D13_EXECUTE=false
```
