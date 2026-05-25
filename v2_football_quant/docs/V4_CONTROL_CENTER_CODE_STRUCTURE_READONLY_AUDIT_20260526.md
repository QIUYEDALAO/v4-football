# V4 Control Center — Code Structure Readonly Audit 20260526

## 最终状态：V4_CONTROL_CENTER_CODE_STRUCTURE_READONLY_AUDIT_PASS

---

## Step 1 — Dashboard 页面清单

| 页面 | 路径 | 文件大小 | Active | 手机可用 | 数据源 | 操作按钮 | 应并入作战台 |
|:-----|:-----|:--------:|:------:|:--------:|:-------|:--------:|:-----------:|
| 情报决策总台 | `index.html` / `intel_desk.html` / `intel_ops_console.html` | 13KB | ✅ | ✅ | scout_v4_, brief_resolution, candidate_view, validation_summary | 无 | ✅ 主页面 |
| V4 实盘记录 | `live_bet_tracker.html` | 19KB | ✅ | ✅ | live_bets jsonl, daily_summary, cumulative_summary | 有(窗口8766 POST) | ✅ 主页面 |
| V4 联赛命中率 | `v4_league_hit_rate.html` | 22KB | ✅ | ✅ | v4_ab_historical_ledger, v4_league_hit_rate_report | 无 | ✅ 抽屉 |
| V4 AB历史复盘 | `v4_ab_historical_ledger.html` | 50KB | ✅ | ❌(偏大) | v4_ab_historical_ledger | 无 | ✅ 抽屉 |
| V3 世界杯情报 | `v3_worldcup_roster_intel.html` | 22KB | ✅ | ✅ | V3 roster | 无 | ❌ V3独立 |
| V4 扫描情报台 | `v4_scan.html` | 2KB | ✅ | ✅ | (占位页) | 无 | ✅ 合并说明 |
| V4 复盘 | `v4_review.html` | 2KB | ✅ | ✅ | (占位页) | 无 | ✅ 合并说明 |
| 系统健康 | `system.html` | 2KB | ✅ | ✅ | (占位页) | 无 | ✅ 抽屉 |
| API缓存 | `api_cache.html` | 2KB | ✅ | ✅ | (占位页) | 无 | ❌ 调试用 |
| intel_desk.html.disabled | (disabled) | 0KB | ❌ | - | - | - | 清理候选 |

### 页面的依赖关系

```
intel_desk.html / index.html / intel_ops_console.html
├── 生成器: tools/generate_intel_desk_html.py
│   ├── 读: scout_v4_{date}.json          → 今日A/B/C/SKIP
│   ├── 读: v3v4_dashboard_brief_resolution_{date}.json
│   ├── 读: v3v4_dashboard_candidate_view_{date}.json
│   ├── 读: v3v4_dashboard_validation_summary_{date}.json (或昨日)
│   ├── 读: v4_script_validation_summary_{date}.json
│   └── 读: v4_match_date_validation_history_recovery.json
├── 刷新器: tools/run_v3v4_dashboard_daily_update.py
│   ├── --phase after-scan (13:00)
│   └── --phase after-validation (13:30)
└── 增强器: tools/intel_ops_display_enhancer.py
    └── 读取 live_bets daily_summary → 注入实盘行

live_bet_tracker.html
├── 服务器: tools/serve_live_bet_tracker.py (8766)
│   ├── 读: data/runtime/live_bets/v4_live_bets_{date}.jsonl
│   ├── 读: data/runtime/live_bets/daily_summary_{date}.json
│   ├── 读: data/runtime/live_bets/cumulative_summary.json
│   ├── 写(POST): /api/live_bets/add
│   ├── 写(POST): /api/live_bets/update
│   ├── 写(POST): /api/live_bets/settle
│   └── 写(POST): /api/live_bets/void
└── 存储层: tools/live_bet_store.py
    ├── 读/写: v4_live_bets_{date}.jsonl
    ├── 读/写: daily_summary_{date}.json
    ├── 读/写: cumulative_summary.json
    └── 读/写: live_bet_tracker_audit.log

v4_ab_historical_ledger.html
├── 生成器: tools/build_v4_ab_historical_ledger.py
│   └── 读: 多日 validation JSONs
└── 50KB 嵌入式 HTML（单文件）

v4_league_hit_rate.html
├── 生成器: tools/build_v4_league_hit_rate_report.py
│   └── 读: v4_ab_historical_ledger
└── 服务器8766 也提供此页
```

---

## Step 2 — API / Server 路由

### serve_dashboard.py（端口 8765）

**类型：纯静态文件服务**
- 模式：只读
- 路由：`GET /{filename}` → 从 `data/runtime/dashboard/` 读取文件
- 无任何 POST / 写入端点
- 无状态，无鉴权

### serve_live_bet_tracker.py（端口 8766）

**类型：混合（静态 + API）**

#### GET 端点（只读）

| 端点 | 返回 | 数据源 |
|:-----|:-----|:-------|
| `GET /live_bet_tracker.html` | HTML页面 | 静态文件 |
| `GET /v4_league_hit_rate.html` | HTML页面 | 静态文件 |
| `GET /api/live_bets?date=YYYYMMDD` | JSON | `v4_live_bets_{date}.jsonl` |
| `GET /api/live_bets/summary?date=YYYYMMDD` | JSON | `daily_summary_{date}.json` |
| `GET /api/live_bets/cumulative` | JSON | `cumulative_summary.json` |
| `GET /api/live_bets/candidates?date=YYYYMMDD` | JSON | `scout_v4_{date}.json` |

#### POST 端点（写入）

| 端点 | 功能 | 写入目标 | 风险等级 |
|:-----|:-----|:---------|:---------|
| `POST /api/live_bets/add` | 记录新投注 | jsonl + summary | 🟡 可操作 |
| `POST /api/live_bets/update` | 修改投注 | jsonl + summary | 🟠 需谨慎 |
| `POST /api/live_bets/settle` | 结算 | jsonl + summary + cumulative | 🟠 不可逆 |
| `POST /api/live_bets/void` | 作废投注 | jsonl + summary | 🟠 需审计 |

### 其他服务

无其他活跃 server。旧 V3 可能曾有 server，当前已无活跃进程。

---

## Step 3 — 核心数据源

| 数据源 | 路径模式 | 数据量 | 更新方式 | 是否自动 |
|:-------|:---------|:------:|:---------|:--------:|
| **今日 A/B/C/SKIP** | `data/daily_reports/scout_v4_{date}.json` | 36K~1.9M | V4 scan 12:00 | ✅ |
| **今日候选视图** | `data/runtime/status/v3v4_dashboard_candidate_view_{date}.json` | ~8K | Dashboard after-scan 13:00 | ✅ |
| **昨日验证** | `data/daily_reports/v4_ht_recommend_validation_{match_date}.json` | 6K~177K | V4 validation dry-run 13:00 | ✅ |
| **Cumulative Truth** | `data/runtime/live_bets/cumulative_summary.json` | ~5K | 结算时写入 | ✅ |
| **AB Ledger** | `data/runtime/status/v4_ab_historical_ledger.json` (或嵌入HTML) | 50K | 生成式 | ✅ |
| **联赛统计** | `v4_league_hit_rate** / v4_ab_historical_ledger` | ~22K | 生成式 | ✅ |
| **实盘每日汇总** | `data/runtime/live_bets/daily_summary_{date}.json` | ~2K | 投注/结算时 | ✅ |
| **实盘明细行** | `data/runtime/live_bets/v4_live_bets_{date}.jsonl` | 1K~5K | API写入 | ✅ |
| **系统健康** | `data/runtime/status/` 各 checker JSON | 各~1K | Crontab | ✅ |
| **QQ通知去重** | `data/runtime/status/qq_notify_done_*.json` | ~0.5K | Crontab 完成后 | ✅ |
| **Cron状态** | `~/.openclaw/cron/jobs.json` | 外部 | Gateway | ✅ |
| **Brief Resolution** | `v3v4_dashboard_brief_resolution_{date}.json` | ~9K | 13:00 解析 | ✅ |
| **Validation Summary** | `v3v4_validation_summary_{date}.json` | ~2K | 13:00 验证 | ✅ |
| **Script Validation** | `v4_script_validation_summary_{date}.json` | ~2K | 13:00 验证 | ✅ |

---

## Step 4 — 可操作功能

| 功能 | 所在页面 | API端点 | 写入目标 | 是否活跃 |
|:-----|:---------|:--------|:---------|:--------:|
| 记录投注 | live_bet_tracker.html | `POST /api/live_bets/add` | jsonl+summary+audit | ✅ |
| 修改投注 | live_bet_tracker.html | `POST /api/live_bets/update` | jsonl+summary+audit | ✅ |
| 结算投注 | live_bet_tracker.html | `POST /api/live_bets/settle` | jsonl+summary+cumulative+audit | ✅ |
| 作废投注 | live_bet_tracker.html | `POST /api/live_bets/void` | jsonl+summary+audit | ✅ |
| 重建summary | store.py rebuild | (CLI) | daily/cumulative | ✅ |
| 补验pending | v4_ht_result_validator.py | (Cron 13:00) | validation | ✅ (自动) |
| 运行checker | 多个 check_*.py | (CLI/Cron) | status JSON | ✅ (自动+手动) |
| QQ测试 | notify/qqbot_safe_send | (CLI) | QQ通道 | ✅ |

### 只读 vs 写入分区

```
只读（浏览器直接打开即可）:
┌─ 情报总台 (13KB)         ← 读 scout + validation + candidate
├─ V4实盘记录 (19KB)       ← 读 jsonl + summary + cumulative
├─ V4联赛命中率 (22KB)     ← 读 ledger
└─ V4 AB历史复盘 (50KB)    ← 读 ledger

需要 server 才能操作:
└─ live_bet_tracker (8766)  ← POST 写入投注数据
```

---

## Step 5 — V4 统一作战台功能矩阵

### 建议布局

```
┌─────────────── 主页面 ───────────────┐
│  V4 统一作战台                          │
│  ┌─ A/B 推荐 ──┬─ 今日候选 ─────────┐  │
│  │ A级 x场      │ 场次 | 联赛 | 评级  │  │
│  │ B级 x场      │ 评分  | 分布 | 样本  │  │
│  │ C级 x场      │ 主因 | 风险         │  │
│  └──────────────┴────────────────────┘  │
│  ┌─ 昨日验证 ──┬─ 滚动统计 ─────────┐  │
│  │ A x/N      │ 近7d | 近30d | 累计  │  │
│  │ B x/N      │ 场次 | 命中率 | ROI   │  │
│  │ SKIP x/N   │ 归因分布              │  │
│  └──────────────┴────────────────────┘  │
│  ┌─ 实盘快照 ─────────────────────────┐  │
│  │ 今日投注 | 未结算 | 盈利/亏损        │  │
│  │ 锁定次数 | 联赛分布                  │  │
│  └────────────────────────────────────┘  │
└─────────────────────────────────────────┘

┌──────── 抽屉（点击展开） ────────────┐
│  ├─ AB历史复盘 (v4_ab_historical_ledger)   │
│  ├─ 联赛命中率 (v4_league_hit_rate)         │
│  ├─ 系统健康检查 (system.html)               │
│  ├─ 定时任务状态 (cron status)               │
│  └─ 实盘操作台 (live_bet_tracker 嵌入)       │
└─────────────────────────────────────────┘
```

### 完整矩阵

| 模块 | 当前来源页面 | 当前代码文件 | 读取数据源 | 写入数据源 | 主页面 | 抽屉 | 锁定 | 风险 |
|:-----|:-----------|:------------|:----------|:----------|:-----:|:----:|:----:|:----:|
| 今日推荐(A/B/C/SKIP) | intel_ops_console | generate_intel_desk_html | scout_v4 | 无 | ✅ | - | - | 🟢 只读 |
| 昨日验证结果 | intel_ops_console | generate_intel_desk_html | v4_ht_recommend_validation | 无 | ✅ | - | - | 🟢 只读 |
| 累计滚动统计 | intel_ops_console | generate_intel_desk_html | cumulative + ledger | 无 | ✅ | - | - | 🟢 只读 |
| 实盘当日快照 | intel_ops_console | intel_ops_display_enhancer | live_bets daily_summary | 无 | ✅ | - | - | 🟢 只读 |
| 候选场次详情 | intel_ops_console | generate_intel_desk_html | candidate_view | 无 | ✅ | - | - | 🟢 只读 |
| AB历史复盘 | v4_ab_hist_ledger.html | build_v4_ab_historical_ledger | 多日validation | 无 | - | ✅ | - | 🟢 只读 |
| 联赛命中率 | v4_league_hit_rate.html | build_v4_league_hit_rate_report | AB ledger | 无 | - | ✅ | - | 🟢 只读 |
| 系统健康 | system.html | (静态) | checker JSONs | 无 | - | ✅ | - | 🟢 只读 |
| 定时任务状态 | (无独立页面) | check_* + cron | cron jobs.json | 无 | - | ✅ | - | 🟢 只读 |
| V3世界杯情报 | v3_worldcup_roster_intel.html | (独立) | V3 roster | 无 | - | - | 🔒 独立 | 🟢 只读 |
| 实盘记录 | live_bet_tracker.html | serve_live_bet_tracker | jsonl+summary | ✅ POST写入 | - | ✅ | 🔒 需server | 🟡 可操作 |
| 结算投注 | live_bet_tracker POST | serve_live_bet_tracker | jsonl+summary+cum | ✅ cumulative | - | - | 🔒 确认窗口 | 🟠 不可逆 |
| 修改/作废投注 | live_bet_tracker POST | serve_live_bet_tracker | jsonl+summary | ✅ jsonl+summary | - | - | 🔒 确认窗口 | 🟠 需审计 |
| QQ通知 | (cron完成时) | notify_cron_task_complete_qq | marker | ✅ QQ通道 | - | - | 🔒 自动 | 🟢 无操作 |
| 补验pending | (cron 13:00) | v4_ht_result_validator | scout+validation | ✅ validation | - | - | 🔒 自动 | 🟢 仅自动 |
| Checker执行 | (手动/自动) | check_*.py | 各数据源 | ✅ status JSON | - | - | ✅ 手动 | 🟢 只读 |

---

## 禁止项确认

```
files_modified:              false
scan_ran:                    false
validation_recomputed:       false
strategy_changed:            false
candidate_changed:           false
QQ_push:                     false
cloud_publish:               false
cron_modified:               false
git_commit:                  false
```

---

## 关键发现

1. **3个重复的"情报总台"页面**: `index.html` / `intel_desk.html` / `intel_ops_console.html` 实际内容相同（13KB），可合并为1个
2. **`v4_scan.html` 和 `v4_review.html` 是占位页**（2KB），无实际内容
3. **`intel_desk.html.disabled`** 残留文件可清理
4. **实盘写入操作全部集中于 8766 server**，没有直接文件写入的 CLI 路径
5. **AB历史复盘50KB** 偏大，手机加载可能慢
6. **无统一鉴权**，8766 的 POST 端点无任何鉴权/确认机制
7. **无统一数据刷新状态指示**，用户不知道数据是否最新
