# Deprecation Registry

> 建立时间：2026-05-15
> 用途：记录已废弃和当前有效的口径、流程和命令

---

## 已废弃

### 2026-05-15 清理

- **V33** — 全量废弃，任何推送不得引用
- V33 H2H 手工流程
- 皇冠半场盘口流程
- V4 raw scout QQ推送
- V4 dashboard QQ推送
- market_scores 作为正式推荐
- FULLTIME_OVER / SECOND_HALF_OVER 作为 V4最终结论
- V2 HOURLY 全量扫描
- daily_runner.py --run_tag HOURLY
- daily_runner.py --run_tag EARLY_CATCHUP
- daily_runner.py --run_tag EVENING_CATCHUP
- daily_runner.py --run_tag NIGHT_CATCHUP
- 固定 V4简报 cron
- announce 二次总结正式简报
- V4采集-A/B/C三档、V4采集调度、V4预算审计、V4走地监控、V4赔率快照、V4半场结算、V4采集进度报告、V4 Universe缺口修复
- V4采集调度器（may_sprint 走地采集已下线）

---

## 当前有效

### V2 — 半场平局边缘系统
- 正式推荐只认 BET_LOCKED
- 状态机：WATCH_EARLY → CANDIDATE → BET_LOCKED / ODDS_OUT / LOCK_CANCELLED → FINAL_RECORD
- 赔率带：2.00-2.90
- 窗口：T-12h / T-6h / T-3h / T-90m / T-45m / T-15m

### V3 — 世界杯 Perception Gap 战备系统
- 当前 enabled=false
- 战备观察状态

### V4 — 上半场情报系统
- 正式结论只认 A/B/C/SKIP
- 入口：v4_scan_and_brief.py
- 推送：v4_openclaw_brief_qq_YYYYMMDD.txt

### OpenClaw — 系统操作员
- 只执行脚本、检查状态、推送正式报告、标记异常
