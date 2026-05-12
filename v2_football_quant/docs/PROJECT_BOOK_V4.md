# V4 走地半场大球策略系统 — 项目说明书 v3.2.1 冻结版

> 版本：v3.2.1  
> 冻结日期：2026-05-12  
> 代码规模：15,054 行 / 65 模块  
> 策略代号：`V4_HT_LIVE_PULLBACK`  
> 状态：纸盘验证期，全流水线闭环运行

---

## 一、项目概述

V4 是一个基于 API-Football 实时数据的足球半场大球走地策略系统。核心逻辑：**赛前筛选高概率进球比赛进入候选池，赛中等待盘口自然衰减至合理区间后进场，赛后自动结算并复盘。**

### 1.1 策略核心假设

赛前半场大球盘口往往高估"强队开场就能进球"的概率。当比赛前 10 分钟未进球时，盘口迅速从大 1.25/1.5 降到大 1.0/0.75，而实际进球概率衰减速度远慢于盘口价格下降速度。策略赚取的是这个**时间衰减溢价**。

### 1.2 EV 驱动决策链（v3.2.1 核心升级）

v3.2.1 从"规则引擎"升级为"EV 联合决策"：

```
ht_goal_hazard_model.py  → 输出 P0 / P1 / P2plus（分钟级进球概率）
line_decay_model.py      → 输出 market_prob / edge（盘口衰减后公平概率）
asian_ev.py              → 计算 EV_gross（亚洲盘毛期望值）
execution_cost_model.py  → 扣除滑点/流动性 → EV_net
risk_guard.py            → 校验风险（联赛COLD/赛程压力/赛季末中游）
                         ↓
              PAPER_BUY_NOW / PAPER_ONLY / SKIP
```

**old legacy rule 仅作为基线对照**，不参与最终入场决策。

### 1.3 与 V2/V3 的关系

| 系统 | 策略 | 市场 | 状态 |
|:---|:---|:---|:---|
| V2 | HT 1X2 平局错杀 | 半场胜平负 | 纸盘验证中 |
| V3 | Elo + Perception Gap | 亚盘套利 | 待世界杯激活 |
| V4 | 半场大球走地回调 | 亚洲大小球 | 纸盘观察期 |

三个系统完全独立运行，互不干扰。

---

## 二、系统架构

### 2.1 总体架构

```
                           V4 Master Run (一键总控)
                                   │
        ┌──────────────┬───────────┼───────────┬──────────────┐
        ▼              ▼           ▼           ▼              ▼
   赛前建池       T-30闸门     走地监控     半场结算       复盘评估
   v4_runner    lineup引擎   EV决策链    ht_verifier   review+eval
        │              │           │           │              │
        ▼              ▼           ▼           ▼              ▼
   scout_v4.json  BOOST/DROP  PAPER_BUY   WIN/LOSS    walk_forward
   +dashboard     +KEEP       _NOW/SKIP   +PUSH        +kill_audit
   +live_watchlist
```

### 2.2 完整流水线

| 阶段 | 时间 | 动作 | 核心脚本 |
|:---|:---|:---|:---|
| 建池 | 12:00 | 全量扫描 | `v4_runner.py --scan-mode fast` |
| 刷新 | 17:00 | 更新赔率/伤停/排名 | `v4_runner.py` |
| 首发闸门 | T-30 | 阵容复核 | `v4_runner --with-lineups` |
| 走地监控 | 0-15min | EV决策链 → PAPER_BUY_NOW | `live_ht_over_monitor.py` |
| 下半场评估 | 45min | SH独立评估 | `second_half_evaluator.py` |
| 实时结算 | 半场后 | 亚洲盘自动结算 | `v4_ht_result_verifier.py` |
| 完整复盘 | 次日 | Walk-forward回测+模型校准 | `v4_master_run.py --phase reports --offline` |

### 2.3 仪表盘信息架构（v3.2.1 极简版）

| 模式 | 用途 | 展示内容 |
|:---|:---|:---|
| **临场作战** | 赛中实时 | 四分区（可进场/等待触发/风险观察/已跳过）+ 监控数字 |
| **复盘模式** | 赛后分析 | HT命中率 / 盘口衰减时间线 / 跳过原因分布 |
| **研究模式** | 深度探索 | 分联赛×分时段×分盘口多维切片 |

**极简原则**：
- 默认只展示 A+ / A / WAIT
- 单场卡片最多 8 个核心字段（动作、等级、盘口、EV标签、执行标签、窗口、主因Top3、风险Top2）
- 复杂参数全部折叠到研究模式
- HT主策略与SH观察策略分 Tab
- 输出动作统一：`PAPER_BUY_NOW / WAIT_LINE / WAIT_TEMPO / PAPER_ONLY / SKIP / RISK_BLOCKED`

---

## 三、模块全览

### 3.1 主策略链路（6个）

| 模块 | 功能 |
|:---|:---|
| `ht_goal_hazard_model.py` | 分钟级进球概率模型，输出 P0/P1/P2plus |
| `line_decay_model.py` | 盘口衰减曲线，输出 market_prob / edge |
| `asian_ev.py` | 亚洲盘 EV_gross 计算 |
| `execution_cost_model.py` | 扣除滑点/流动性，输出 EV_net + execution_quality |
| `risk_guard.py` | 联赛COLD/赛程HIGH/赛季末中游拦截 |
| `walk_forward_backtest.py` | Walk-forward 滚动回测 |

### 3.2 数据采集引擎（7个）

| 模块 | 功能 |
|:---|:---|
| `data_sources/h2h_engine.py` | H2H 多维画像（HT/SH/FT 三向评分+回调适配） |
| `data_sources/lineup_strength.py` | 首发强度（攻击/中场/防守核心拆分） |
| `data_sources/api_coverage.py` | 数据覆盖闸门（FULL/GOOD/BASIC/WEAK） |
| `data_sources/league_baseline.py` | 联赛基准（FRIENDLY/NEUTRAL/COLD） |
| `data_sources/season_phase.py` | 赛季阶段（EARLY/MID/LATE/FINAL_ROUND） |
| `data_sources/motivation.py` | 战意过滤（保级/争冠/中游安全区） |
| `data_sources/schedule_pressure.py` | 赛程压力（7/10天密度） |

### 3.3 走地与盘中（6个）

| 模块 | 功能 |
|:---|:---|
| `live_ht_over_monitor.py` | 上半场走地监控 |
| `live_odds_snapshot.py` | 赔率衰减时间线快照库 |
| `second_half_evaluator.py` | 下半场独立评估 |
| `data_sources/live_tempo.py` | 赛中节奏判断 |
| `odds_io_adapter.py` | Sbobet全场盘口适配器 |
| `odds_monitor.py` | 赔率监控基础模块 |

### 3.4 结算与评估（8个）

| 模块 | 功能 |
|:---|:---|
| `asian_over_settlement.py` | 亚洲盘结算 |
| `v4_ht_result_verifier.py` | 半场自动回填 |
| `v4_sh_result_verifier.py` | 下半场独立结算 |
| `paper_trading.py` | V2/V4统一纸盘框架 |
| `v4_review_report.py` | 每日复盘报告 |
| `v4_strategy_eval.py` | V4策略评估 |
| `v4_sh_strategy_eval.py` | SH独立评估 |
| `v4_calibration_report.py` | EV分桶校准报告 |

### 3.5 P0 数据闭环（7个）

| 模块/目录 | 功能 |
|:---|:---|
| `data/universe/` | 全量比赛池（不遗漏任何可评估场次） |
| `data/decision_logs/` | 决策日志（为什么PAPER_BUY_NOW/为什么SKIP） |
| `data/shadow_backtest/` | 影子回测（legacy rule对照EV链） |
| `data/execution/` | 执行成本模拟 |
| `data/model_versions/` | 模型版本登记 |
| `data/calibration/` | EV分桶校准 |
| `data/walk_forward/` | Walk-forward滚动窗口 |
| `data/kill_audit/` | Kill Criteria审计日志 |

### 3.6 仪表盘与总控（6个）

| 模块 | 功能 |
|:---|:---|
| `v4_dashboard.py` | 三模式交互仪表盘（作战/复盘/研究） |
| `v4_scout_report.py` | 终端情报卡片（S/A/B级+红绿灯） |
| `v4_match_intelligence.py` | 智能比赛解释器 |
| `v4_master_run.py` | 一键总控 |
| `v4_data_logger.py` | 统一数据日志 |
| `v4_release_freeze.py` | 发布冻结管理 |

### 3.7 基础与工具（25+个）

`bankroll.py`, `clv.py`, `daily_runner.py`, `strategy_router.py`, `scoring_engine_v0.py`, `aligner.py`, `fetcher.py`, `net_utils.py`, `team_cn_map.py`, `context_enrichment.py`, `context_marginal_report.py`, `fd_history_to_candidates.py`, `league_hierarchical_threshold.py`, `league_replay_tiers.py`, `live_bridge.py`, `risk_guard.py`, `strategy_candidates_tracker.py`, `v4_versioning.py`, `wc_model.py`, 等

---

## 四、数据采集管线

### 4.1 数据源

| 数据源 | 用途 | 覆盖 |
|:---|:---|:---|
| **API-Football Pro** | 实时赛程、事件、阵容、赛中统计、走地赔率轮询 | 7,500次/天 |
| **football-data.co.uk** | 历史赛果、HT/FT比分、赛前/收盘赔率基准 | 31赛季免费 |
| **Betfair/自采live odds** | 盘口衰减曲线训练（分钟级走地tick） | 待接入 |

> 注意：football-data.co.uk 提供赛前/终盘数据，**不提供分钟级走地盘口**。衰减曲线训练需要独立走地数据源。

### 4.2 核心采集维度

| 维度 | 内容 |
|:---|:---|
| H2H画像 | HT/SH/FT进球率+场均进球+时间分桶+回调适配 |
| 近期动能 | 近5场HT/SH/FT攻防交叉+进球/失球统计 |
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
- 性能：fast模式+按需加载+API缓存（40场/336秒/140次调用）

---

## 五、EV 决策链（v3.2.1 核心）

### 5.1 三方向评分

| 方向 | 用途 | 策略归属 |
|:---|:---|:---:|
| HT_LIVE_OVER | 上半场走地回调 | ✅ 主策略 |
| SECOND_HALF_OVER | 下半场大球参考 | ❌ 仅观察 |
| FULLTIME_OVER | 全场大球参考 | ❌ 仅观察 |

### 5.2 候选池门槛

- HT走地评分 ≥ 50，且为最强方向
- 半场大球盘口 ≥ 大1.25
- API数据覆盖 ≥ GOOD

### 5.3 EV 联合决策链

```
赛中实时数据
  │
  ├─ ht_goal_hazard_model.py → P0 / P1 / P2plus
  │     剩余时间 × 进球率 → 条件进球概率
  │
  ├─ line_decay_model.py → market_prob / edge
  │     盘口衰减后公平概率
  │
  ├─ asian_ev.py → EV_gross
  │     EV_gross = P(win) × 赢额 + P(half) × 半额 + P(loss) × (-1)
  │
  ├─ execution_cost_model.py → EV_net
  │     扣除滑点估计(0.02-0.05) + 流动性折扣
  │
  ├─ risk_guard.py → PASS / BLOCK
  │     联赛COLD / 赛程HIGH / 赛季末中游
  │
  └─ 最终输出
       EV_net > min_ev_threshold → PAPER_BUY_NOW
       EV_net ≤ threshold      → PAPER_ONLY (纸盘记录，不推荐)
       风险拦截                 → SKIP / RISK_BLOCKED
```

### 5.4 动作标签（统一）

| 动作 | 含义 |
|:---|:---|
| **PAPER_BUY_NOW** | EV_net > 阈值，纸盘推荐进场 |
| **WAIT_LINE** | 盘口还未降到目标线 |
| **WAIT_TEMPO** | 节奏数据未达标 |
| **PAPER_ONLY** | 纸盘记录（EV_net 不足但可观察） |
| **SKIP** | 不满足进场条件 |
| **RISK_BLOCKED** | 风险守卫拦截 |

### 5.5 legacy rule 边界

旧规则引擎（"盘口降到大1.0+水位合理+节奏OK→BUY_NOW"）仅作为**基线对照组**保存在 `data/shadow_backtest/` 中，不参与最终入场决策。v3.2.1 只以 EV_net > min_ev_threshold 作为唯一入场标准。

---

## 六、漏斗指标与评估

### 6.1 全链路漏斗

```
候选池 → 走地监控 → 等到降盘 → 节奏合格 → EV_net > 阈值 → PAPER_BUY_NOW → HT命中 → 亚洲盘ROI
         ↓           ↓           ↓           ↓
       跳过       进球跳过    节奏跳过    PAPER_ONLY
```

### 6.2 样本量阶段

| 阶段 | 样本量 | 目的 |
|:---|:---:|:---|
| 纸盘观察期 | 50场 | 检查逻辑错误 |
| 小样本校准 | 100场 | 初步命中率/进场率/EV校准 |
| 有效评估 | 300场 | 判断策略正期望 |
| 分联赛优化 | 500+场 | 独立阈值调整 |

### 6.3 Kill Criteria

```yaml
# config/kill_criteria.yaml
triggers:
  - sharpe_ratio < -1.0 over last_50_trades
  - consecutive_losses >= 8
  - ev_net_mean < -0.03 over last_100_trades
  - walk_forward_calibration_fails >= 2
```

---

## 七、性能数据（2026-05-12 实测）

| 指标 | 初始版 | 优化后 | 提升 |
|:---|:---:|:---:|:---:|
| 扫描耗时 | 超时(>900s) | **336秒** | 稳定可生产 |
| API调用 | 473次 | **140次** | -70% |
| 单场平均 | ~12s | **3.6s** | -70% |
| 预热模式 | 预热ON: 345s | **默认OFF: 336s** | 更快 |

---

## 八、技术栈

| 组件 | 选型 |
|:---|:---|
| 语言 | Python 3.9+ |
| 实时数据 | API-Football Pro（7,500次/天） |
| 历史数据 | football-data.co.uk（31赛季免费CSV） |
| 走地盘口训练 | Betfair历史/自采live odds |
| 存储 | JSON文件系统（P0八层闭环） |
| 仪表盘 | 纯HTML/CSS/JS（三模式，无框架依赖） |
| 调度 | Cron (OpenClaw Gateway) |
| 版本控制 | Git + GitHub (whoerixxz/v2-football-quant) |
| 代码规模 | 15,054行 / 65模块 |

---

## 九、文件结构

```
v2_football_quant/
├── engine/                          51个模块
│   ├── v4_runner.py                 ← 主扫描器
│   ├── v4_dashboard.py              ← 三模式仪表盘
│   ├── v4_master_run.py             ← 一键总控
│   ├── ht_goal_hazard_model.py      ← 分钟概率模型
│   ├── line_decay_model.py          ← 盘口衰减模型
│   ├── asian_ev.py                  ← 亚洲盘EV
│   ├── execution_cost_model.py      ← 执行成本
│   ├── risk_guard.py                ← 风险守卫
│   ├── walk_forward_backtest.py     ← Walk-forward
│   ├── live_ht_over_monitor.py      ← 走地监控
│   ├── second_half_evaluator.py     ← 下半场评估
│   ├── asian_over_settlement.py     ← 亚洲盘结算
│   └── data_sources/               14个数据引擎
├── data/
│   ├── universe/                    ← 全量比赛池
│   ├── decision_logs/               ← 决策日志
│   ├── shadow_backtest/             ← 影子回测
│   ├── execution/                   ← 执行成本模拟
│   ├── model_versions/              ← 模型版本
│   ├── calibration/                 ← EV校准
│   ├── walk_forward/                ← Walk-forward窗口
│   ├── kill_audit/                  ← Kill审计
│   ├── daily_reports/               ← 球探快照+性能摘要
│   ├── paper_trading/               ← 纸盘结算
│   └── live_odds_snapshots/         ← 赔率快照库
├── docs/
│   ├── PROJECT_BOOK_V4.md           ← 本项目说明书
│   ├── V4_STRATEGY_RULES.md         ← 策略规则（28章）
│   └── V4_KEY_REQUIRED_TASKS.md     ← 运行任务清单
└── config/
    ├── leagues_whitelist.json       ← 56联赛白名单
    └── kill_criteria.yaml           ← Kill Criteria
```

---

## 十、生产命令

```bash
# 赛前扫描（生产默认参数）
python3 engine/v4_runner.py --scan-mode fast --lookahead-hours 24 --recent-prewarm off

# 交互仪表盘（默认临场作战模式）
python3 engine/v4_dashboard.py --date 20260512

# 走地监控循环
python3 engine/live_ht_over_monitor.py --date 20260512 --watch --interval 30

# 半场自动结算
python3 engine/v4_ht_result_verifier.py --date 20260512 --watch --interval 300

# 完整复盘（离线）
python3 engine/v4_master_run.py --date 20260512 --phase reports --offline

# Walk-forward回测
python3 engine/walk_forward_backtest.py --date 20260512

# Kill Criteria审计
python3 engine/walk_forward_backtest.py --audit-kill
```

---

> 📌 **v3.2.1 核心升级**：从规则引擎升级为 EV 联合决策。PAPER_BUY_NOW 由 EV_net > min_ev_threshold 驱动，legacy rule 仅作影子对照。

> 📊 **当前状态**：65模块/15K行代码，全流水线闭环，40场336秒。P0八层数据闭环就绪。待300场样本验证策略正期望。
