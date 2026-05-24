# V3/V4 Dashboard Auto Refresh Cron Schedule Rebase — Issue List

**Phase:** V3V4-DASHBOARD-AUTO-REFRESH-CRON-ENABLE-PRECHECK-SCHEDULE-REBASE-20260524
**Generated:** 2026-05-24 10:27 CST

## Issues

| # | Issue | Status |
|:-:|:------|:------:|
| 1 | 12:00 V4_DAILY_SCAN_READONLY 必须明确纳入调度验收 | ✅ acknowledged |
| 2 | 13:00 after-scan 只更新比赛推荐，不碰验证区 | ✅ acknowledged |
| 3 | 13:00 validation dry-run 启动赛后验证 | ✅ acknowledged |
| 4 | 13:30 after-validation 第一次更新验证 | ✅ acknowledged |
| 5 | 14:00 after-validation final 补刷验证 | ✅ acknowledged |
| 6 | 14:00 不能重新跑 scan | ✅ acknowledged |
| 7 | 14:00 不能重新跑 validation | ✅ acknowledged |
| 8 | 14:00 source_hash 未变必须 NOOP | ✅ acknowledged |
| 9 | cron 本轮只 precheck，不启用 | ✅ acknowledged |
| 10 | checker 必须拦截漏掉 12:00 或 14:00 的计划 | ✅ acknowledged |

## Gap Found

**Runner `--final-pass` flag missing:**
- `tools/run_v3v4_dashboard_daily_update.py` 当前不支持 `--final-pass` 参数
- 14:00 补刷任务需要该参数来确保：不重新跑 validation、source_hash 未变时 NOOP
- 标记 `code_change_required=true`

## Conclusion

```
ISSUE_LIST_COMPLETE
```
