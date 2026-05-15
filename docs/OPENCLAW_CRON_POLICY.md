# OpenClaw Cron Policy

> 建立时间：2026-05-15
> 原则：cron 只触发固定脚本，不做 AI 总结

---

## 原则

- cron 只触发固定脚本
- cron 不做 AI 总结
- cron 不自由分析
- cron 不自由 kill/retry
- cron 输出必须进入 watchdog 或 systemEvent

---

## 当前最终调度

| 时间 | 任务 | 脚本 |
|:----|:----|:-----|
| 每小时 05/35 | V2窗口检查器 | v2_window_checker_with_watchdog.py |
| 每3分钟 18-11 | V4赛中快照 | v4_live_stats_snapshot.py |
| 01:20 | V4扫描-凌晨 | v4_scan_and_brief.py |
| 07:20 | V4扫描-早场 | v4_scan_and_brief.py |
| 07:35 | V2早场兜底 | v2_window_checker_with_watchdog.py |
| 12:10 | V2每日结算 | v2_settle_with_watchdog.py |
| 12:35 | V4每日复盘 | v4_review_with_watchdog.py |
| 13:00 | SYS每日结算汇总 | V2+V4文件完整性检查（systemEvent） |
| 13:15 | V2建池-每日 | daily_runner.py --run_tag DAILY_POOL |
| 14:05 | V4扫描-午间 | v4_scan_and_brief.py |
| 15:35 | V2结算补跑 | v2_settle_with_watchdog.py |
| 16:20 | V4扫描-傍晚 | v4_scan_and_brief.py |
| 17:25 | 每日状态更新 | (systemEvent) |
| 18:35 | V2晚场兜底 | v2_window_checker_with_watchdog.py |
| 22:20 | V4扫描-晚间 | v4_scan_and_brief.py |
| 23:35 | V2夜间兜底 | v2_window_checker_with_watchdog.py |
| 周一 11:20 | V4周报 | v4_weekly_report.py |
| 08:40/17:40/23:40 | SYS-架构审计守卫 | audit + cron policy check |
| 每月1日 13:20 | V4月报 | v4_monthly_report.py |

---

## 中午链路规则

- V2/V4 结算不并发；
- 全部 delivery.mode=none；
- 正式推送只走 systemEvent；
- 不允许 announce；
- 不允许 agentTurn 自由摘要；
- SYS汇总只读正式文件，不自由总结。

---

## Timeout 规则

| 任务类型 | 外层 cron timeout | supervisor hard timeout |
|:---------|:-----------------:|:----------------------:|
| V4 扫描 | 4500s | 3600s |
| V2 窗口检查器 | 480s | 900s |
| V2 结算 | 2700s | — |
| V4 复盘 | 1200s | — |
| V4 快照 | 60s | 120s |
| V2 建池 | 1200s | — |

---

## 禁止命令

**禁止在 cron 中出现的命令：**
- `daily_runner.py --run_tag HOURLY`
- `daily_runner.py --run_tag EARLY_CATCHUP`
- `daily_runner.py --run_tag EVENING_CATCHUP`
- `daily_runner.py --run_tag NIGHT_CATCHUP`
- `v4_runner.py` 直跑推送
- `v4_dashboard.py` 直跑推送
- 固定 V4简报 cron
- announce 二次加工正式报告

**允许在 cron 中出现的命令：**
- `v2_window_checker_with_watchdog.py`
- `v2_settle_with_watchdog.py`
- `daily_runner.py --run_tag DAILY_POOL`
- `v4_scan_and_brief.py`
- `v4_review_with_watchdog.py`
- `v4_live_stats_snapshot.py`
