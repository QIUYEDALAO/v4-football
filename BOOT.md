# BOOT.md — 启动检查清单

每次启动必须执行：

---

1. 【必须】读取 MEMORY.md
2. 【必须】读取 STATE_CURRENT.md
3. 【必须】检查 DEPRECATION_REGISTRY.md
4. 【必须】检查 watchdog 状态
5. 【必须】检查是否有 BLOCKER

---

## 启动后禁止

- 不主动改系统
- 不主动重跑任务
- 不自由 kill/retry
- 等待 BOSS 指令
