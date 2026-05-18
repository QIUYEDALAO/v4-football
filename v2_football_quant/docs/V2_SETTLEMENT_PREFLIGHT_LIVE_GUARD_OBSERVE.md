# V2 Settlement Preflight Live Guard Observe Plan (Phase D.8.6)

> 本文档只定义 preflight live guard observe 计划，**本轮不执行 live**。

## 1. 执行属性

- live_guard_execution_allowed=false
- preflight_required=true
- fail_closed_required=true
- verify_date_blocked_when_preflight_blocks=true
- verified_write_blocked_when_preflight_blocks=true
- watchdog_status_required=true
- production_verified=false
- boss_approval_required=true

## 2. preflight 强前置

正式 settlement 入口必须先执行 preflight，且 fail-closed：

- `official_bet_locked=0` → BLOCK
- `new_locks_count=0` → BLOCK
- `lock_owner` 缺失 → BLOCK
- `missed_candidates` 存在 → BLOCK
- source marker 缺失 → BLOCK

## 3. BLOCK 状态硬约束

- BLOCK 时不得调用 `verify_date`
- BLOCK 时不得写 `verified`
- BLOCK 时 watchdog 状态必须为 `BLOCKED_PREFLIGHT`
- BLOCK 结果必须写入状态 marker

## 4. ALLOW 状态边界

- 即使未来出现 ALLOW，也不得自动写 `PRODUCTION_VERIFIED`
- ALLOW 不等于恢复生产完成
- 仍需 BOSS 单独审批后再进入后续受控执行步骤

## 5. 操作纪律

- 失败只报告 watchdog 状态
- 不允许 AI 自由 kill/retry
- 不允许手工覆盖历史证据

## 6. 结论

- D.8.6 当前仅输出计划并等待评审。
- 进入执行必须等待 D.8.7 单独审批。
