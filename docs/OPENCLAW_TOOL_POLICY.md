# OpenClaw Tool Policy

> 建立时间：2026-05-15
> 原则：工具权限按角色最小化

---

## 原则

工具权限按角色最小化。
不是所有 Agent 都能 exec/write/edit/apply_patch。
DevAgent 权限最高，但不能由 cron 自动触发。

---

## ClawOps

**允许：**
- read
- exec（固定脚本）
- send systemEvent
- 检查 watchdog
- 检查 cron
- 检查 gateway status

**禁止：**
- 自由执行未知命令
- 自由 kill/retry
- 自由修改代码
- 自由改策略
- 自由总结比赛

---

## AlertAgent

**允许：**
- read
- systemEvent
- 读取 watchdog 状态

**禁止：**
- exec
- write
- edit
- apply_patch
- git
- cron 修改
- gateway 修改
- kill/retry

---

## DevAgent

**允许：**
- read
- write
- edit
- apply_patch
- exec
- git commit/push

**限制：**
- 只能 BOSS 明确指令触发
- 不得 cron 自动触发
- 不得自行改策略阈值
- 不得直接推送比赛建议

---

## ResearchAgent

**允许：**
- read data
- write research reports
- 读取 attribution / validation / rolling stats

**禁止：**
- cron
- gateway
- strategy edit
- final QQ push
- 实时评级覆盖

---

## ReportAgent

**允许：**
- read formal reports
- write qq formatted reports
- 优化排版

**禁止：**
- 改评级
- 改推荐
- 改模型
- 改策略
- 读取 raw scout 后重算

---

## Sandbox 建议

非 owner / 非 DevAgent：
优先 workspaceAccess=ro 或 none。

DevAgent：
如启用 sandbox，必须明确 workspaceAccess。
不得默认 full host access。
