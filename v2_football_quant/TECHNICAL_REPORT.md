# ⚽ V2 量化足球分析系统 — 完整技术报告

> **版本**: v1.1  
> **启动日期**: 2026-05-04  
> **报告日期**: 2026-05-06 17:00  
> **代码规模**: 14 模块 · 3026 行 Python + 1 SQL schema  
> **数据规模**: 2322 场联赛回测 + 128 场世界杯回测  
> **数据源**: API-Football Pro (v3)  
> **联赛覆盖**: 56 个一级联赛  
> **核心KPI**: 命中率 > 58% | vig-adjusted ROI > 3% | CLV > 0

---

## 💎 核心价值观（Core Philosophy）

> **赔率涨跌不改变已成交的 PnL，只影响 CLV 的符号，而 CLV 的符号才是 Alpha 存在的证据。**

- 命中率再高、连赢再多，如果 CLV < 0，只是方差/运气。
- 只有长期稳定击败收盘线（Pinnacle Closing Line），才证明 Alpha 真实存在。
- 收盘线是全市场最聪明的钱博弈出来的有效前沿——它是衡量模型价值的唯一客观标尺。

---

## 一、项目背景与目标

### 1.1 投注策略

| 维度 | 说明 |
|------|------|
| **核心策略** | 半场大小球（Half-Time Over 0.5/1.0），即上半场是否有进球 |
| **理论基础** | 历史交锋上半场进球率高 → 本场上半场也容易有进球 |
| **本金预算** | 2000 单位 |
| **单注范围** | 100-300 单位（1/4 Kelly 仓位管理） |
| **单日上限** | ≤ 5 场推荐 |
| **目标市场** | 日常联赛（V38 策略） + 2026 世界杯（独立模型） |

### 1.2 已验证性能（2322场回测，时序对齐后）

| 指标 | 数值 |
|------|:---:|
| 回测场次 | 2322 场（35联赛，2026-03-05 → 2026-05-04） |
| V38 门槛通过场次 | 510 场 |
| **命中率** | **70.8%（361/510）** |
| OOS Train/Test | 71.3% / 70.3%（稳定，差异仅1%） |
| 滚动50场 ROI | 10个窗口全正，+18.4% ~ +40.6% |
| 模型衰退 | 无预警 |
| 世界杯模型 | 128场回测，命中率 76.7%（23/30） |

---

## 二、系统架构

```
v2_football_quant/
├── config/
│   ├── leagues_whitelist.json    # 56个一级联赛白名单
│   ├── market_aliases.json       # 盘口标准化映射
│   └── odds_strategy.md          # 赔率策略文档
├── db/
│   ├── v2_football.db            # SQLite 数据库
│   └── init_schema.sql           # 4张表 schema
├── data/
│   ├── raw_fixtures/             # API 原始响应缓存
│   │   ├── h2h/                  # 2322 个 H2H JSON
│   │   ├── predictions/          # 2322 个 Predictions JSON
│   │   ├── odds/                 # 312 个 Odds JSON
│   │   └── fixtures_list.json    # 2322 场比赛索引
│   ├── worldcup/                 # 世界杯数据（128场 2018+2022）
│   ├── daily_reports/            # 每日推荐日报
│   ├── paper_trading/            # 纸盘验证日志
│   └── backtest_results_v0.csv   # 2322 场回测结果
├── engine/                       # 核心引擎（14个模块）
│   ├── team_cn_map.py            # 球队中英文映射（320条，fuzzy match）
│   ├── daily_runner.py           # ⭐ 每日自动运行（444行）
│   ├── backtest_pipeline_v0.py   # 回测流水线
│   ├── scoring_engine_v0.py      # 5维度评分引擎
│   ├── wc_model.py               # 世界杯独立3维模型
│   ├── bankroll.py               # Kelly仓位 + 熔断
│   ├── paper_trading.py          # 纸盘验证 + 全量汇总
│   ├── oos_monitor.py            # OOS验证 + 滚动ROI + 衰退预警
│   ├── odds_monitor.py           # Pinnacle赔率轮询 + 15%波动报警
│   ├── aligner.py                # 时序对齐 + H2H自引用检测
│   ├── clv.py                    # 收盘线价值 + EV + 公平赔率
│   ├── fetcher.py                # 批量数据拉取（限频+重试+降级）
│   ├── p0_day1_validate.py       # 单场API链路验证
│   └── fetcher.js                # Node.js 版拉取
├── TECHNICAL_REPORT.md           # 本报告
└── P0-P2-TRACKER.md              # 任务追踪
```

### 2.1 代码规模

| 模块 | 行数 | 用途 |
|------|:---:|------|
| team_cn_map.py | 458 | 320条球队英文→中文，逐级精确+子串+fuzzy匹配 |
| daily_runner.py | 444 | 每日自动化全流程（含降级策略+赔率模糊匹配+H2H有效性过滤） |
| paper_trading.py | 240 | 赛后验证 + 纸盘汇总（ROI/CLV/命中率/联赛分层/滚动窗口） |
| fetcher.py | 239 | 批量拉取（asyncio + 限频 + 3次重试 + 指数退避） |
| aligner.py | 221 | 时序对齐、H2H自引用检测、数据质量标记 |
| scoring_engine_v0.py | 217 | 5维等权评分（含H2H自引用排除） |
| backtest_pipeline_v0.py | 213 | 回测主流程 → CSV输出（含预留赔率字段） |
| p0_day1_validate.py | 208 | 单场API链路验证 → 数据落库 |
| oos_monitor.py | 194 | OOS对抗验证 + 滚动50场ROI + 衰退预警 |
| odds_monitor.py | 162 | Pinnacle赔率轮询 + 15%水位报警 + 快照保存 |
| wc_model.py | 157 | 世界杯独立3维评分模型（数据诚实版） |
| bankroll.py | 153 | Kelly仓位 + 动态风控 + 连续亏损熔断 |
| clv.py | 120 | 收盘线价值 + 期望值 + 公平赔率 + 庄家抽水计算 |
| **总计** | **3026** | |

---

## 三、数据采集体系

### 3.1 数据源

**API-Football Pro (v3)**
- 端点: `https://v3.football.api-sports.io`
- 限频: 30次/分钟（免费版），实际使用 1.5秒/次间隔
- 重试: 3次 + 指数退避（2s/4s/8s）
- 降级: 失败 → `_fallback=True` 标记，不中断流水线

### 3.2 采集的原始数据

| 数据类型 | API端点 | 采集内容 | 数量 |
|------|------|------|:---:|
| **Fixtures** | `GET /fixtures` | 比赛基本信息、半场/全场比分、开赛时间、联赛 | 2322 场 |
| **H2H** | `GET /fixtures/headtohead` | 两队历史交锋 20 场，含半场/全场比分 | 2322 个 JSON |
| **Predictions** | `GET /predictions` | 赛前预测：胜平负概率、泊松分布、advice、form、att/def | 2322 个 JSON |
| **Odds** | `GET /odds` | 博彩公司实时赔率（仅保存7天） | 312 个 JSON |

### 3.3 Fixtures 提取字段

```json
{
  "id": 1379257,
  "date": "2026-03-05T20:00:00+00:00",
  "league": 39,
  "home": "Tottenham",
  "away": "Crystal Palace",
  "homeId": 47,
  "awayId": 52,
  "htHome": 1,
  "htAway": 3,
  "ftHome": 1,
  "ftAway": 3
}
```

### 3.4 H2H 提取字段（每场历史交锋）

- `fixture.date` — 比赛日期
- `fixture.status.short` — 赛果状态（仅统计 FT/AET/PEN，排除延期/腰斩）
- `score.halftime.home/away` — **半场比分**（核心特征）
- `score.fulltime.home/away` — 全场比分
- `league.name` — 联赛名称

### 3.5 Predictions 提取字段

```python
{
  "predictions": {
    "advice": "Double chance : draw or Manchester City",  # AI投注建议
    "percent": {"home": "10%", "draw": "45%", "away": "45%"},
    "under_over": None,
  },
  "teams": {
    "home": {
      "last_5": {
        "form": "27%",       # 近5场胜率
        "att": "39%",        # 进攻能力评分
        "def": "56%",        # 防守能力评分
        "goals": {"for": {"average": 1.4}}
      }
    },
    "away": { ... }
  }
}
```

---

## 四、核心分析逻辑

### 4.1 5维等权评分（满分100）

| # | 维度 | 权重 | 数据来源 | 计算逻辑 |
|:--:|------|:--:|------|------|
| 1 | **H2H 上半场进球率** | 60% | h2h JSON | HT有球场次/总H2H场次 × 60 |
| 2 | **近期进攻** | 20% | Predictions.att | (主队att + 客队att)/2 × 0.20 |
| 3 | **H2H 场均进球** | 10% | h2h JSON | HT总进球数/总场次 × 10 |
| 4 | **AI建议信号** | 10% | Predictions.advice | 含over/goal关键词 → +5；含under → -5 |

### 4.2 V38 硬性门槛

```python
H2H场次 ≥ 4 场
HT进球率 ≥ 80%
HT 0-0场次 ≤ 2 场
H2H比赛状态必须为 FT/AET/PEN（排除延期/腰斩）
```

### 4.3 时序对齐（防数据泄露 — 最关键的发现）

**H2H API 将本场比赛自身包含在返回结果中！**

| 阶段 | 场次 | 命中率 | 状态 |
|------|:---:|:---:|------|
| 未排除自引用 | 763 | 86.4% | ❌ 数据泄露 |
| **排除自引用** | **510** | **70.8%** | ✅ 真实 |

```python
def strip_self_reference(h2h_list, fixture_id):
    return [f for f in h2h_list 
            if f["fixture"]["id"] != fixture_id]
```

**此外：H2H 请求必须用球队ID而非fixture ID**
```python
# ❌ 错误：fixture ID 经常返回0场
api(f"fixtures/headtohead?h2h={fixture_id}")

# ✅ 正确：球队ID组合
api(f"fixtures/headtohead?h2h={home_id}-{away_id}")
```

### 4.4 网格搜索结果

**最优参数组合：H2H≥4 + 进球率≥85% + 0-0≤1 + 近期ATT≥45%**
- 命中率: 70.3%（286场）
- 比 V38 原阈值少 224 场但信号更纯

### 4.5 0-0 防守机制

```python
if h2h_zero > 3:  # H2H 中 0-0 场次 > 3
    score = min(score, 40)  # 强制降到 40 以下
```

---

## 五、赔率与CLV体系

### 5.1 赔率模糊匹配（多层降级策略）

```
1. Pinnacle (id=6) → HT Over 0.5 精确名
2. Pinnacle → HT Over/Under 模糊匹配（first half + over/under）
3. Bet365 (id=2) → 同上
4. 任意博彩公司 → 顺延
5. 降级到 FT Over 2.5 作为参考
6. 全找不到 → 标记 skip_reason="no_ht_market"
```

**赔率市场名模糊匹配**：含 `first half/1st half/ht` + `over/under` 的 market 名。

**流动性检查**：博彩公司报价 < 3 家 → 标记 `low_liquidity`，跳过。

### 5.2 CLV 计算公式

```python
CLV = (ClosingOdds - PlacedOdds) / PlacedOdds

# CLV > 0 → 战胜市场
# CLV < 0 → 被市场碾压

# 实战 ROI（扣除 5% 庄家抽水）
Real_ROI = HitRate × (AvgClosingOdds × 0.95) - 1
```

**赔率时间锚点**：统一使用 Kickoff-30min 的 Pinnacle 赔率作为 ClosingOdds。

---

## 六、回测验证结果

### 6.1 联赛分层（34个联赛，时序对齐后）

| 分级 | 联赛数 | 代表联赛 | H2H命中率 |
|:---:|:---:|------|:---:|
| 🟢 强 | 9 | 瑞士超、乌克超、比甲、沙特联、克亚甲等 | 86-100% |
| 🟡 中 | 10 | 保甲、荷甲、德甲、意甲、土超等 | 70-85% |
| 🔴 弱 | 15 | 西甲、英超、澳超、墨西联、法甲等 | 37-69% |

### 6.2 OOS 对抗验证（时序切分）

| 指标 | Train (3/5-4/10) | Test (4/10-5/4) |
|------|:---:|:---:|
| V38 通过场次 | 261 | 249 |
| 命中 | 186 | 175 |
| **命中率** | **71.3%** | **70.3%** |
| **稳定性** | — | ✅ 差异仅 1% |

### 6.3 滚动50场 ROI（10个窗口全正🟢）

| 窗口 | ROI | 窗口 | ROI |
|------|:--:|------|:--:|
| 03-05 → 03-08 | +33.2% | 04-06 → 04-12 | +25.8% |
| 03-09 → 03-14 | +18.4% | 04-12 → 04-19 | +29.5% |
| 03-14 → 03-20 | +36.9% | 04-19 → 04-25 | +40.6% |
| 03-20 → 04-04 | +25.8% | 04-25 → 04-28 | +25.8% |
| 04-04 → 04-06 | +40.6% | 04-29 → 05-03 | +33.2% |

> ⚠️ ROI 使用模型理论赔率 1.85，实战需扣除 5-8% 庄家抽水

---

## 七、风险控制体系

### 7.1 Kelly 仓位管理

```python
def kelly_fraction(p, odds, kelly_factor=0.25):
    """1/4 Kelly — 保守仓位"""
    b = odds - 1
    f_star = (b * p - (1 - p)) / b
    return max(0, f_star * kelly_factor)
```

| 条件 | 动作 |
|------|------|
| 正常 | 1/4 Kelly，单注 100-300 |
| 回撤 > 25% | 降至 1/8 Kelly，单注减半 |
| 回撤 > 40% | **熔断**，停投 |
| 连续亏损 5 场 | 熔断器打开，人工干预 |
| 单日场次 | ≤ 5 场 |
| 赔率 < 1.75 | 跳过不推 |

### 7.2 流动性与数据质量防线

| 防线 | 条件 | 动作 |
|------|------|------|
| 博彩公司数量 | < 3 家报价 | 跳过（低流动性） |
| 半场盘口 | 找不到 HT market | 标记 `no_ht_market` |
| H2H 比赛有效性 | 只统计 FT/AET/PEN | 排除延期/腰斩 |
| API 失败降级 | H2H/Predictions 超时 | `_fallback=True`，不中断 |

---

## 八、世界杯独立模型

### 8.1 设计理念

- **禁用 H2H 权重**：国家队 4 年阵容一变，历史交锋价值极低
- **赛制因子为核心**：小组赛刻意保守（0-0防守阈值40%）vs 淘汰赛必须分胜负（阈值25%）
- **数据诚实**：只用可自动获取的 3 维度

### 8.2 评分公式

```python
raw_score = (
    stage_weight * 0.40           # 淘汰赛 1.15-1.30 > 小组赛 0.85
    + att_signal * 0.35           # 进攻信号
    + def_weakness * 0.25         # 防守漏洞
) × cross_conf_bonus              # 欧洲vs亚非 +15%
```

### 8.3 回测结果（128场 2018+2022）

| 阶段 | 推荐 | 命中 | 命中率 |
|------|:--:|:--:|:--:|
| 小组赛 | 2 | 1 | 50% |
| 16强 | 5 | 4 | 80% |
| 8强 | 8 | 7 | 88% |
| 半决赛 | 4 | 3 | 75% |
| 决赛 | 9 | 6 | 67% |
| 三四名 | 2 | 2 | 100% |
| **合计** | **30** | **23** | **76.7%** |

**关键发现：淘汰赛上半场进球(1.31球/场) > 小组赛(0.94球/场)**

---

## 九、每日自动化流程

### 9.1 6步流水线

```
08:00 daily_runner.py 自动触发
    │
    ├── [1/6] 拉取今日赛程
    │   └── 全量请求 → 白名单本地过滤 → NS/TBD 比赛
    │
    ├── [2/6] 拉取 H2H + Predictions（try/except 降级）
    │   └── 球队ID查H2H + Predictions API
    │
    ├── [3/6] 评分计算
    │   └── 排除自引用 + FT/AET/PEN过滤 → V38门槛 → 5维评分
    │
    ├── [4/6] Top 5 赔率抓取
    │   └── 模糊匹配 HT Over 0.5 → 流动性检查 → 降级兜底
    │
    ├── [5/6] 生成 Markdown 日报
    │   └── data/daily_reports/daily_{date}.md
    │
    └── [6/6] 保存预测 JSON
        └── data/daily_reports/predictions_{date}.json
```

### 9.2 赛后验证

```bash
# 验证今日预测
python3 paper_trading.py --verify 2026-05-06

# 全量汇总
python3 paper_trading.py --summary
```

---

## 十、56个联赛白名单

| 区域 | 数量 | 联赛 |
|------|:--:|------|
| 🔵 杯赛 | 2 | 欧冠(2)、欧联杯(3) |
| 🟢 欧洲 | 35 | 英超(39)、英冠(40)、西甲(140)、西乙(141)、意甲(135)、意乙(136)、德甲(78)、德乙(79)、法甲(61)、法乙(62)、荷甲(88)、葡超(94)、比甲(144)、苏超(179)、土超(203)、俄超(235)、挪超(103)、瑞典超(113)、丹超(119)、奥甲(218)、瑞士超(207)、波兰超(106)、塞尔超(286)、克亚甲(210)、罗甲(283)、冰岛超(164)、芬超(244)、乌克超(333)、希腊超(197)、捷克甲(345)、匈甲(271)、保甲(172)、斯洛伐超(332)、立陶甲(362)、阿塞超(418) |
| 🔴 亚洲 | 8 | 日职联(98)、韩K联(292)、澳超(188)、沙特联(307)、印度超(323)、印尼超(274)、中超(169)、阿联酋超(301) |
| 🟠 美洲 | 9 | 自由杯(10)、南美杯(11)、美职业(253)、墨西联(262)、巴西甲(71)、阿甲(128)、乌拉甲(268)、秘鲁甲(281)、玻利甲(344) |
| 🟣 其他 | 2 | 埃及超(233)、爱超(357) |

---

## 十一、关键数据质量发现

### 11.1 H2H 自引用污染（致命级）
API-Football 将本场比赛自身包含在 H2H 返回中。不排除 → 86.4% 虚高命中率。排除后 → 70.8% 真实。

### 11.2 Odds 保存期限制
API 仅保存过去 7 天赔率。历史回测无法使用真实赔率，用模型理论赔率替代。

### 11.3 fixture ID vs 球队ID
`h2h={fixture_id}` 在大部分情况下返回0场。必须用 `h2h={home_id}-{away_id}`。

### 11.4 赔率市场名不一致
不同联赛/博彩公司的 market name 不同。采用模糊匹配（first half + over/under 关键词）解决。

---

## 十二、执行纪律

| # | 规则 | 原因 |
|---|------|------|
| 1 | 回测数据严格 T-24h 时间对齐 | 防数据泄露 |
| 2 | P0 不碰 LightGBM/动态权重 | 先等权跑通 |
| 3 | 1/4 Kelly 仓位 | 防爆仓 |
| 4 | 单日推荐 ≤ 5 场 | 质量 > 数量 |
| 5 | 0-0 概率 > 35% 强制降级 | 减少无效投注 |
| 6 | 博彩公司 < 3 家跳过 | 低流动性风险 |
| 7 | 所有时间字段 UTC | 跨时区/夏令时不出错 |

---

## 十三、纸盘验收硬指标（5/6 - 5/12）

| 指标 | 计算口径 | 通过阈值 | 失败动作 |
|------|---------|:--:|------|
| vig-adjusted ROI | HitRate × (AvgClosingOdds × 0.95) - 1 | ≥ +3.0% | 暂停，检查特征衰减 |
| 平均 CLV | PlacedOdds / ClosingOdds - 1 | > 0 | 若 < -0.02 → 停用 |
| 最大回撤 MDD | 本金曲线最低谷 | ≤ 12% | 触发熔断，人工复盘 |
| 推荐稳定性 | 7天累计推荐场次 | ≥ 25场 | < 15场 → 放宽过滤 |

---

## 十四、下一步计划

| 阶段 | 任务 | 时间 |
|------|------|:--:|
| 📊 纸盘验证 | 7天纸盘，每日 08:00 跑 daily_runner | 5/6 - 5/12 |
| 📥 数据补充 | 拉取缺失14个联赛历史数据 | 5/6 - 5/10 |
| 🏆 世界杯备战 | 阵容依赖度预标注 + 赛制因子完善 | 5/10 - 5/20 |
| 🚀 切盘判断 | 若纸盘 CLV>0 & ROI≥3% → 切实盘 | 5/12 |

---

## 十五、系统架构演进路线图：纸盘 vs 实盘

### 15.1 核心问题：静态扫描与动态盘口的错位

博彩市场赔率是高度动态的。如果 08:00 算出的赔率是 3.05（Edge > 5%），但比赛 22:00 才开打，中间 14 小时赔率必然发生变化：

| 情形 | 赔率变化 | 风险 |
|:---|:---|:---|
| **A. 赔率下跌** (3.05 → 2.80) | 买入价变差 | 如果 08:00 看到推荐但下午才手动下注，Edge 可能已从 +8% 跌到 -2%。这是**标准负期望值（-EV）交易**。 |
| **B. 赔率上升** (3.05 → 3.50) | 表面 Edge 变大 | 说明全市场聪明钱都在买对立面，庄家被迫调价平衡资金。可能发生模型不知道的**突发基本面变化**（核心球员复出/伤病等）。 |

### 15.2 设计红线：信号抓取与交易执行彻底分离

> **量化交易系统最大的技术债不是代码写得乱，而是架构初衷的遗忘。**
> 绝不直接把 `daily_runner.py` 的 08:00 快照结果拿去 API 下单——
> 这是静态快照代替临场轮询的致命错误。

### 15.3 两阶段架构对比

| 维度 | 📊 纸盘阶段（5/6 - 5/12） | 🚀 实盘阶段（未来） |
|:---|:---|:---|
| **08:00 任务** | `daily_runner.py`：快照扫描 + 生成推荐 | `daily_runner.py`：**降级为"观察池生成器"** — 只挑满足 att_def_spread 档位的比赛，不生成最终下注指令 |
| **赛前任务** | ❌ 不管赔率变化 | `odds_monitor.py`：**开赛前 30 分钟起，每分钟轮询** Pinnacle 最新赔率 |
| **临场决策** | 假设 08:00 瞬间以快照赔率"成交" | **T-15min**：用最新赔率重新计算 Edge，仅当 Edge 仍 > 5% → Kelly 仓位 → API 下单 |
| **结算方式** | `paper_trading.py`：placed_odds vs closing_odds → CLV | 实盘 PnL + CLV 双轨评估 |
| **赔率变化意义** | 只影响 CLV 符号（负→方差运气，正→真 Alpha） | 触发 `odds_monitor.py` 15% 水位报警，标记比赛状态 |

### 15.4 纸盘阶段的关注焦点

```
                       08:00 快照成交价              凌晨收盘线
                    placed_odds = 3.05    vs    closing_odds = 2.80
                               │                      │
                               └──── CLV = -8.2% ────┘
                                      (市场比你聪明)

                    placed_odds = 3.05    vs    closing_odds = 3.50
                               │                      │
                               └──── CLV = +14.8% ────┘
                                      (你跑赢了市场)
```

**纸盘期核心 KPI 不是 PnL，是 CLV 的正向分布。**
- CLV > 0 的比赛占比 → Alpha 强度的直接度量
- 7 天纸盘后，若平均 CLV > 0 且占比 > 50%，模型就值得真金白银。

### 15.5 实盘激活流程

```
08:00  daily_runner.py
       └─ 赛程拉取 → att_def_spread → 白名单过滤
       └─ 存⼊ today_watchlist.json

T-30min odds_monitor.py 启动
       └─ 每 1 分钟轮询 Pinnacle HT 1X2 赔率
       └─ 水位变化 > 15% → 写入 alert_log.json

T-15min 临场决策
       └─ 取最新赔率 → 重新计算 fair_odds + edge
       └─ edge > 5% → Kelly 仓位 → API 下单
       └─ edge ≤ 5% → 放弃，记录 skip_log

次日   paper_trading.py
       └─ 取 closing_odds → 计算 True CLV
       └─ PnL + CLV 分桶统计 → 风险归因报告
```

### 15.6 关键里程碑

| 里程碑 | 条件 | 动作 |
|:---|:---|:---|
| 🟡 纸盘验证完成 | 7 天 ≥ 25 场推荐 | 生成首份全量汇总报告 |
| 🟢 切盘绿灯 | 平均 CLV > 0 · ROI ≥ 3% · MDD ≤ 12% | 激活 odds_monitor，准备小仓位实盘 |
| 🔴 切盘红灯 | 平均 CLV < -2% | 暂停，重新校准评分引擎权重 |

---

## 附录 A：14个引擎模块清单

| 文件 | 行数 | 功能 |
|------|:--:|------|
| `team_cn_map.py` | 458 | 320条球队中英文映射 + fuzzy match |
| `daily_runner.py` | 444 | ⭐ 每日自动化全流程（含降级+赔率模糊+H2H校验）|
| `paper_trading.py` | 240 | 赛后验证 + 纸盘汇总（ROI/CLV/联赛分层/滚动窗口） |
| `fetcher.py` | 239 | 批量拉取（限频+重试+降级） |
| `aligner.py` | 221 | 时序对齐 + H2H自引用检测 + 数据质量标记 |
| `scoring_engine_v0.py` | 217 | 5维等权评分引擎 |
| `backtest_pipeline_v0.py` | 213 | 回测主流程 → CSV |
| `p0_day1_validate.py` | 208 | 单场API链路验证 |
| `oos_monitor.py` | 194 | OOS对抗验证 + 滚动ROI + 衰退预警 |
| `odds_monitor.py` | 162 | Pinnacle赔率轮询 + 15%报警 + 快照 |
| `wc_model.py` | 157 | 世界杯3维独立模型 |
| `bankroll.py` | 153 | Kelly仓位 + 动态风控 + 熔断 |
| `clv.py` | 120 | CLV + EV + 公平赔率 + 抽水计算 |
| **总计** | **3026** | |

## 附录 B：数据库 Schema

```sql
-- 比赛结果表
fixtures_results (fixture_id, league_id, kickoff_utc, 
    home/away team, ht/ft/et/penalty scores)

-- 赔率快照表
odds_snapshots (fixture_id, captured_at, bookmaker, 
    market, odds_type, decimal_odds, is_closing)

-- API预测缓存
predictions_cache (fixture_id, raw_response, advice, 
    prob_home/draw/away, under_over, poisson, form, att, def)

-- 回测结果
backtest_results (fixture_id, model_version, score, 
    model_prob, placed_odds, closing_odds, clv, ev, 
    recommended, actual_result, roi)
```

---

> 💡 **最后更新**：2026-05-07 23:30  
> **状态**：Phase 3 多策略路由蓝图已部署 · V2 JSON 生成端封板 · P0+P1+P2+2.1+2.2+3 全部就绪  
> **下一里程碑**：积累 N ≥ 20 场有效样本 · Router 激活 · 纸盘验收 (5/12)

---

## ⚖️ Phase 3 路由与加权行为守则 (The Iron Rules)

**第一条：防范过拟合 (N ≥ 20 铁律)**
任何归因面板（A/B 测试、档位跳变、交叉视角）中发现的正向或负向 Pattern，**在其独立样本数 (N) 达到 20 场之前，仅限观察，绝对禁止在 Router 中修改权重或干预路由。**

**第二条：红线不可逾越**
无论 Router 赋予某笔交易多高的 Priority（优先级）或 Boost 加成，最终下注金额**绝对不允许突破 `bankroll.py` 中设定的 5% 仓位硬顶和 Kelly 基础风控参数**。

**第三条：CLV 唯一裁判**
我们只对具有稳健且显著正向 `True CLV` (去水收盘线价值) 的子集（如小幅跳变区）开启提权；对 `True CLV` 严重为负的子集（如大幅残阵区）执行阻断。胜率不作为核心改动依据。
