# Intel Scheduler Target Policy

> 生效日期：2026-05-21
> 版本：3.2

---

## 1. 核心原则

- ✅ 所有 refresh 基于任务完成事件触发，**非固定时间延迟**
- ✅ 任务完成后立即执行 `intel_ops_refresh.py` + `intel_desk_html.py`
- ✅ 高频任务按 status change + throttle 触发
- ✅ 15:10 为兜底 fallback refresh
- ❌ 禁止使用 12:02 / 13:02 / 14:02 / 15:02 固定延迟刷新

---

## 2. 目标调度表

| 时间 | 任务 | Refresh 类型 | 刷新触发 |
|:---|:---|:---:|:---|
| 12:00 | V4_DAILY_SCAN_READONLY | EVENT_REFRESH_AFTER_V4_SCAN | after_success |
| 13:00 | V4_VALIDATION_DRY_RUN | EVENT_REFRESH_AFTER_V4_VALIDATION | after_success |
| 14:00 | V2_DAILY_POOL_READONLY | EVENT_REFRESH_AFTER_V2_POOL | after_success |
| 14:30→11:30 | V2_WINDOW_CHECKER_READONLY（每 30min） | CONDITIONAL_EVENT_REFRESH | after_status_change |
| 3min interval | V4_LIVE_SNAPSHOT_FOR_ATTRIBUTION（仅比赛日活跃时） | CONDITIONAL_EVENT_REFRESH | after_new_snapshot |
| 15:00 | V2_VALIDATION_DRY_RUN | EVENT_REFRESH_AFTER_V2_VALIDATION | after_success |
| **15:10** | **FALLBACK_INTEL_REFRESH_HTML** | **FALLBACK_REFRESH** | **fallback_only** |
| 15:15 | QQ_PREVIEW_ONLY_READS_LATEST | — | — |
| 23:45 | DAILY_STATUS_SUMMARY | EVENT_REFRESH_AFTER_DAILY_SUMMARY | after_success |

---

## 3. 刷新触发细则

### 3.1 After Success（核心任务）

每个核心任务必须在实际完成后触发刷新：

```
Task Completed
  ├── returncode == 0 ?
  ├── timeout/partial ?
  ├── output file fresh ?
  ├── no BLOCKER ?
  ├── no forbidden guard?
  └── ALL PASS → intel_ops_refresh.py + intel_desk_html.py
                → FAIL 只刷 status/risk
```

### 3.2 After Status Change（高频任务）

```
V2_WINDOW_CHECKER completed
  ├── BET_LOCKED / WATCH / CANDIDATE count changed?
  ├── active_window changed?
  ├── throttle ≥ 30min?
  ├── YES → refresh
  └── NO  → skip, log only

V4_LIVE_SNAPSHOT completed
  ├── new snapshot / goal / decision_log / shadow / sim?
  ├── throttle ≥ 15min?
  ├── YES → refresh
  └── NO  → skip, log only
```

### 3.3 After Failure

```
Task FAILED/BLOCKER/TIMEOUT
  ├── refresh status section only
  ├── risk indicator = RED/YELLOW
  ├── data section = last_good_snapshot or DEGRADED
  └── no QQ send, no scan trigger
```

### 3.4 Fallback（兜底）

```
15:10 fallback cron
  ├── only_refresh = false
  ├── no scan/validation trigger
  ├── no task failure override
  └── produce latest dashboard (even if DEGRADED)
```

---

## 4. 核心任务完成判据

| 任务 | 完成判据 |
|:---|:---|
| V4_DAILY_SCAN_READONLY | returncode=0 + watchdog DONE + scout/brief fresh + no partial |
| V4_VALIDATION_DRY_RUN | returncode=0 + review result fresh |
| V2_DAILY_POOL_READONLY | returncode=0 + pool summary fresh |
| V2_VALIDATION_DRY_RUN | returncode=0 + validation result fresh |
| DAILY_STATUS_SUMMARY | returncode=0 + summary generated |

---

## 5. 安全边界

| 检查项 | 值 |
|:---|:---|
| Refresh 触发 scan | ❌ false |
| Refresh 触发 validation | ❌ false |
| QQ preview 触发 scan | ❌ false |
| QQ preview 触发 validation | ❌ false |
| Refresh 推 QQ | ❌ false |
| Refresh 写 state | ❌ false |
| Refresh 写 verified | ❌ false |

---

## 6. 合规标记

```
NO_FIXED_DELAY_REFRESH=true
NO_1202_FIXED=true
NO_1302_FIXED=true
NO_1402_FIXED=true
NO_1502_FIXED=true
NO_2347_FIXED=true
AFTER_SUCCESS_REFRESH_DEFINED=true
AFTER_STATUS_CHANGE_REFRESH_DEFINED=true
FAILURE_STATUS_REFRESH_DEFINED=true
FALLBACK_REFRESH_TIME=15:10
FALLBACK_REFRESH_ONLY=true
FALLBACK_REFRESH_NOT_ONLY_REFRESH=true
V2_WINDOW_HAS_THROTTLE=true
V2_WINDOW_THROTTLE_MINUTES=30
V4_SNAPSHOT_HAS_THROTTLE=true
V4_SNAPSHOT_THROTTLE_MINUTES=15
REFRESH_NO_SCAN=true
REFRESH_NO_VALIDATION=true
REFRESH_NO_PUSH=true
REFRESH_NO_STATE=true
REFRESH_NO_VERIFIED=true
QQ_PREVIEW_READS_LATEST=true
QQ_PREVIEW_NO_SCAN=true
PHASE_E=false
D13_EXECUTE=false
```
