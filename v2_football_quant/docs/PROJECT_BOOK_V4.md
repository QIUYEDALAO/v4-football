# ⚽ V4 因子勘探引擎 — 功能与运行逻辑完整报告 v1.1

> 生成时间：2026-05-10  
> 代码仓库：`v2_football_quant/`  
> 核心文件：`h2h_engine.py` · `v4_runner.py` · `strategy_router.py` · `paper_trading.py`

---

## 一、项目定位

V4 不是独立武器，而是 **V2 HT 1X2 引擎的侦察兵和瞄准镜**。

```
V2（主力）        → 赛前静态盘口套利（HT 1X2 平局错杀）
V3（大赛）        → 世界杯 Elo + Perception Gap 狙击
V4（侦察兵）      → 低门槛蓄水 → CLV 审判 → 达标的联赛×市场组合注入 V2
V5（待建）        → 接收 V4 滚球雷达池 → In-Play 时间衰减狙击
```

核心哲学：**放宽门槛疯狂蓄水 → Pandas 冷血切片 → 选中的组合升级为 V2 辅助因子。** V4 从"一票否决/一票通过"的暴君，降级为提供弹药的参谋。

---

## 二、系统架构全景

```
┌──────────────────────────────────────────────────────────┐
│                    v4_runner.py                           │
│  日频扫描器 · 每天独立运行 · 不与 daily_runner 冲突       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. fetch_today_fixtures()                                │
│     └── 白名单联赛 ∩ 12h内开赛 (前置漏斗)                 │
│                                                          │
│  2. evaluate_h2h_edge() × 逐场                            │
│     ├── 🔪 锁1: 2020年时间窗口                            │
│     ├── 规则: HT有球率 ≥ 70% + 0-0 ≤ 2                  │
│     ├── ⏱ 进球时间分桶 (time_bins)                       │
│     └── 🔪 锁2: (主近5 + 客近5) / 2 ≥ 70%                │
│                                                          │
│  3. 盘口获取 (三层优先级)                                  │
│     ├── 🟢 Priority 1: HT Over 1.0 ≥ 1.60 → optimal     │
│     ├── 🟡 Priority 2: HT Over 0.5 ≥ 1.25 → degraded    │
│     └── 🎯 探测 ≥1.5线 → V4_HT_LIVE_STANDBY 滚球池     │
│                                                          │
│  4. StrategyRouter.process_signals()                     │
│     └── 🚧 V4 物理断路器: startswith("V4") → OBSERVE    │
│                                                          │
│  5. 输出分流                                              │
│     ├── predictions_v4_YYYYMMDD.json  → 赛前收录         │
│     └── live_watchlist_YYYYMMDD.json  → 滚球雷达池       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 文件职责矩阵

| 文件 | 职责 | 关键函数 |
|:---|:---|:---|
| `engine/data_sources/h2h_engine.py` | H2H 多维画像引擎 | `evaluate_h2h_edge()` |
| `engine/v4_runner.py` | V4 日频扫描器 | `run_v4_scan()` |
| `engine/strategy_router.py` | 多策略路由总控 | `process_signals()` — V4 物理断路器 |
| `engine/paper_trading.py` | 结算 + Pandas 多维审计 | `v4_factor_audit()` + A/B 面板 |
| `engine/bankroll.py` | 仓位管理 | Kelly 1/4 + 阶梯熔断 |
| `engine/live_bridge.py` | 纸盘→实盘网关 | 三级准入 + Kill-Switch |

---

## 三、三重硬锁详解

### 🔪 锁1：2020 年时间红线

```python
H2H_YEAR_CUTOFF = 2020  # 固定锚点，不滑动
cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
```

**逻辑**：只取 2020 年及之后的交锋记录。2020 年前的足球生态（疫情前战术、范佩西时代阵容）与当下完全无关。

**不达标准则**：2020 年以来 H2H < 3 场 → 直接抛弃。

**效果**：费耶诺德 vs 阿尔克马尔（34场总H2H，但仅部分在2020+）不会被2010年数据污染。

### 🔪 锁2：近期动能门

```python
recent_form_avg = (home_recent_ht_over + away_recent_ht_over) / 2
if recent_form_avg < 0.7: REJECT
```

**逻辑**：历史基因必须由近期动能激活。H2H 再漂亮，近期两队都不进球就是纸上富贵。

**数据源**：API-Football `fixtures?team={id}&last=5&status=FT`，各查 5 场完赛记录。

### 🔪 锁3：盘口锚定 + 降级采集

```
Priority 1: HT Over 1.0 ≥ 1.60  →  optimal（不进=走水保本）
Priority 2: HT Over 0.5 ≥ 1.25  →  degraded（降级采集，标记原因）
探测层:   HT Over ≥ 1.5          →  V4_HT_LIVE_STANDBY（赛前买不起，潜伏等降）
```

**核心原则**：
- 绝对不碰 .25 或 .75 的半边盘口（进1.25个球的概率算不出来）
- HT Over 1.0 是完美容错线：进0=输全，进1=走水保本，进2=赢全
- HT Over 0.5 降级时放宽底线到 1.25（而非 1.60），记录真实低水位供 CLV 审判

---

## 四、双轨输出结构

### 4.1 赛前收录信号

```json
{
  "fixture_id": 1379328,
  "strategy_id": "V4_FACTOR_EXPLORE",
  "market": "HT_OU",
  "line": 1.0,
  "placed_odds": 1.68,
  "placed_opp_odds": 2.20,
  "line_quality": "optimal",
  "strategy_note": null,
  "factors": {
    "h2h_ht_goal_rate": 0.90,
    "h2h_sample_size": 10,
    "h2h_total": 32,
    "h2h_3y_count": 14,
    "h2h_expired": 18,
    "ft_0_0_count": 1,
    "time_bins": {"0_15": 0.30, "16_30": 0.30, "31_45": 0.60},
    "home_recent_ht_over": 0.60,
    "away_recent_ht_over": 1.00,
    "recent_form_avg": 0.80
  },
  "action": "OBSERVE_ONLY",
  "weight_in_model": 0.20,
  "paper_trade_only": true
}
```

### 4.2 滚球雷达信号

```json
{
  "fixture_id": 1387992,
  "strategy_id": "V4_HT_LIVE_STANDBY",
  "action": "OBSERVE_ONLY",
  "market": "HT_OU",
  "current_line": 1.5,
  "current_odds": 1.93,
  "current_under": 1.88,
  "target_line": 1.0,
  "entry_window": "15-25 min",
  "time_bin_hotspot": "31_45分钟",
  "skip_reason": "早盘线过高(开1.5)，等待时间衰减至1.0后狙击",
  "factors": { ... }
}
```

---

## 五、四层防线中的 V4 位置

### 物理级断路器（永不解除）

```python
# strategy_router.py: process_signals()
if strategy_id.startswith("V4"):
    signal["action"] = "OBSERVE_ONLY"
    signal["max_risk_units"] = 0.0
    signal["leverage_boost"] = 0.0
    signal["skip_reason"] = "[GUARD] V4 为子因子引擎，严禁直接触碰实盘资金。"
    return signal
```

**含义**：任何带有 `V4` 前缀的信号，无论外层配置如何，风险强制归零。V4 只能做数据采集，只能通过 V2 间接影响实盘。

---

## 六、Pandas 多维切片审计系统

### 触发方式
```bash
python3 engine/paper_trading.py --v4-audit
```

### 四大审计维度

**维度一：联赛 × 盘口 交叉审计**
```
League (联赛)      Market    N     Hit%   AvgCLV   Verdict
荷甲              HT_OU_0.5 32/28  81%   +1.82%   🟢 TIER_1_CORE
英超              HT_OU_1.0 45/40  68%   -0.52%   🟡 AUX_FILTER
法甲              HT_OU_0.5 32/28  72%   -0.85%   🟠 NOISY
西甲              HT_OU_0.5 15/12  58%   -3.20%   🔴 DROP_ZONE
意甲              HT_OU_0.5 12/8   75%   +1.10%   ⚪ INCUBATING
```

**维度二：仅联赛汇总** — 各联赛的样本量、平均HT率、覆盖盘口数

**维度三：HT有球率分布画像** — 70-79% / 80-89% / 90-100% 分桶

**维度四：A/B 策略分流审计**
```
[实验组 A] 早盘直打 HT Over 1.0: N场 → 赛前即满足，直接收录
[实验组 B] 潜伏等降 HT Over 1.0: N场 → 赛前大1.5+，等15-25分钟衰减
```
预期：实验组 B 的 MDD 远低于 A（进1球=走水保本，顶级进攻球队极少0-0）

### Tier 分级规则（CLV 唯一真神）

| Tier | 条件 | 行动 |
|:---|:---|:---|
| 🟢 **TIER_1_CORE** | N≥30, CLV≥+1.0% | 嵌入 V2 评分引擎，权重 0.6-0.8 |
| 🟡 **AUX_FILTER** | N≥30, CLV 0%~1.0% | 辅助过滤层，权重 0.2-0.3 |
| 🟠 **NOISY** | N≥30, Hit%≥70% 但 CLV<0% | **高命中率陷阱，严禁上车** |
| 🔴 **DROP_ZONE** | N≥30, CLV<-2.0% | 暂停该市场 |
| ⚪ **INCUBATING** | N<30 | 继续蓄水 |

### V2 ∩ V4 叠加增益 A/B 面板（在 `--summary` 中自动输出）

```
🔬 V2 引擎叠加 V4 过滤效能审计 (A/B Test)

 [基准] V2 原始决策集:
   👉 N=150 | CLV: -2.50% | MDD: -2700 | 状态: ❌ 负期望 (ICU)

 [实验] V2 决策集 ∩ V4 过滤 (H2H HT≥70%):
   👉 N=45  | CLV: +1.20% | MDD: -360  | 状态: 🔥 提取出纯净 Alpha！
```

若实验组 CLV 持平或低于基准 → V4 参谋提供的是假情报 → 废弃。

---

## 七、与 V2 的协同升级路径

### 当前 (v1.0)：平行勘探
```
V2 daily_runner → 独立产出推荐 → QQ Bot 推送
V4 v4_runner    → 独立纸盘记录 → 静默蓄水
                     (互不干扰)
```

### 未来 (v2.0)：权重融合
```
V2 scoring 引擎 = {
    h2h_ht_goal_rate: 0.20,      ← 原始
    V4_TIER1_factor:  0.20,      ← 🆕 TIER_1_CORE 联赛×市场
    recent_form:      0.20,
    league_factor:    0.20,
    head_to_head:     0.20,
}
```

### V4 对 V2 推荐的实际增强
```
🔥🔥 阿贾克斯 vs 费耶诺德 | HT Draw @3.05
    ├── V2 综合评分: 82/100
    ├── V4 辅助信号: ✅ HT有球率 85% (🇳🇱荷甲 TIER_1: 81%命中)
    └── 双重确认 → 提升信心等级
```

---

## 八、运行管线

### 日频扫描
```bash
python3 engine/v4_runner.py
python3 engine/v4_runner.py --run_tag=AM0800   # 早盘
python3 engine/v4_runner.py --run_tag=PM1600   # 傍晚
```

### 因子体检
```bash
# N≥30 场后运行
python3 engine/paper_trading.py --v4-audit
```

### 完整 A/B 审计
```bash
python3 engine/paper_trading.py --summary
# 自动输出 V2∩V4 叠加增益面板 + 四层防线体检单
```

### Cron 调度（建议）
```
08:00 BJT → V2每日扫描 (daily_runner --AM0800)
08:05 BJT → V4勘探线扫描 (v4_runner --AM0800)
09:00 BJT → V2每日结算 (paper_trading --verify-yesterday)
12:00 BJT → V2影子扫描-午间
16:00 BJT → V2影子扫描-傍晚
16:05 BJT → V4勘探线扫描 (v4_runner --PM1600)
```

---

## 九、状态机与数据流

```
┌──────────┐    ┌──────────────┐    ┌─────────────────┐
│ API奥运  │ →  │ h2h_engine   │ →  │ 三重锁过滤      │
│ 7500次/天│    │ 多维画像     │    │ 2020窗+动能+盘口│
└──────────┘    └──────────────┘    └───────┬─────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                  ▼
                    ┌──────────┐    ┌────────────┐    ┌──────────────┐
                    │ optimal  │    │ degraded   │    │ live_standby │
                    │ HT 1.0   │    │ HT 0.5     │    │ wait 1.5↓1.0 │
                    │ ≥1.60    │    │ ≥1.25      │    │ 15-25 min    │
                    └────┬─────┘    └─────┬──────┘    └──────┬───────┘
                         │               │                   │
                         └───────┬───────┘                   │
                                 ▼                           ▼
                    ┌──────────────────┐        ┌──────────────────┐
                    │ predictions_v4   │        │ live_watchlist   │
                    │ _YYYYMMDD.json   │        │ _YYYYMMDD.json   │
                    └────────┬─────────┘        └──────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ paper_trading    │
                    │ --v4-audit       │
                    │ Pandas groupby   │
                    │ Tier 分级        │
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    ▼                  ▼
             ┌────────────┐   ┌──────────────┐
             │ TIER_1 →   │   │ DROP/NOISY → │
             │ 注入 V2     │   │ 废弃/暂停     │
             └────────────┘   └──────────────┘
```

---

## 十、技术栈

| 组件 | 技术 | 文件 |
|:---|:---|:---|
| 数据源 | API-Football Pro (7500次/天) | `config/secrets.py` |
| H2H 引擎 | Python 3 + urllib | `engine/data_sources/h2h_engine.py` |
| 日频扫描 | v4_runner.py (独立进程) | `engine/v4_runner.py` |
| 策略路由 | StrategyRouter.process_signals() | `engine/strategy_router.py` |
| 多维审计 | Pandas 2.3.3 groupby | `engine/paper_trading.py --v4-audit` |
| A/B 测试 | V2∩V4 叠加增益面板 | `engine/paper_trading.py --summary` |
| 网络层 | urllib + certifi SSL | `engine/net_utils.py` |
| 存储 | JSON | `data/daily_reports/` |
| 仓位 | Kelly 1/4 + 阶梯熔断 | `engine/bankroll.py` |
| 实盘网关 | 三级准入 + Kill-Switch | `engine/live_bridge.py` |

---

## 十一、关键设计决策

| # | 决策 | 日期 | 理由 |
|:---:|:---|:---|:---|
| 1 | market FT_OU_2.5 → HT_OU_0.5 → HT_OU_1.0 | 05-10 | 因子是 HT 有球，盘口必须对齐；1.0 是完美容错线 |
| 2 | 时间窗：3年滑动 → 2020 固定锚 | 05-10 | 疫情前足球生态完全不同，固定锚点不漂移 |
| 3 | 门槛 80% → 70% | 05-10 | V4 定位是"蓄水"而非"精准"，宽进严出 |
| 4 | V4 降级为"参谋"角色 | 05-10 | 单因子模型不应一票否决 V2 的多维决策 |
| 5 | Pandas groupby 替代手工审计 | 05-10 | 自动化多维切片 → Tier 分级 → 冷血客观 |
| 6 | V4 物理断路器焊死 | 05-10 | startswith("V4") → max_risk_units=0，永不解除 |
| 7 | CLV 唯一真神 + NOISY 陷阱层 | 05-10 | Hit% ≥70% 但 CLV<0 → 庄家早已洞察，严禁上车 |
| 8 | 滚球雷达 V4_HT_LIVE_STANDBY | 05-10 | 赛前高开不能买 → 不扔 → 存进冰柜等时间衰减 |
| 9 | HT 0.5 降级采集底线 1.25 | 05-10 | 1.60 在 0.5 线上是庄家钓鱼盘，1.25 才是真实防线 |

---

> 📌 **核心记忆点**：V4 = 2020锚点时间窗 → 低门槛蓄水(70%) → 三重锁过滤 → Pandas 冷血切片 → CLV 真神审判 → TIER_1_CORE 注入 V2 评分引擎。
>
> **V4 不是武器，是 V2 的瞄准镜。NDR (No Direct Risk) — 永不触碰实盘资金。**
