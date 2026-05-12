# V4 足球走地半场大球策略系统 — 项目说明书 v4.0

> 日期：2026-05-12  
> 代码规模：**15,054 行 Python / 65 个模块**  
> 策略代号：`V4_HT_LIVE_PULLBACK`  
> 状态：纸盘验证期 — 全流水线闭环运行

---

## 一、项目概述

V4 是一个基于 API-Football 实时数据的足球半场大球走地策略系统。核心逻辑：**赛前筛选高概率进球比赛进入候选池，赛中等待盘口自然衰减至合理区间后进场，赛后自动结算并复盘。**

### 1.1 策略核心假设

赛前半场大球盘口往往高估"强队开场就能进球"的概率。当比赛前 10 分钟未进球时，盘口迅速从大 1.25/1.5 降到大 1.0/0.75，而实际进球概率衰减速度远慢于盘口价格下降速度。策略赚取的是这个**时间衰减溢价**。

### 1.2 与 V2/V3 的关系

| 系统 | 策略 | 市场 | 状态 |
|:---|:---|:---|:---|
| V2 | HT 1X2 平局错杀 | 半场胜平负 | 纸盘验证中 |
| V3 | Elo + Perception Gap | 亚盘套利 | 待世界杯激活 |
| V4 | 半场大球走地回调 | 亚洲大小球 | 纸盘观察期 |

三个系统完全独立运行，互不干扰。

---

## 二、系统架构

### 2.1 总体架构图

```
                           V4 Master Run (一键总控)
                                   │
        ┌──────────────┬───────────┼───────────┬──────────────┐
        ▼              ▼           ▼           ▼              ▼
   赛前建池       T-30闸门     走地监控     半场结算       复盘评估
   v4_runner    lineup引擎   live_monitor  ht_verifier   review+eval
        │              │           │           │              │
        ▼              ▼           ▼           ▼              ▼
   scout_v4      BOOST/DROP   BUY_NOW      WIN/LOSS     策略报告
   +dashboard                +SKIP         +PUSH         +Kill评估
   +live_watchlist
```

### 2.2 完整流水线

| 阶段 | 时间 | 动作 | 核心脚本 |
|:---|:---|:---|:---|
| 建池 | 12:00 | 全量扫描，建立候选池 | `v4_runner.py` |
| 刷新 | 17:00 | 更新赔率/伤停/排名 | `v4_runner.py` |
| 首发闸门 | T-30 | BOOST/KEEP/DROP | `v4_runner --with-lineups` |
| 走地监控 | 0-15min | 等盘口衰减后进场 | `live_ht_over_monitor.py` |
| 下半场评估 | 45min | SH独立评估 | `second_half_evaluator.py` |
| 实时结算 | 半场后 | 亚洲盘自动结算 | `v4_ht_result_verifier.py` |
| 完整复盘 | 次日 | 全维度复盘+策略评估 | `v4_master_run.py --phase reports --offline` |

### 2.3 三模式仪表盘

| 模式 | 用途 | 默认 |
|:---|:---|:---:|
| **临场作战** | 赛中实时：四分区分组+监控指标+动作卡片 | ✅ 默认 |
| **复盘模式** | 赛后分析：HT命中率/盘口衰减/跳过原因 | 手动切换 |
| **研究模式** | 深度探索：分联赛/分时段/分盘口多维切片 | 手动切换 |

---

## 三、模块全览（65个模块 / 15,054行）

### 3.1 核心扫描与画像（8个）

| 模块 | 行数 | 功能 |
|:---|:---:|:---|
| `v4_runner.py` | — | 主扫描器（fast/full双模式+prewarm可配+性能摘要） |
| `data_sources/h2h_engine.py` | — | H2H多维画像（HT/SH/FT三向评分+回调适配+攻防交叉） |
| `data_sources/lineup_strength.py` | — | 首发强度识别（攻击/中场/防守核心拆分） |
| `data_sources/api_coverage.py` | — | API数据覆盖闸门（FULL/GOOD/BASIC/WEAK） |
| `data_sources/league_baseline.py` | — | 联赛HT/SH/FT基准（FRIENDLY/NEUTRAL/COLD） |
| `data_sources/season_phase.py` | — | 赛季阶段（EARLY/MID/LATE/FINAL_ROUND） |
| `data_sources/motivation.py` | — | 排名战意过滤（保级/争冠/中游安全区） |
| `data_sources/schedule_pressure.py` | — | 赛程压力（未来7/10天密度） |

### 3.2 走地与盘中（6个）

| 模块 | 功能 |
|:---|:---|
| `live_ht_over_monitor.py` | 上半场走地监控（0-10min等降盘→BUY_NOW/SKIP） |
| `live_odds_snapshot.py` | 赔率衰减时间线快照库 |
| `second_half_evaluator.py` | 下半场独立评估（SH_BUY_NOW/SH_SKIP） |
| `data_sources/live_tempo.py` | 赛中节奏判断（射门/角球/危险进攻/红牌） |
| `odds_io_adapter.py` | Sbobet/Bet365全场盘口适配器 |
| `odds_monitor.py` | 赔率监控基础模块 |

### 3.3 结算与评估（8个）

| 模块 | 功能 |
|:---|:---|
| `asian_over_settlement.py` | 亚洲盘结算（WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS） |
| `v4_ht_result_verifier.py` | 半场自动回填（API状态码轮询） |
| `v4_sh_result_verifier.py` | 下半场独立结算 |
| `paper_trading.py` | V2/V4统一纸盘结算框架 |
| `v4_review_report.py` | 每日复盘报告（JSON+MD） |
| `v4_strategy_eval.py` | V4策略评估（满50场后） |
| `v4_sh_strategy_eval.py` | 下半场独立策略评估 |
| `v4_calibration_report.py` | 校准报告 |

### 3.4 量化模型（6个）

| 模块 | 功能 |
|:---|:---|
| `ht_goal_hazard_model.py` | 分钟进球概率模型 |
| `asian_ev.py` | 亚洲盘EV计算 |
| `line_decay_model.py` | 盘口衰减曲线模型 |
| `execution_cost_model.py` | 三套ROI（纸盘/理论/实盘含滑点） |
| `league_hierarchical_threshold.py` | 联赛分层阈值 |
| `walk_forward_backtest.py` | Walk-forward回测 |

### 3.5 风控与数据（8个）

| 模块 | 功能 |
|:---|:---|
| `bankroll.py` | Kelly仓位管理（1/4+阶梯熔断） |
| `risk_guard.py` | Risk Guard |
| `live_bridge.py` | 纸盘→实盘网关（三级准入+Kill-Switch） |
| `v4_data_logger.py` | 统一数据日志 |
| `strategy_candidates_tracker.py` | 候选策略追踪 |
| `context_enrichment.py` | 天气/场地/裁判采集 |
| `context_marginal_report.py` | 边际效应报告 |
| `fd_history_to_candidates.py` | football-data.co.uk历史数据转换 |

### 3.6 仪表盘与报告（6个）

| 模块 | 功能 |
|:---|:---|
| `v4_dashboard.py` | 三模式交互仪表盘（作战/复盘/研究） |
| `v4_scout_report.py` | 终端情报卡片（S/A/B级+红绿灯） |
| `v4_match_intelligence.py` | 智能比赛解释器 |
| `v4_report.py` | 兼容旧格式报表 |
| `v4_master_run.py` | 一键总控（full/reports/offline） |
| `v4_versioning.py` | 版本管理 |

### 3.7 工具与基础（23个）

`aligner.py`, `clv.py`, `daily_runner.py`, `fetcher.py`, `logger.py`, `net_utils.py`, `team_cn_map.py`, `team_cn_missing_collector.py`, `v4_release_freeze.py`, `wc_model.py`, `strategy_router.py`, `scoring_engine_v0.py`, `backtest_pipeline_v0.py`, `league_replay_tiers.py`, `data_pipeline/ingest_football_data_history.py` 等

---

## 四、数据采集管线

### 4.1 主数据源

**API-Football Pro**（7,500次/天）提供全部实时数据。补充数据源：`football-data.co.uk`（31赛季免费历史数据）、`odds-api.io`（Sbobet全场盘口）。

### 4.2 核心数据维度

| 维度 | 内容 |
|:---|:---|
| H2H画像 | HT/SH/FT进球率+场均进球+时间分桶+回调适配 |
| 近期动能 | 近5场HT/SH/FT攻防交叉+进球/失球动能 |
| 联赛基准 | 各联赛HT/SH/FT环境（FRIENDLY/NEUTRAL/COLD） |
| 赛季阶段 | EARLY/MID/LATE/FINAL_ROUND |
| 战意 | 保级/争冠/欧战/升级/中游安全区 |
| 赛程压力 | 未来7/10天比赛密度 |
| 首发阵容 | 攻击/中场/防守核心完整度 |
| 赔率 | 赛前Pinnacle半场大小球全量线+赛中走地快照 |
| 赛中节奏 | 射门/射正/角球/危险进攻/红牌 |

### 4.3 关键规则

- H2H时间红线：仅采集2020年及以后的交锋
- 样本底线：2020+至少3场H2H
- 扫描窗口：今天+明天全部56个白名单联赛
- 性能优化：fast模式+按需加载+API缓存（40场/336秒/140次调用）

---

## 五、策略执行规则

### 5.1 三方向评分

| 方向 | 用途 | 策略归属 |
|:---|:---|:---:|
| HT_LIVE_OVER | 上半场走地回调 | ✅ 主策略，可进场 |
| SECOND_HALF_OVER | 下半场大球参考 | ❌ 仅观察 |
| FULLTIME_OVER | 全场大球参考 | ❌ 仅观察 |

### 5.2 候选池门槛

- 近期HT攻防动能 ≥ 70%
- HT走地评分 ≥ 50，且为最强方向
- 半场大球盘口 ≥ 大1.25
- API数据覆盖 ≥ GOOD

### 5.3 走地进场窗口

```
0-10分钟 有进球 → SKIP_EARLY_GOAL
0-10分钟 0-0   → 继续观察
8-15分钟 0-0 + 盘口降到大1.0/0.75 + 水位合理 + 节奏不沉闷 → BUY_NOW
15分钟后 未达到 → SKIP_WINDOW_CLOSED
```

---

## 六、漏斗指标与评估

### 6.1 全链路漏斗

```
候选池 → 走地监控 → 等到降盘 → 节奏合格 → 进场 → HT命中 → 亚洲盘ROI
         ↓           ↓           ↓
      跳过数      进球跳过     节奏跳过
```

### 6.2 样本量阶段

| 阶段 | 样本量 | 目的 |
|:---|:---:|:---|
| 纸盘观察期 | 50场 | 检查逻辑错误 |
| 小样本校准 | 100场 | 初步命中率/进场率 |
| 有效评估 | 300场 | 判断策略正期望 |
| 分联赛优化 | 500+场 | 独立阈值调整 |

---

## 七、性能数据（2026-05-12 实测）

| 指标 | 初始版 | 优化后 | 提升 |
|:---|:---:|:---:|:---:|
| 扫描耗时 | 超时(>900s) | **336秒** | 稳定可生产 |
| API调用 | 473次 | **140次** | -70% |
| 单场平均 | ~12s | **3.6s** | -70% |
| 产出 | 无 | 18情报+仪表盘 | ✅ |

---

## 八、技术栈

| 组件 | 选型 |
|:---|:---|
| 语言 | Python 3.9+ |
| 数据源 | API-Football Pro + football-data.co.uk + odds-api.io |
| 存储 | JSON文件系统 |
| 仪表盘 | 纯HTML/CSS/JS（三模式，无框架依赖） |
| 调度 | Cron (OpenClaw Gateway) |
| 版本控制 | Git + GitHub |
| 代码规模 | 15,054行 / 65模块 |

---

## 九、文件结构

```
v2_football_quant/
├── engine/                          51个模块
│   ├── v4_runner.py                 ← 主扫描器
│   ├── v4_dashboard.py              ← 三模式仪表盘
│   ├── v4_master_run.py             ← 一键总控
│   ├── live_ht_over_monitor.py      ← 走地监控
│   ├── second_half_evaluator.py     ← 下半场评估
│   ├── asian_over_settlement.py     ← 亚洲盘结算
│   ├── ht_goal_hazard_model.py      ← 分钟概率模型
│   ├── line_decay_model.py          ← 盘口衰减模型
│   ├── walk_forward_backtest.py     ← Walk-forward回测
│   └── data_sources/               14个数据引擎
├── docs/
│   ├── PROJECT_BOOK_V4.md           ← 本项目说明书
│   ├── V4_STRATEGY_RULES.md         ← 策略规则（28章）
│   └── V4_KEY_REQUIRED_TASKS.md     ← 运行任务清单
├── config/
│   ├── leagues_whitelist.json       ← 56联赛白名单
│   └── kill_criteria.yaml           ← 策略Kill Criteria
└── data/
    ├── daily_reports/               ← 球探快照+性能摘要
    ├── paper_trading/               ← 纸盘结算
    └── live_odds_snapshots/         ← 赔率快照库
```

---

## 十、生产命令

```bash
# 赛前扫描（生产默认参数）
python3 engine/v4_runner.py --scan-mode fast --lookahead-hours 24 --recent-prewarm off

# 交互仪表盘
python3 engine/v4_dashboard.py --date 20260512

# 走地监控循环
python3 engine/live_ht_over_monitor.py --date 20260512 --watch --interval 30

# 半场自动结算
python3 engine/v4_ht_result_verifier.py --date 20260512 --watch --interval 300

# 完整复盘报告
python3 engine/v4_master_run.py --date 20260512 --phase reports --offline
```

---

> 📌 **核心设计理念**：不在赛前预测谁会进球，在赛中等待盘口犯错。用时间换价格，用纪律换盈亏比。

> 📊 **当前状态**：65模块/15K行代码，全流水线闭环，40场336秒稳定产出。待300场样本验证策略正期望。
