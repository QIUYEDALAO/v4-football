# OpenClaw Incident Response

> 建立时间：2026-05-15
> 原则：发现异常只标记、不自行处理策略

---

## P0 事故类型

- V33污染复燃
- 旧 HOURLY 复燃
- AI代理自由 kill/retry
- QQ推送非正式结论
- API Key 泄露
- V2/V4 重复扫描抢 API
- Gateway 启动失败
- cron 外层 timeout 误杀
- KILLED_SIGKILL 频繁出现
- systemEvent 被 announce 替代
- raw scout 被推到 QQ
- V4简报缺昨日验证
- V2将 WATCH_EARLY/CANDIDATE 当正式推荐

---

## 固定处理流程

1. 停止继续推送错误信息
2. 保留日志
3. 标记 BLOCKER
4. 报告 BOSS
5. 不自由修策略
6. 不自由重跑
7. 不自由 kill
8. 不自由改超时
9. 等待 BOSS 指令

---

## 禁止

- 不得自行选择口径
- 不得自行改评级
- 不得自行重算
- 不得用旧文件冒充新状态
