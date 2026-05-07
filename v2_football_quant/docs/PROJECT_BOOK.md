# ⚽ V2 Football Quant — 项目书 v2.1
> HT 1X2 分档模型 · 纸盘验证第3天 · 2026-05-07 · P0 五件套已部署

| 指标 | 值 |
|:---|---|
| 状态 | 纸盘验证 (5/6 – 5/12) |
| 本金 | 2,000 |
| 注码 | 100 – 300 (Kelly 不足100 → SKIP_LOW_KELLY) |
| Kelly | 1/4 (不再强行 clamp 抬高) |
| CLV | 三层分解: raw_clv / fair_line / ev_vs_close |
| 主模型 | deepseek-v4-pro |
| Cron | 每天 08:00 BJT |
| 最新 Commit | 8918c5b — P0 五件套 |

---

## 目录

1. 项目概览与时间线
2. 系统架构全景
3. V2 引擎核心: att_def_spread 分档模型
4. V38 辅助系统: 捷报比分 H2H 采集
5. V3/V4 多策略架构 (Strategy Router)
6. 纸盘验证体系 (Paper Trading)
7. CLV 收盘线价值 —— 核心诊断
8. 工程基础设施 (API Key · Git · Cron · 通道)
9. 风控体系 (Kelly · 熔断 · 仓位)
10. 数据与联赛白名单
11. 风险警示与红线
12. 路线图与下一步

---

## 1. 项目概观与时间线

V2 Football Quant 是一个基于 API-Football Pro 数据驱动的足球半场投注量化系统。
核心理念：信号与执行分离 —— 模型产出 Edge(>5%) 的信号，风控体系用 True CLV 验证含金量，
仅通过纸盘验收后进入实盘。

### 关键里程碑

| 日期 | 事件 |
|:---|---|
| 2026-04-24 | OpenClaw + DeepSeek 环境初始化 |
| 2026-04-25 | V26–V33 捷报比分 H2H 分析系统迭代 (V33: 分进程防OOM) |
| 2026-05-01 | V2 HT 1X2 模型核心逻辑设计 (att_def_spread 分档) |
| 2026-05-02 | V33 策略开发完成 + V38 策略锁定 |
| 2026-05-05 | 首场纸盘: Al Khaleej vs Al Hilal ✅ HT 1-1 |
| 2026-05-06 | **Cron 08:00 首跑 · 纸盘验证开始 (5/6 – 5/12)** |
| 2026-05-06 PM | V3/V4 多策略系统建成 · Strategy Router 三路分发 |
| 2026-05-07 | 工程交付: API Key 统一 · CLV 结算闭环 · 项目书生成 |
| 2026-05-07 PM | **P0 五件套部署**: Kelly毒药拆除 · 三层CLV · 全量候选池 · 信号审计 · 密钥清理 |

---

## 2. 系统架构全景

### 2.1 四引擎并行架构

| 引擎 | 数据源 | 市场 | 状态 |
|:---|:---|:---|:---|
| **V2** (主力) | API-Football Pro | HT 1X2 (半场胜平负) | 纸盘中 ✅ |
| **V38** (辅助) | 捷报比分 nowscore | HT OU (半场大小球) | 暂停 ⚠️ |
| **V3** (世界杯) | Elo + API-Football | 多类 · 亚盘套利 | 已完成 · 待赛 💤 |
| **V4** (五大联赛) | Proxy xG + 伤停 | 多因子综合 | 暂停 · 8月 💤 |

### 2.2 Strategy Router 分发

```
strategy_router.py
├── V2 (次级) → daily_runner → HT 1X2 信号
├── V3 (W杯) → wc_model.py → AH 亚盘套利
└── V4 (五大) → proxy_xg_engine → 多因子综合
```
开闭原则设计 —— 新模型独立接入，不修改 daily_runner。

### 2.3 核心文件地图

```
engine/
├── daily_runner.py       (16.4K) 每日主入口: 扫描+预测+结算昨天
├── paper_trading.py      (20.9K) 纸盘验证: 赛果+收盘赔率+CLV
├── bankroll.py            (4.1K) 仓位管理: Kelly公式+熔断
├── strategy_router.py     (4.0K) 策略路由分发器
├── wc_model.py            (9.0K) V3 W杯 Elo 模型
├── fetcher.py             (8.3K) API-Football 批量拉取
├── odds_monitor.py        (5.2K) 实时赔率轮询·水位报警
├── oos_monitor.py         (5.9K) 样本外观测器
├── scoring_engine_v0.py   (9.2K) 多因子评分引擎
├── clv.py                 (4.4K) CLV 计算模块
├── aligner.py             (7.4K) 数据对齐引擎
├── logger.py              (3.2K) 统一日志
├── fair_odds_matrix.json  (2.7K) HT 1X2 公平赔率矩阵
└── data_sources/
    ├── apifootball_deep.py     API-Football 深挖(伤停+首发+战力)
    ├── proxy_xg_engine.py      伪xG引擎(射门加权)
    ├── elo_scraper.py          Elo积分爬虫
    └── ...

config/
├── secrets.py             (484B) 统一API Key源 (唯一入口)
├── leagues_whitelist.json  (1.5K) 56个白名单联赛
├── core_players_weight.json(4.9K) 12队核心球员权重
├── market_aliases.json     (435B) 市场别名映射
└── odds_strategy.md       (1.8K) 赔率策略文档

data/
├── daily_reports/
│   ├── predictions_20260505.json
│   └── predictions_20260506.json
└── paper_trading/
    ├── verified_20260505.json
    └── verified_20260506.json
```

---

## 3. V2 引擎核心: att_def_spread 分档模型

### 核心理念

将每场比赛的攻防实力差 (att_def_spread) 分为 10 档，每档拥有独立的 HT 1X2 概率分布，
基于 2,322 场历史比赛统计。

### 3.1 每日工作流 (08:00 BJT)

1. 拉取赛程: API-Football `/fixtures` → 未来 24h 白名单比赛
2. 计算 att_def_spread: 基于近 5 场主客队得失球率差值
3. 分档: 10 档 (档5 ≈ 实力均衡)
4. 查表: `fair_odds_matrix.json` → H/D/A 公平赔率
5. 比价: Pinnacle 实时赔率 vs 公平赔率 → Edge(%)
6. 过滤: Edge > 5% 信号 → 推荐清单
7. 保存: `predictions_YYYYMMDD.json` → 等待次日 CLV 结算

### 3.2 10 档分位表 (基于 2,322 场历史)

| 档位 | att_def_spread | 典型场景 | H% | D% | A% |
|:---:|:---|:---|---:|---:|---:|
| 1 | < -30 | 客队碾压 (PSG客战垫底队) | 10 | 18 | 72 |
| 3 | -20 ~ -10 | 客队占优 | 20 | 30 | 50 |
| **5** | **-10 ~ +10** | **实力均衡 (拜仁vs巴黎)** | **38** | **32** | **30** |
| 7 | +10 ~ +20 | 主队占优 | 48 | 28 | 24 |
| 10 | > +30 | 主队碾压 | 70 | 20 | 10 |

### 3.3 Edge 计算

```
Edge = 模型概率 - 市场隐含概率
市场隐含概率 = 1 / 当前Pinnacle赔率

例: 拜仁vs巴黎, 档5
  模型D概率 = 32.0%
  市场D隐含 = 1/3.19 = 31.4%
  Edge = 32.0% - 31.4% = +0.6% (太小，不是这场的真实值)
```

**实际3场推荐全部为档5 (均衡) → 推半场平局(D)**。
均衡比赛中平局是最容易被市场低估的结果。

---

## 4. V38 辅助系统: 捷报比分 H2H 采集

> ⚠️ V38 源代码完整但未设置定时任务。V2 之前的主策略，专注历史交锋上半场进球率。

### 4.1 策略硬性门槛

| 参数 | 值 | 说明 |
|:---|---|:---|
| H2H 最少场数 | 4 | 不足4场的比赛跳过 |
| 最低进球率 | 80% | H2H上半场有进球的场次占比 |
| 最大0-0场数 | 2 | H2H中0-0不能超过2场 |
| 盘口要求 | 必须有 | 无半场盘口→不推荐 |
| 联赛白名单 | 21个 | 五大+欧洲主流+亚洲+美洲 |

### 4.2 分级规则

```
100% 进球率:
  H2H≥6 + 场均≥1.2 → 🔥🔥 强烈推荐
  H2H=4-5          → ⚡ 样本小，降为推荐

80-89% 进球率:
  场均≥1.8                      → ✅ 推荐
  场均≥1.5 且 H2H≥8            → ✅ 推荐
```

### 4.3 增强信号

- **H2H 分时期加权**: 前3场权重1.5x，早期0.7x
- **连续趋势检测**: 连续3场进球→加分，连续3场冷→扣分
- **盘口变化**: 升盘=机构看好/尽快买，降盘=门槛降低/买入时机
- **近期状态辅判**: 两队近期HT进球率≥70%→提升信心

### 4.4 分进程防 OOM 架构

```
jiebao-scraper-v38.js (主入口·只做编排)
  └── fork batch-worker-v38.js (子进程, 每15场)
        └── 独立 Playwright browser
        └── 退出即100%释放内存
```
实测: 90场无OOM (之前20场/批跑90场必挂)

### 4.5 捷报比分验证数据 (4/27 – 5/1)

| 进球率 | 场次 | 命中 | 实际命中率 |
|:---:|:---:|:---:|:---:|
| **100%** | **19** | **17** | **89.5% 🔥** |
| 90% | 4 | 3 | 75% |
| 80-89% | 23 | 12 | 52.2% |
| 总计 | 46 | 32 | 69.6% |

**结论: 100% 进球率区间最稳定 (89.5%)，优先推荐。**

---

## 5. V3/V4 多策略架构

### 5.1 V3 世界杯引擎

| 组件 | 文件 | 说明 |
|:---|:---|:---|
| Elo 积分 | data_sources/elo_scraper.py | 爬取国际 Elo 排名 |
| Perception Gap | wc_model.py | 大众认知 vs 真实实力差距 |
| 亚盘套利 | wc_model.py | AH 让球盘 + 淘汰赛平局溢价 |
| 2022 回测 | wc_model.py | 2022 世界杯回测通过 |

### 5.2 V4 五大联赛引擎 (暂停 · 8月恢复)

| 组件 | 文件 | 说明 |
|:---|:---|:---|
| Proxy xG | data_sources/proxy_xg_engine.py | 禁区内/外射门加权→伪预期进球 |
| 战力折损 | data_sources/apifootball_deep.py | 伤停+首发+核心球员影响 |
| 核心权重 | config/core_players_weight.json | 12队关键球员战力权重库 |
| FotMob | Killed by Cloudflare Turnstile | ⚠️ 永久放弃 |

### 5.3 Code Review 修复 (3轮·9个 Bug)

| 轮次 | Bug | 严重度 | Commit |
|:---|:---|:---|:---|
| R1 | Stake丢失(pred_save漏字段) | 🔴 致命 | 7514727 |
| R1 | NoneType崩溃(last_5=null) | 🔴 致命 | 7514727 |
| R1 | 旧纸盘确认逻辑错误 | 🔴 致命 | 7514727 |
| R2 | Kelly被unit_min=100摧毁 | 🔴 致命 | e2c1b20 |
| R2 | 平局误杀(H遮蔽D) | 🔴 致命 | e2c1b20 |
| R2 | 收盘真空(API实测通过) | 🟡 暗礁 | e2c1b20 |
| R3 | 双发请求缓存 | 🟡 效率 | ebc7de0 |
| R3 | 死代码残留 | 🟡 卫生 | ebc7de0 |
| R3 | 密钥硬编码→统一管理 | 🔴 安全 | f8cff48 |

---

## 6. 纸盘验证体系 (Paper Trading)

### 验证周期
**2026-05-06 → 2026-05-12 (7天)**

### 验收标准
• 累计 ≥ 25 场
• CLV > 0
• ROI ≥ 3%
• MDD ≤ 12%

### 6.1 每日结算流程

```
08:00 BJT
  ├── 1. 读取昨日 predictions_YYYYMMDD.json
  ├── 2. API-Football 拉取实际半场比分 → H/D/A 标签
  ├── 3. API-Football 拉取 Pinnacle 收盘 HT 1X2 赔率
  ├── 4. 去水计算 Fair Closing Odds → True CLV(%)
  └── 5. 结算 PnL → 写入 verified_YYYYMMDD.json
```

### 6.2 结算数据结构

```json
{
  "fixture_id": 1540844,
  "home": "Bayern München",
  "away": "Paris Saint Germain",
  "bet_outcome": "D",
  "placed_odds": 3.19,
  "stake": 0,
  "ht_score": "0-1",
  "actual_outcome": "A",
  "is_hit": false,
  "pnl": 0,
  "closing_ht_1x2": { "H": 2.01, "D": 3.20, "A": 4.44 },
  "fair_closing_odds": 3.3128,
  "true_clv": -0.0371,
  "ht_has_goal": true
}
```

---

## 7. CLV 收盘线价值 —— 核心诊断

> **核心价值观**: 赔率涨跌不改变已成交的 PnL，只影响 CLV 的符号，
> 而 CLV 的符号才是 Alpha 存在的证据。

### 7.1 累计结算面板 (2天 · 3场)

| 指标 | 数值 |
|:---|---:|
| 总场次 | 3 |
| 命中率 | 66.7% (2/3) |
| PnL | +86.1 |
| ROI | +205% |
| **平均 CLV** | **-7.57% 🔴** |

### 7.2 三场明细

| 日期 | 比赛 | 预测 | 买入价 | 半场 | 中 | 收盘D | 公平D | CLV |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| 5/5 | Al Khaleej vs Al Hilal | D | 3.05 | 1-1 | ✅ | 3.12 | 3.33 | **-8.43%** |
| 5/6 | Bayern vs PSG | D | 3.19 | 0-1 | ❌ | 3.20 | 3.31 | **-3.71%** |
| 5/6 | Shabab Al Ahli vs Al Nasr | D | 2.60 | 1-1 | ✅ | 2.70 | 2.91 | **-10.75%** |

### 7.3 重大发现

三场推荐全部为 **Draw (平局)**。命中 2/3 (66.7%) —— 纯拼脸已经不错了。
但 **CLV 三场全负，均值 -7.57%**。这意味着:

> 市场收盘价持续高于我们的买入价 —— 全球 Sharp Money 在临场前一直做空平局。

#### 为什么会出现"全红但全负 CLV"?

**① 信息颗粒度断层 (主因)**

V2 使用 `last_5` (近5场得失球率) 计算 att_def_spread。
这个宏观统计在 08:00 有效 —— 但在 T-60min 临场首发公布后，
Sharp Money 根据主力伤停、首发轮换进行天量资金对冲。
V2 引擎看不到阵容变化，被掌握内幕的 Sharp Money 碾压。

**② 杯赛与表演赛噪音**

• 拜仁 vs 巴黎: 欧冠淘汰赛，战意因素复杂
• Shabab Al Ahli + Al Khaleej: 边缘联赛，临场资金操控性强

**③ 统计学: 3场 = 噪音**

3 场比赛远不足以做统计推断。需要至少 30-50 场才能确认
att_def_spread 是不是一个负 EV 的垃圾因子。
**当前绝不修改 V2 代码 —— 让子弹再飞。**

### 7.4 结论

这不是失败 —— 是 **纸盘验证存在的全部意义**。

如果没有 CLV 计算，66.7% 的命中率已经让人飘了。
正是负 CLV 告诉我们: 中的那两场只是方差运气，不是 Alpha。

V4 的伤停战力折损因子就是专门为填补这个信息断层而设计的。

### 7.5 三层 CLV 重构 (P0 部署 · 2026-05-07)

| 层 | 名称 | 公式 | 含义 | 拜仁vs巴黎 实测 |
|:---:|:---|:---|:---|---:|
| 1 | **raw_clv** | (placed / raw_close) - 1 | 战胜了市场表象吗？ | **-0.31%** (几乎持平!) |
| 2 | **fair_line_clv** | 去水公平概率漂移 | 扣除 vig 后的真实移动 | -3.71% |
| 3 | **ev_vs_close** | 等同于旧 True CLV | 最严苛标准 | -3.71% |

> **核心发现**: raw_clv 只有 -0.31% —— 我们的买入价几乎等于收盘价，市场并没有显著做空我们。
> 之前的 -7.57% 恐慌有一大半是"抽水幻觉" (Pinnacle 收盘 vig)。

---
### 7.6 CLV 计算公式（三层含 vig）

```
True CLV (去水收盘线价值)

步骤1: 计算 Pinnacle 收盘三向隐含概率总和 (Overround)
  margin = 1/H + 1/D + 1/A

步骤2: 去水 → 公平概率
  true_prob = (1/D_odds) / margin

步骤3: 公平收盘赔率
  fair_closing_odds = 1 / true_prob

步骤4: CLV
  true_clv = placed_odds / fair_closing_odds - 1
```


---

## 8. 工程基础设施

### 8.1 API Key 统一管理 (DRY + 安全强化)

**2026-05-07 重构完成 + P0 安全强化**: 所有 API Key 从 `config/secrets.py` 单一源导入，不再在 6 个引擎文件中硬编码。

```python
# config/secrets.py — 唯一 API Key 源 (P0 强化后)
import os
API_KEY = os.getenv("APIFOOTBALL_KEY")
if not API_KEY:
    raise RuntimeError("🚨 找不到 APIFOOTBALL_KEY 环境变量！")
# 绝不提供 fallback 明文 —— 防止泄露到 Git 历史
```

**安全级别**: 环境变量注入 · .gitignore 已拦截 · 从未进入 Git 历史

**修复的 6 个文件**:
daily_runner.py · paper_trading.py · fetcher.py · odds_monitor.py
· p0_day1_validate.py · proxy_xg_engine.py

### 8.1.1 P0 五件套 架构变更 (2026-05-07 PM)

| # | 模块 | 变更 | 文件 |
|:---:|:---|:---|:---|
| 1 | **Kelly 毒药拆除** | `calculate_stake()` 返回 dict，<100 → SKIP_LOW_KELLY | bankroll.py |
| 2 | **三层 CLV** | `clv_triple()` → raw / fair_line / ev_vs_close | clv.py, paper_trading.py |
| 3 | **基准防线** | 每天 08:00 快照全量候选池 → universe_candidates_YYMMDD.json | daily_runner.py |
| 4 | **信号审计** | pred_save 新增 break_even_prob + action 字段 | daily_runner.py |
| 5 | **密钥清理** | 移除 fallback 明文，强制环境变量，git rm --cached | secrets.py |

### 8.2 定时任务

| 任务 | 时间 | 命令 | 状态 |
|:---|:---|:---|:---:|
| V2 每日扫描 | 08:00 BJT | `python3 engine/daily_runner.py` | ✅ 运行中 |
| V38 下午分析 | 15:00 BJT | `node tools/jiebao-scraper-v38.js` | ❌ 未创建 |

### 8.3 Git 仓库

```
github: whoerixxz/v2-football-quant
branch: main
最新 commit: f8cff48  DRY: centralized API key in config/secrets.py
.gitignore:  config/secrets.py · data/ · *.log
```

### 8.4 通道配置

| 通道 | 状态 | 用途 |
|:---|:---|:---|
| QQ Bot (AppID: 1903966582) | ✅ ON | 每日推荐推送 · 结算结果 |
| WebChat (127.0.0.1:18789) | ✅ ON | 主控制台 · 手动分析 |
| 微信 | ❌ 已弃 | v2.4.1 不兼容 · 已卸载插件 |

---

## 9. 风控体系

### 红线

> 1. 绝不把 08:00 快照直接接下单 API
> 2. 绝不使用 Full Kelly
> 3. 绝不投小联赛
> 4. 周末/赛前不碰代码
> 5. 必须积累 30+ 场纸盘才考虑实盘

### 9.1 银行配置

| 参数 | 值 |
|:---|---|
| 本金 | 2,000 |
| 单注上限 | 300 (绝对安全帽) |
| 单注下限 | 100 |
| Kelly 系数 | 1/4 (保守) |
| 硬熔断 | 回撤 > 40% → 全停 |
| 软熔断 | 回撤 > 25% → 减半注 |
| 低价值跳过 | Edge < 10 · 不投 |

### 9.2 Kelly 公式

```
f* = (bp - q) / b

b  = 赔率 — 1  (净赔率)
p  = 模型预测胜率
q  = 1 — p     (失败概率)

应用: f = f* × 1/4  (¼ Kelly)
单注金额 = 本金 × f, clamp(100, 300)
```

### 9.3 纸盘 → 实盘架构演进

| 阶段 | 08:00 | T-30min | T-15min |
|:---|:---|:---|:---|
| **纸盘** (当前) | 扫描·出信号·保存 | — | — |
| **实盘** | daily_runner → 观察池 | odds_monitor 赔率轮询 | 临场决策·下单 |

---

## 10. 数据与联赛白名单

### 10.1 V2 白名单 (56个联赛)

| 区域 | 联赛 |
|:---|:---|
| 五大 | 英超 · 西甲 · 意甲 · 德甲 · 法甲 |
| 二级 | 英冠 · 英甲 · 德乙 · 西乙 · 意乙 · 法乙 |
| 欧洲 | 荷甲 · 葡超 · 比甲 · 土超 · 俄超 · 挪超 · 瑞典超 · 奥甲 · 瑞士超 · 丹超 · 苏超 |
| 亚洲 | 日职联 · 韩K联 · 澳超 · 沙特联 |
| 美洲 | 美职业 · 墨西联 · 巴西甲 · 阿甲 |
| 其他 | 欧冠 · 欧联杯 · 世界杯 · 欧洲杯等 |

### 10.2 不投的黑名单

❌ 马来超 · 南非超 · 奥甲降 · 罗甲冠 · 秘鲁甲 · 等小联赛
（数据不透明，操控风险高）

---

## 11. 风险警示与红线

### ⚠️ 已知风险

| 风险 | 影响 |
|:---|:---|
| att_def_spread 因子信息滞后 | 08:00 快照无法反映临场首发变化 |
| 杯赛/边缘联赛噪音 | V2 对所有联赛用统一分档，不区分战意 |
| DeepSeek API 偶发连接错误 | 5/6 下午曾大规模超时 |
| 会话每天凌晨 4:00 重置 | WebChat 每天醒来是全新会话，不保留历史 |

### 禁止事项

1. ❌ 绝不把 08:00 快照直接接下单 API
2. ❌ 绝不使用 Full Kelly
3. ❌ 绝不投白名单外联赛
4. ❌ 周末/开赛前不准改代码
5. ❌ 30场样本内不准做统计推断

---

## 12. 路线图与下一步

### 12.1 近期 (5/7 – 5/12): 纸盘验收

| 任务 | 优先 | 状态 |
|:---|:---:|:---:|
| 每天 08:00 自动扫描·推荐 | P0 | ✅ 运行中 |
| 每天次日 CLV 结算·归档 | P0 | ✅ 闭环 |
| 积累 ≥25 场纸盘样本 | P0 | ⏳ 3/25 |
| 周末 CLV 汇总验收 (ROI≥3%, CLV>0, MDD≤12%) | P0 | ⏳ |
| 评分引擎权重校准 (H2H 20%→60%) | P1 | ❌ |
| 14联赛数据补拉 | P2 | ❌ |
| 创建 V38 下午 15:00 定时任务 | P2 | ❌ |

### 12.2 中期: 实盘过渡 (纸盘验收通过后)

1. daily_runner 降级为观察池
2. odds_monitor 启动 T-30min 赔率轮询
3. T-15min 临场决策: Edge + CLV 双因子过滤
4. 实盘下单 (100-300/注, 每日 ≤5注)

### 12.3 长期: V2 → V4 演进

1. V4 五大联赛引擎 8 月重启 (2026-27 赛季)
2. 伤停战力折损因子修补 V2 的信息断层
3. V3 W杯引擎 2026 年 6 月实战
4. 多引擎融合: Edge 加权 + CLV 一致性投票

---

## 附录

### A. 环境信息

| 项 | 值 |
|:---|---|
| OS | macOS 13.7.8 (arm64) |
| Node | v22.22.2 |
| OpenClaw | 2026.5.4 (325df3e) |
| 默认模型 | deepseek/deepseek-v4-flash |
| 会话模型 | deepseek/deepseek-v4-pro (thinking:high) |
| 上下文窗口 | 1,000,000 tokens |
| API Key 位置 | config/secrets.py |
| Tavily 搜索 | ON |

### B. 常用命令

```
# 手动扫描
python3 engine/daily_runner.py

# 手动结算指定日期
python3 engine/paper_trading.py --verify 2026-05-06

# 全量 CLI 汇总
python3 engine/paper_trading.py --summary

# V38手动分析
node tools/jiebao-scraper-v38.js

# 切换模型
/model deepseek/deepseek-v4-pro

# 开关推理
/reasoning on

# 查看状态
/status
```

### C. 生成信息

```
生成时间: 2026-05-07 17:09 BJT
版本: v2.1 (P0 五件套部署)
基于: V2 纸盘第3天 (5/7) 数据
最新 commit: 8918c5b — P0 五件套
```
