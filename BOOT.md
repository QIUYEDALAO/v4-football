# BOOT.md — 静态启动纪律

本文件只作为人工/Agent 参考，不再由 boot-md hook 自动执行。

每次启动或接到 BOSS 指令前，OpenClaw 应遵守：

1. 先读取 MEMORY.md；
2. 先读取 STATE_CURRENT.md；
3. 检查 DEPRECATION_REGISTRY.md；
4. 检查 watchdog 状态；
5. 检查是否有 BLOCKER；
6. 不主动改系统；
7. 不主动重跑任务；
8. 不自由 kill/retry；
9. 等待 BOSS 指令。

## 禁止

- 不得主动发送 boot check
- 不得使用 message tool 发送启动检查结果
- 不得在聊天窗口打开时自动执行
- 不得回复 NO_REPLY 循环
- 不得把启动检查注入正常聊天上下文

## 启动检查由以下任务承担

- 每日 17:25 STATE_CURRENT 更新
- HEARTBEAT.md 人工/定时检查
- watchdog 状态文件
- BOSS 手动指令
