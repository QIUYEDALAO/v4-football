# Intel Refresh Trigger Policy

> 生效日期：2026-05-21
> 版本：3.2

---

## 1. 刷新触发规则

Intel Ops Refresh 的触发机制已从 **固定延迟** 改为 **任务完成事件触发**。

### 旧机制（已废弃）

```
12:02 → intel_ops_refresh.py  ❌ 不安全（已废弃）
13:02 → intel_ops_refresh.py  ❌ 不安全（已废弃）
14:02 → intel_ops_refresh.py  ❌ 不安全（已废弃）
15:02 → intel_ops_refresh.py  ❌ 不安全（已废弃）
23:47 → intel_ops_refresh.py  ❌ 不安全（已废弃）
```

### 新机制（3.2）

| 触发方式 | 说明 |
|:---|:---|
| after_success | 核心任务正常完成 → 全量刷新 |
| after_status_change | 高频任务状态变化 → 条件刷新（有 throttle） |
| after_failure | 任务失败 → 只刷 status/risk |
| fallback | 15:10 兜底刷新（not the only refresh） |

---

## 2. Event Refresh After Success

### 触发管道

```
Task Completed
  ├── returncode == 0 ?
  ├── status_marker in DONE/PASS/REVIEW_ONLY_READY ?
  ├── output_mtime >= task_started_at ?
  ├── no .partial/.tmp residual ?
  ├── no BLOCKER in logs ?
  ├── no forbidden guard true ?
  └── ALL ✅ → python3 tools/intel_ops_refresh.py
              → python3 tools/intel_desk_html.py
```

### 触发后刷新内容

- ✅ 最新 V4 brief 到 dashboard
- ✅ 最新 V2 pool 到 dashboard
- ✅ 最新 checker 结果到 dashboard
- ✅ 最新状态/异常到 dashboard

### 触发后的禁止

- ❌ 不得触发 V4 scan
- ❌ 不得触发 validation
- ❌ 不得推 QQ
- ❌ 不得写 state
- ❌ 不得写 verified

---

## 3. Event Refresh After Status Change

### 适用任务

| 任务 | 变化检测 | Throttle |
|:---|:---|---:|
| V2_WINDOW_CHECKER_READONLY | BET_LOCKED/WATCH/CANDIDATE/active_window | 30 分钟 |
| V4_LIVE_SNAPSHOT_FOR_ATTRIBUTION | new snapshot/goal/decision_log/shadow/sim | 15 分钟 |

### 检查逻辑

```
Task Completed
  ├── status changed since last refresh ?
  ├── throttle exceeded ?
  ├── YES → intel_ops_refresh.py + intel_desk_html.py
  └── NO  → skip, log reason
```

---

## 4. Event Refresh After Failure

### 触发条件

- `task_returncode != 0` 或 `status in [FAILED, BLOCKER, TIMEOUT]`

### 行为

| 区域 | 行为 |
|:---|:---|
| Status | 显示 FAILED/BLOCKER/TIMEOUT + 错误原因 |
| Risk | 黄色/红色指示器 + 失败时间 |
| Data sections | 保留 `last_good_snapshot` 或标记 `DEGRADED` |
| QQ send | ❌ 禁止 |

---

## 5. Fallback Refresh

| 项目 | 值 |
|:---|:---|
| 时间 | 15:10 |
| 类型 | fallback_only |
| not_only_refresh | ✅ true（不是唯一刷新） |
| 是否触发 scan | ❌ false |
| 是否覆盖 task failure | ❌ false |

---

## 6. QQ Preview

| 项目 | 值 |
|:---|:---|
| 来源 | 只读 latest dashboard |
| 触发 V4 scan | ❌ false |
| 触发 validation | ❌ false |
| 推 QQ | ❌ false |

---

## 7. 合规标记

```
NO_FIXED_DELAY_REFRESH=true
NO_1202_FIXED=true
NO_1302_FIXED=true
NO_1402_FIXED=true
NO_1502_FIXED=true
NO_2347_FIXED=true
EVENT_REFRESH_AFTER_SUCCESS_DEFINED=true
COMPLETION_CONDITION_REQUIRED=true
OUTPUT_FRESHNESS_CHECK_REQUIRED=true
PARTIAL_OUTPUT_GUARD_REQUIRED=true
FAILURE_STATUS_REFRESH_DEFINED=true
FALLBACK_REFRESH_ONLY=true
FALLBACK_REFRESH_NOT_ONLY_REFRESH=true
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

## 8. 安全边界（表记录）

| 项目 | 值 |
|:---|:---|
| No fixed delay refresh | ✅ true |
| 12:02 absent | ✅ true |
| 13:02 absent | ✅ true |
| 14:02 absent | ✅ true |
| 15:02 absent | ✅ true |
| Event refresh after success defined | ✅ true |
| Completion condition required | ✅ true |
| Output freshness check required | ✅ true |
| Partial output guard required | ✅ true |
| Failure status refresh defined | ✅ true |
| Fallback refresh time | 15:10 |
| Fallback refresh only | ✅ true |
| Fallback refresh not only refresh | ✅ true |
| QQ preview reads latest | ✅ true |
| QQ preview no scan | ✅ true |
| Refresh no scan | ✅ true |
| Refresh no validation | ✅ true |
| Refresh no push | ✅ true |
| Refresh no state write | ✅ true |
| Refresh no verified write | ✅ true |
| Phase E | ❌ false |
| D13 execute | ❌ false |

---

## 8. BLOCKER 条件

以下任一触发 BLOCKER：
- BLOCKER: 12:02/13:02/14:02/15:02 仍作为正式策略；
- BLOCKER: 出现 fixed +2min refresh 作为主机制；
- BLOCKER: 核心任务没有 completion condition；
- BLOCKER: refresh 可读取 partial output 作为成功结果；
- BLOCKER: 15:10 被写成唯一 refresh；
- BLOCKER: refresh 触发 scan/validation；
- BLOCKER: QQ/state/verified 被误设为 true。
