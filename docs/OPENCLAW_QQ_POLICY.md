# OpenClaw QQ Policy

> 建立时间：2026-05-15
> 原则：QQ 是通知通道，不是分析层

---

## 原则

- QQ 是通知通道，不是分析层
- 正式推送必须 systemEvent 原样发送
- 不得经过 AI 代理二次总结

---

## V4 推送

**只允许推送：**
`data/daily_reports/v4_openclaw_brief_qq_YYYYMMDD.txt`

**必须包含：**
- V4上半场情报
- 今日概览
- A/B/C/SKIP
- 昨日验证
- 滚动验证
- 今日结论

**禁止推送：**
- raw scout
- dashboard
- market_scores
- FULLTIME_OVER
- SECOND_HALF_OVER
- 高评分
- 球探扫描结果
- V33
- AI 二次总结
- OpenClaw自由分析

---

## V2 推送

**只允许推送状态机结果：**
- BET_LOCKED
- WATCH_EARLY
- CANDIDATE
- WATCH_HIGH
- FINAL_RECORD
- ODDS_OUT
- SKIPPED_NO_ACTIVE_WINDOW
- SKIPPED_STARTED_OR_CLOSED
- DONE_BET_LOCKED
- DONE_NO_BET_LOCKED

V2 正式推荐只认 BET_LOCKED。

---

## 群聊

- 群聊只读
- 不得触发 admin
- 不得触发代码修改
- 不得触发 kill/retry
- 不得触发 cron 修改

---

## BOSS 私聊

- 只有 BOSS allowFrom 可以发管理指令
- admin 命令必须只允许 BOSS openid
