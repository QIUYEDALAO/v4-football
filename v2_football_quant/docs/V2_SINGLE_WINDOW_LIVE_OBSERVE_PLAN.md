# V2 Single-window Live Observe Plan (Phase D.8.5)

> 本文档仅定义单窗口 live observe 方案，**本轮不执行 live**。

## 1. 执行属性

- live_observe_execution_allowed=false
- settlement_write_allowed=false
- qq_push_allowed=false
- production_verified=false
- boss_approval_required=true

## 2. 计划范围

- 仅限单窗口观察（single-window）
- 仅观察 watchdog / marker / preflight 行为
- 不触发 DAILY_POOL / window_checker / settlement 执行
- 不发送 QQ

## 3. 强制边界

- preflight fail-closed 必须开启
- no-settlement-write
- no-QQ-push
- no-PRODUCTION_VERIFIED
- 失败仅报告 watchdog 状态
- 不允许 AI 自由 kill/retry
- 不允许补推
- 不允许补记
- 不允许手动修历史 verified

## 4. 回滚准备

- 任何异常立即保持 cron 关闭
- 保留全部日志与状态 marker
- 仅追加审计说明，不覆盖历史证据

## 5. 结论

- D.8.5 当前仅可 `READY_FOR_BOSS_REVIEW`（计划可评审）。
- 进入执行必须等待 D.8.7 之后的单独 BOSS 指令。
