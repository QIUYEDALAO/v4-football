# V4 走地半场大球策略系统 — 项目说明书 v3.1

> 日期：2026-05-12  
> 状态：**纸盘验证期** — 全流水线闭环，样本累积中  
> 策略代号：`V4_HT_LIVE_PULLBACK`

---

## 一、项目概述

V4 是一个基于 API-Football 实时数据的足球半场大球走地策略系统。核心逻辑：赛前筛选高概率进球比赛进入候选池，赛中等待盘口自然衰减至合理区间后进场，赛后自动结算并复盘。

**策略假设**：赛前半场大球盘口往往高估"强队开场就能进球"的概率。当比赛前 10 分钟未进球时，盘口迅速从大 1.25/1.5 降到大 1.0/0.75，而实际进球概率衰减速度远慢于盘口价格下降速度。策略赚取的是这个时间衰减溢价。

---

## 二、系统架构

### 2.1 总体架构

```
赛前建池 → T-30首发闸门 → 0-10min等降盘 → 8-15min进场 → 亚洲盘结算 → 复盘评估
```

### 2.2 完整流水线

| 阶段 | 时间 | 动作 | 脚本 |
|:---|:---|:---|:---|
| 建池 | 12:00 | 全天扫描，建立候选池 | `v4_runner.py --scan-mode fast` |
| 刷新 | 17:00 | 更新赔率/伤停/排名 | `v4_runner.py` |
| 首发闸门 | T-30 | 阵容复核，BOOST/KEEP/DROP | `--with-lineups` |
| 走地监控 | 0-15min | 等盘口衰减后进场 | `live_ht_over_monitor.py` |
| 下半场评估 | 45min | SH候选评估 | `second_half_evaluator.py` |
| 实时结算 | 半场后 | 亚洲盘结算 | `v4_ht_result_verifier.py` |
| 复盘报告 | 次日 | 完整复盘+策略评估 | `v4_master_run.py --phase reports --offline` |

### 2.3 性能数据（2026-05-12 实测）

| 指标 | 优化前 | 优化后 |
|:---|:---:|:---:|
| 扫描耗时 | 超时(>15min) | **336秒** |
| API调用 | 473次 | **140次** (-70%) |
| 产出 | 无 | 18份情报+仪表盘 |

---

## 三、数据采集管线

### 3.1 数据源

系统通过 **API-Football Pro**（7,500次/天）采集：

| 数据类别 | API端点 | 采集频率 |
|:---|:---|:---|
| 赛程 | `fixtures?date=` | 每次扫描 |
| 历史交锋 | `fixtures/headtohead` | 逐场 |
| 半场/全场赔率 | `odds?fixture=` | 赛前+赛中 |
| 走地赔率 | `odds/live?fixture=` | 赛中轮询 |
| 伤停 | `injuries?team=` | 每次扫描 |
| 首发阵容 | `fixtures/lineups` | T-30分钟 |
| 赛中统计 | `fixtures/statistics` | 赛中轮询 |
| 排名 | `standings?league=` | 每次扫描 |
| 球队赛程 | `fixtures?team=&next=3` | 每次扫描 |

### 3.2 关键规则

- **H2H时间红线**：仅采集2020年及之后的交锋记录
- **H2H样本底线**：2020年以来至少3场
- **扫描窗口**：默认今天+明天全部白名单联赛
- **白名单联赛**：56个（英超→乌拉甲全覆盖）

---

## 四、赛前画像维度

每场比赛采集以下维度：

### 4.1 三向独立评分

| 方向 | 满分 | 用途 | 策略归属 |
|:---|:---:|:---|:---|
| HT_LIVE_OVER | 100 | 上半场走地回调 | 主策略 |
| SECOND_HALF_OVER | 100 | 下半场大球参考 | 仅观察 |
| FULLTIME_OVER | 100 | 全场大球参考 | 仅观察 |

**纪律**：三方向互不污染，SH/FT分数再高也不进入上半场走地池。

### 4.2 画像因子

- H2H上半场/下半场/全场进球率 + 场均进球
- 进球时间分桶（0-15/16-30/31-45分钟，46-60/61-75/76-90分钟）
- 回调适配指标（STRONG/OK/WEAK）
- 近期5场HT/SH/FT攻防动能
- 联赛基准（FRIENDLY/NEUTRAL/COLD）
- 赛季阶段（EARLY/MID/LATE/FINAL_ROUND）
- 排名战意（保级/争冠/中游安全区）
- 赛程压力（未来7/10天密度）
- API数据覆盖闸门
- 首发阵容强度（攻击/中场/防守核心拆分）

---

## 五、走地进场规则

### 5.1 候选池门槛

- 近期HT攻防动能 ≥ 70%
- HT走地评分 ≥ 50分，且为评分最强方向
- 半场大球盘口 ≥ 大1.25
- API数据覆盖 ≥ GOOD

### 5.2 进场窗口（0-15分钟）

```
0-10分钟 有进球 → SKIP_EARLY_GOAL
0-10分钟 0-0   → 继续观察
8-15分钟:
  盘口降到大1.0或大0.75
  Over水位合理（大1.0: 1.65-2.05）
  无红牌/重大伤退
  节奏不沉闷
  → BUY_NOW
15分钟后未达到 → SKIP_WINDOW_CLOSED
```

### 5.3 亚洲盘结算

| 盘口线 | 半场1球 | 半场2球 |
|:---|:---|:---|
| 大0.75 | 半赢 | 全赢 |
| 大1.0 | 走水 | 全赢 |
| 大1.25 | 半输 | 全赢 |
| 大1.5 | 全输 | 全赢 |

---

## 六、漏斗指标与评估计划

### 6.1 全链路漏斗

```
候选池 → 走地监控 → 等到降盘 → 节奏合格 → 进场 → HT命中 → 亚洲盘ROI
```

### 6.2 样本量要求

| 阶段 | 样本量 | 目的 |
|:---|:---:|:---|
| 纸盘观察期 | 50场 | 检查逻辑错误 |
| 小样本校准 | 100场 | 初步命中率/进场率 |
| 有效评估 | 300场 | 判断策略正期望 |
| 分联赛优化 | 500+场 | 独立阈值调整 |

### 6.3 核心评估指标

- HT有球命中率 / W-P-L-Push分布 / ROI
- 分盘口线ROI（0.75/1.0/1.25）
- 分进场分钟ROI（0-5/6-10/11-15）
- 分联赛ROI
- 降盘前进球跳过率 / 节奏不合格跳过率

---

## 七、技术栈

| 组件 | 技术选型 |
|:---|:---|
| 编程语言 | Python 3.9+ |
| 数据源 | API-Football Pro (7,500次/天) + football-data.co.uk (免费历史) |
| 存储 | JSON文件系统 |
| 仪表盘 | 纯HTML/CSS/JS（无框架依赖） |
| 结算 | 自研亚洲盘结算模块 |
| 定时调度 | Cron (OpenClaw Gateway) |
| 版本控制 | Git + GitHub (whoerixxz/v2-football-quant) |

---

## 八、生产命令

```bash
# 赛前扫描
python3 engine/v4_runner.py --scan-mode fast --lookahead-hours 24 --recent-prewarm off

# 交互仪表盘
python3 engine/v4_dashboard.py --date 20260512

# 走地监控
python3 engine/live_ht_over_monitor.py --date 20260512 --watch --interval 30

# 半场结算
python3 engine/v4_ht_result_verifier.py --date 20260512 --watch --interval 300

# 完整复盘
python3 engine/v4_master_run.py --date 20260512 --phase reports --offline
```

---

## 九、运行性能（实测）

| 日期 | 扫描 | 耗时 | API调用 | 产出 |
|:---|:---|:---:|:---:|:---:|
| 2026-05-12 | 40场 | **336秒** | **140次** | 18情报 |

---

## 十、项目文件结构

```
v2_football_quant/
├── engine/
│   ├── v4_runner.py              ← 主扫描器
│   ├── v4_dashboard.py           ← 交互仪表盘
│   ├── v4_scout_report.py        ← 终端情报卡片
│   ├── v4_match_intelligence.py  ← 智能比赛解释器
│   ├── live_ht_over_monitor.py   ← 上半场走地监控
│   ├── live_odds_snapshot.py     ← 赔率快照
│   ├── second_half_evaluator.py  ← 下半场评估
│   ├── v4_ht_result_verifier.py  ← 半场结果回填
│   ├── v4_sh_result_verifier.py  ← 下半场结算
│   ├── v4_master_run.py          ← 一键总控
│   ├── v4_review_report.py       ← 每日复盘
│   ├── v4_strategy_eval.py       ← 策略评估
│   ├── asian_over_settlement.py  ← 亚洲盘结算
│   ├── asian_ev.py              ← 亚洲盘EV计算
│   ├── ht_goal_hazard_model.py   ← 分钟概率模型
│   ├── line_decay_model.py       ← 盘口衰减模型
│   ├── walk_forward_backtest.py  ← Walk-forward回测
│   ├── risk_guard.py            ← 风险守卫
│   ├── execution_cost_model.py   ← 执行成本模型
│   └── data_sources/
│       ├── h2h_engine.py         ← H2H多维画像
│       ├── lineup_strength.py    ← 首发强度识别
│       ├── api_coverage.py       ← 数据覆盖闸门
│       ├── league_baseline.py    ← 联赛基准
│       ├── season_phase.py       ← 赛季阶段
│       ├── motivation.py         ← 战意分析
│       ├── schedule_pressure.py  ← 赛程压力
│       ├── live_tempo.py         ← 赛中节奏
│       ├── context_enrichment.py ← 天气/场地/裁判
│       └── league_hierarchical_threshold.py ← 分层阈值
├── data/
│   ├── daily_reports/            ← 球探快照+性能摘要
│   ├── paper_trading/            ← 纸盘结算
│   ├── live_monitor/             ← 走地状态
│   └── live_odds_snapshots/      ← 赔率快照库
├── docs/
│   ├── V4_STRATEGY_RULES.md      ← 策略规则(28章)
│   └── V4_KEY_REQUIRED_TASKS.md  ← 运行任务清单
└── config/
    └── kill_criteria.yaml        ← 策略Kill Criteria
```

---

> 📌 **核心设计理念**：不在赛前预测谁会进球，在赛中等待盘口犯错。用时间换价格，用纪律换盈亏比。

> 📊 **当前状态**：全流水线闭环，40场扫描336秒，18份情报产出。待300场样本验证策略正期望。
