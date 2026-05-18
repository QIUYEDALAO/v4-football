# STATE_CURRENT.md — 当前运行状态

> 本文件只记录短期状态，每天覆盖更新。长期原则以 MEMORY.md 为准。
> 不写入 API Key/Token/密钥。冲突时以当前代码和最新报告为准。

---

## 📋 2026-05-18 日间状态（17:25 CST）

### V2
- DAILY_POOL(20260518): ❌ **未运行** — 上次成功 20260517 14:23
  - P0 marker 已写入 `data/runtime/status/P0_DAILY_POOL_MISSING_20260518.json`
  - 发生时分支 codex/phase-c-api-snapshot-cache，现已合并 main
- DAILY_SETTLE(20260518): ✅ DONE（20260517 赛后验证）
  - 无 BET_LOCKED 可结算
- V2 窗口检查器: 未触发（无 pool 源）

### V4扫描 — 今日窗口
| 窗口 | 时间 | 扫描场次 | Scout | A/B/C | SKIP | 备注 |
|:----|:----:|:--------:|:-----:|:-----:|:----:|:-----|
| 凌晨 | — | — | — | — | — | 未触发 |
| 早场 | — | — | — | — | — | 未触发 |
| 🌤 午间 | 14:05 | 24 | 7 | 0/0/0 | **7** | 全部SKIP |
| 🌆 傍晚 | 16:26 | 25 | 7 | 0/0/0 | **7** | 全部SKIP，简报已生成 |
| 晚间 | — | — | — | — | — | 待触发 |

SKIP 原因：H2H HT率 0.4~0.7，未达 0.8 阈值。
今日 **无 A/B 级推荐**，**无主推荐**。

### V4复盘（20260517）
- 复盘于 13:44 自动触发 ✅
- route 状态: `guard BLOCKER (BLOCKER)` — route 被拦截
- push 状态: `NOT_SENT` — 未推 QQ
- 复盘已完成但 guard 未通过，等 BOSS 确认

### V4简报
- 傍晚窗口简报已生成（v4_openclaw_brief_qq_20260518.txt）
- 标记为 TEST（非正式推送）
- 当前未推 QQ，未接 cron

### 系统状态
- 当前分支: `main` ✅
- **Phase C 已合并 main** ✅ — merge commit: `0c91fe0`
- STATE_CURRENT restore commit: `be18d61`
- Phase C.4.1 Real Ingest Smoke: ✅ PASS（1次status endpoint）
- Phase A/B 已合并 main ✅
- stash remainder 已隔离 ✅ — STATE_CURRENT.md 不再在 stash
  - v4_review_with_watchdog.py：保留在 remainder stash，建议 Phase F 处理
  - Excel：保留在 remainder stash，等待人工判断
- 生产验证: ❌ PRODUCTION_VERIFIED = false
- PIPELINE_READY: ❌ false
- V2/V4 正式链路未接 cache
- QQ 未接 cache
- cron 未接 cache（仅 */2 pre_match_reminder 活跃）
- 推 QQ: ❌ 否
- 未进入 Phase D
- 未进入 Phase F
- 当前等级: **CODE_READY**
