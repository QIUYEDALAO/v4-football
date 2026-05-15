# OpenClaw Agent Architecture

> 建立时间：2026-05-15
> 当前阶段：治理规则建立期
> 核心原则：先建立职责边界和纪律，再分阶段启用 Agent

---

## 当前原则

当前阶段暂不立即启用多个 Agent。
先建立职责边界、权限矩阵、workspace 纪律和审计工具。
等 V2/V4 自动任务稳定后，再分阶段启用。

多 Agent 的目的不是让 AI 更自由，而是让 OpenClaw 更守纪律。

---

## 未来 Agent 规划

### 1. ClawOps

**定位：** 系统总控操作员。

**职责：**
- 管理 V2/V3/V4 总状态
- 读取 STATE_CURRENT.md
- 读取 watchdog 状态
- 检查 cron 状态
- 推送正式系统报告
- 接收 BOSS 指令
- 维护系统运行纪律

**允许：**
- 读取状态文件
- 执行固定脚本
- 发送 systemEvent
- 检查 watchdog
- 检查 cron

**禁止：**
- 不分析比赛
- 不重算评级
- 不修改策略
- 不自由 kill/retry
- 不把 C 级说成强推荐
- 不把 HT_SKIP 说成推荐
- 不用 raw scout 覆盖正式 brief

---

### 2. AlertAgent

**定位：** 异常通知员。

**职责：**
- 只读取 watchdog / cron 状态
- 只报告 FAILED / TIMEOUT / KILLED_SIGKILL / BLOCKER / CRON_TIMEOUT
- 只发送异常提醒

**允许：**
- read
- systemEvent
- 读取 data/runtime/status

**禁止：**
- 不分析比赛
- 不重跑任务
- 不修改代码
- 不修改策略
- 不执行 kill/retry
- 不解释推荐

**建议：** 第一个可以启用的独立 Agent。

---

### 3. DevAgent

**定位：** 代码修改员。

**职责：**
- 只在 BOSS 明确指令下修改代码
- 修 bug
- 新增脚本
- 更新 cron
- 跑语法检查
- git commit / push

**允许：**
- read
- write
- edit
- apply_patch
- exec
- git

**限制：**
- 不得由 cron 自动触发
- 不得自行修改策略阈值
- 不得输出比赛推荐
- 每次修改必须输出变更清单

---

### 4. ResearchAgent

**定位：** 离线研究员。

**职责：**
- 赛后复盘
- 周报
- 月报
- 样本验证
- 归因统计
- 滚动命中率
- 规则观察建议

**允许：**
- 读取归因文件
- 读取验证文件
- 写研究报告

**禁止：**
- 不碰 cron
- 不推实盘建议
- 不覆盖系统正式评级
- 不直接改规则
- 不改实时评分

---

### 5. ReportAgent

**定位：** 报告格式员。

**职责：**
- 优化 QQ 移动端简报
- 优化日报/周报/月报排版
- 生成 iPhone QQ 友好版本
- 保持报告简洁整齐

**允许：**
- 读取正式报告
- 生成 QQ 版报告
- 写 report 文件

**禁止：**
- 不改 A/B/C/SKIP
- 不重算评级
- 不追加球评
- 不把研究结论变成正式推荐
- 不读取 raw scout 后自行评级

---

## 启用顺序

| 天数 | Agent | 条件 |
|:---:|:------|:-----|
| D0 | — | 只建立架构文件，不启用多 Agent |
| D1 | AlertAgent | 优先考虑，异常通知最独立 |
| D3 | ReportAgent | 稳定后考虑 |
| D7 | ResearchAgent | 稳定后考虑 |
| D14 | DevAgent | 最后考虑 |

## 当前结论

当前先保持主 Agent 运行。
多 Agent 只进入规划和治理文件。
任何真实创建 Agent 的动作，必须等待 BOSS 明确批准。
