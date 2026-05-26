# V4 Control Center System Error Center

**Phase**: V4-CONTROL-CENTER-SYSTEM-ERROR-CENTER-20260526  
**Status**: `V4_SYSTEM_ERROR_CENTER_PASS`  
**Date**: 2026-05-26

## Overview

在 V4 统一作战台新增只读系统异常中心。扫描 `data/runtime/status/*.json` 和 `logs/*.log`，脱敏密钥后输出安全摘要，在作战台前端以只读 drawer 面板展示。

## Architecture

```
collect_v4_system_error_summary.py          ← 只读扫描器
       ↓
build_v4_control_center_model.py            ← 接入 model["system_errors"]
       ↓
v4_control_center.html (buildErrorsPanel)   ← 前端渲染
```

## Changes

### New Files
| File | Purpose |
|------|---------|
| `tools/collect_v4_system_error_summary.py` | 只读系统异常摘要采集器，扫描 status JSON 和日志文件 |
| `tools/check_v4_system_error_center.py` | 52 项安全守卫检查 |

### Modified Files
| File | Change |
|------|--------|
| `tools/build_v4_control_center_model.py` | 新增 `_load_system_error_summary()`，接入 model 并更新 system_status |
| `data/runtime/dashboard/v4_control_center.html` | 新增系统异常中心按钮、导航、drawer 面板和渲染逻辑 |

## Safety Guarantees

- **只读**: 采集器仅读取文件，不修改任何源文件
- **脱敏**: 6 种正则脱敏规则覆盖 api_key/auth/bearer/token/private_key
- **raw_log_hidden=true**: 所有输出项标记，前端不展示原始日志
- **safe_to_show=true**: 所有输出项标记
- **无操作按钮**: 前端不提供 kill/retry/rerun 按钮
- **短路径**: 仅显示文件名，不显示完整路径
- **最多 20 条**: 每类限制输出条数
- **每条最多 5 行**: 前端渲染严格控制

## Error Classification

| 等级 | 条件 | 展示 |
|------|------|------|
| BLOCKER | active + BLOCKER 关键字 | 红色左侧边框 |
| FAIL | active + ERROR/CRASH/EXCEPTION | 橙色左侧边框 |
| WARN | 已恢复 或 WARN 关键字 | 黄色左侧边框 |
| RESOLVED | 后续 PASS 覆盖 | 灰色 "已恢复" 标签 |

## Frontend Integration

- 系统控制卡片：新增 "系统异常" 按钮（异常数 badge）
- 底部导航：新增 "⚠ 异常" 按钮（blocker 时红点指示）
- 顶部状态 pill：实时反映异常计数
- Drawer 面板：ACTIVE / RECENT 分区展示，底部锁定声明

## Checker Results
- 52/52 checks passed
- Coverage: collector safety, model integration, frontend safety, prohibition items

## Compliance

| Item | Status |
|------|--------|
| Full scan ran | NO |
| Validation recomputed | NO |
| Strategy changed | NO |
| Candidate changed | NO |
| Live bet records modified | NO |
| QQ push | NO |
| Cloud publish | NO |
| Cron modified | NO |
| Secrets exposed | NO |
| Kill/retry/rerun provided | NO |
| Raw logs displayed | NO |
