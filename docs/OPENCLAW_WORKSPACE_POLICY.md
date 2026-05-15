# OpenClaw Workspace Policy

> 建立时间：2026-05-15
> 当前原则：只保留一个 active workspace

---

## 当前原则

当前阶段只保留一个 active workspace：
`/Users/liudehua/.openclaw/workspace`

不要马上为每个 Agent 复制代码仓库。
避免 workspace 状态漂移。

---

## Workspace 文件职责

| 文件 | 职责 |
|:----|:-----|
| AGENTS.md | 操作宪法。写系统边界、禁止事项、正式输出优先级 |
| SOUL.md | 角色风格。冷静、执行型、非球评、不自由发挥 |
| USER.md | BOSS 信息和系统背景 |
| TOOLS.md | 本地工具、脚本、cron、git、watchdog 使用规则 |
| HEARTBEAT.md | 每日健康检查清单 |
| BOOT.md | 每次启动必须先读 STATE_CURRENT.md 和 MEMORY.md |
| MEMORY.md | 长期规则。不得写短期状态。不得写 API Key |
| STATE_CURRENT.md | 短期系统状态。每日更新。不得写长期规则 |
| memory/YYYY-MM-DD.md | 每日运行记录，可归档 |

---

## Workspace 禁止事项

- 不允许旧 workspace 继续跑 cron
- 不允许旧 workspace 推送报告
- 不允许多个 workspace 指向不同代码状态
- 不允许短期状态写入 MEMORY.md
- 不允许 API Key / Token 写入任何 workspace 文档
- 不允许 DevAgent 和 ResearchAgent 同时写 STATE_CURRENT.md

---

## 状态写入权

| 文件 | 允许写入者 |
|:----|:----------|
| STATE_CURRENT.md | 仅限 ClawOps / SYS 状态任务 |
| research_reports/ | ResearchAgent |
| report/ | ReportAgent |
| 代码文件 + changelog | DevAgent |
| 系统状态文件 | AlertAgent（只读，不写） |
