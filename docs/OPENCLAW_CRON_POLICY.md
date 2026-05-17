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

## 当前最终调度（20项，2026-05-16 BOSS确认）

| 时间 | 任务 | 脚本 |
|:----|:----|:-----|
| 每3分钟 18:00-11:59 | V4赛中快照 | v4_live_stats_snapshot.py |
| 每小时 05/35分 | V2窗口检查器 | v2_window_checker_with_watchdog.py |
| 01:20 | V4扫描-凌晨 | v4_scan_and_brief.py |
| 07:20 | V4扫描-早场 | v4_scan_and_brief.py |
| 07:35 | V2早场兜底 | v2_window_checker_with_watchdog.py |
| 08:40/17:40/23:40 | SYS-架构审计守卫 | audit + cron policy check |
| 周一 11:20 | V4周报 | v4_weekly_report.py |
| 12:10 | V2每日结算 | v2_settle_with_watchdog.py |
| 12:35 | V4每日复盘 | v4_review_with_watchdog.py |
| 13:00 | SYS每日结算汇总 | 脚本读取V2+V4文件（systemEvent） |
| 13:15 | V2建池-每日 | daily_runner.py --run_tag DAILY_POOL |
| 14:05 | V4扫描-午间 | v4_scan_and_brief.py |
| 14:45 | V4午间最后验收 | (systemEvent) |
| 15:35 | V2每日结算-补跑 | v2_settle_with_watchdog.py |
| 16:20 | V4扫描-傍晚 | v4_scan_and_brief.py |
| 17:25 | 每日状态更新 | (systemEvent) |
| 18:35 | V2晚场兜底 | v2_window_checker_with_watchdog.py |
| 22:20 | V4扫描-晚间 | v4_scan_and_brief.py |
| 23:35 | V2夜间兜底 | v2_window_checker_with_watchdog.py |
| 每月1日 13:20 | V4月报 | v4_monthly_report.py |

---

## 强校验规则

check_cron_policy.py 强校验要求：
- 20项必要任务必须全部存在且名称精确匹配
- 核心时间链路（12:10/12:35/13:00/13:15/14:05）expr精确匹配
- 任何缺失或时间不匹配 → status=FAIL
- 全部 delivery.mode=none
- announce=0
- 禁止命令出现 → BLOCKER

## 中午链路规则

- V2/V4 结算不并发；
- 全部 delivery.mode=none；
- 正式推送只走 systemEvent；
- 不允许 announce；
- 不允许 agentTurn 自由摘要；
- SYS汇总只读正式文件，不自由总结。
- SYS汇总 V4路径：v4_review_qq + v4_review_guard_qq + v4_review_structured（非 v4_openclaw_brief）
- SYS汇总 V2路径：data/paper_trading/verified_{date}.json
- V4扫描简报昨日验证来源：仅限 review_guard PASS 的 review_qq 摘要，不得使用 validation/attribution 全量样本反推

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

## V4每日复盘固定模板纪律

V4每日复盘必须使用固定模板：`templates/v4_daily_review_qq_template.md`

V4每日复盘必须生成：
- `data/daily_reports/v4_review_structured_YYYYMMDD.json`（结构化输入）
- `data/daily_reports/v4_review_qq_YYYYMMDD.txt`（渲染输出）
- `data/runtime/status/v4_review_guard_YYYYMMDD.json`（守卫结果）

流程：
1. 读取正式 brief 确定 A/B/C/SKIP
2. 结构化 JSON
3. API 获取赛果/events
4. renderer.py 推 QQ 文本
5. guard.py 检查
6. guard PASS 后 ClawOps 推送

禁止：
- agentTurn 自由总结
- announce
- ReportAgent 自由改结构
- validation 全量样本反推正式分级

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
- `v4_review_renderer.py`
- `v4_review_guard.py`
- `v4_live_stats_snapshot.py`

---

## V4 链路命名定义

| 概念 | 定义 | cron | template_id |
|:----|:----|:----|:-----------|
| **V4比赛推送** | 当日A/B/C/SKIP简报，来自V4扫描 | V4扫描任务内置 `--push conditional` | v4_scan_brief_qq_v1 |
| **V4结算** | **不是独立cron**，是V4每日复盘12:35内部阶段 | 无独立cron | — |
| **V4复盘** | 赛后归因+剧本验证，可引用V4结算结果 | 12:35 V4每日复盘 | v4_daily_review_qq_v1 |

V4结算内部阶段：
- official_manifest_check：读取 v4_official_samples_{date}.json
- v4_settlement_stage：按official manifest统计命中/未中/命中率/完赛状态
- 不决定样本范围；不使用validation/scout/brief决定样本

---

## V4每日复盘内部状态机（12:35）

1. `official_manifest_check` — 读取 official manifest
2. `v4_settlement_stage` — 按manifest统计结算
3. `readiness_check` — 检查数据准备度
4. `review_render` — full版渲染
5. `qq_summary_render` — QQ摘要版渲染
6. `guard` — 守卫检查
7. `ReportAgent` — 排版审查
8. `safe_outbound` — openclaw message send推送

---

## Safe Outbound 固化

正式推送路径（唯一允许）：

```bash
openclaw message send \
 --channel qqbot \
 --account report \
 --target D1BC6F68CBBAC6A473947C53ECB861EC \
 --message "$(cat <template_file>)"
```

**禁止路径：**
- announce ❌
- agentTurn ❌
- model-call ❌
- wake ❌
- main session ❌
- stdout ❌
- Python relay ❌
- Gateway patch ❌

推送前置条件：
- template registry命中
- renderer输出
- guard PASS
- ReportAgent PASS
- route marker允许

---

## 已知异常

1. **V4扫描-凌晨 01:20** — 上次被 Gateway 重启打断，待下次自然触发验证，不补跑
2. **SYS每日汇总 13:00** — 上次 Message failed（agentTurn路径），当前修复为 openclaw message send 直推，待下次自然触发验证

---

## 明天生产流程

1. cron 自然运行
2. renderer 输出模板文本
3. guard PASS
4. ReportAgent PASS
5. `openclaw message send --channel qqbot --account report`
6. delivery log
7. marker=DELIVERED_UNCONFIRMED
8. 后续自动确认/手动确认后 marker=SENT
