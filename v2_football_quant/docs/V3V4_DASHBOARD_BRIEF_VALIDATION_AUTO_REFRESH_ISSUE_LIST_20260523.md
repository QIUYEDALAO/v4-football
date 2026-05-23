# V3/V4 Dashboard Brief Validation Auto Refresh Issue List — 20260523

status: PASS
issues_count: 10
phase: V3V4-DASHBOARD-BRIEF-VALIDATION-AUTO-REFRESH-20260523

## 问题清单

1. 验证区重复，昨日 / 近7天 / 累计全部默认展开导致主页面过重。
2. 近7天验证默认展示，不符合移动端轻量展示要求。
3. 今日候选显示旧日期，存在 stale candidate source 风险。
4. 今日正式简报未驱动 dashboard，导致 `v4_openclaw_brief_20260523.txt` 未成为首选源。
5. 简报和验证数据源混用风险：brief 只能用于候选展示，不得用于命中率计算。
6. 需要 brief resolver，按日期读取 `data/daily_reports/v4_openclaw_brief_YYYYMMDD.txt`。
7. 需要 validation resolver，只读取正式 attribution / validation / review 产物。
8. 需要 source_date gate，今日 brief 存在时禁止旧日期冒充今日。
9. 需要 stale data checker，同时检查本地 HTML 与 served HTML。
10. 需要 daily refresh status marker，记录 source_hash / dashboard_sha256 / no capture / no push / no cloud。

## BLOCKER 判定

- 仍允许旧日期显示为今日候选：BLOCKER。
- 今日 brief 存在但 dashboard 仍用旧候选源：BLOCKER。
- brief 被用于命中率计算：BLOCKER。
