# OpenClaw Report Policy

> 建立时间：2026-05-15
> 原则：正式报告、状态报告、研究报告、异常报告严格分层

---

## 报告分层

### 正式报告
- V2/V4 正式结论
- 给 QQ
- systemEvent 原样推送

### 状态报告
- watchdog / cron / STATE_CURRENT
- 只讲任务状态

### 研究报告
- ResearchAgent 输出
- 不进入实盘 QQ 简报

### 异常报告
- AlertAgent 输出
- 只讲 FAILED / TIMEOUT / KILLED_SIGKILL / BLOCKER

---

## 禁止混用

- 研究报告不能变成正式推荐
- 状态报告不能改评级
- 异常报告不能加球评
- 正式报告不能被 AI 二次总结
- C级观察不能说成强推荐
- HT_SKIP不能说成推荐
