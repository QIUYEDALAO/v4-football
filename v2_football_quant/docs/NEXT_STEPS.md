# ⚽ V2-V4 量化系统 — 下一步开发计划书

> 制定日期：2026-05-06 23:00  
> 资金：2000 本金 | 单注 100-300 | Kelly 1/6  
> 通道：QQ Bot 推送 | GitHub: whoerixxz/v2-football-quant  
> 状态：V2 纸盘验证中（第1天/共7天）

---

## 零、当前进度快照

| 维度 | 状态 |
|:---|:--:|
| V2 daily_runner | ✅ 8:00 Cron → QQ Bot 推送 |
| V2 paper_trading | ✅ CLV 引擎 + 赛后结算 |
| 5/5 首场结算 | ✅ Al Khaleej HT 1-1 · PnL +86.1u · CLV -8.43% |
| 5/6 推荐 2 场 | ✅ 拜仁vs巴黎 + 阿联酋超，5/7凌晨开打 |
| 代码质量 | ✅ 6 bug 已修 · 代码冻结 |
| bankroll | ✅ 纯 Kelly · 无 hard limit |
| memory | ✅ memory-core + memory-wiki |
| 数据管道 | ⚠️ FotMob/Understat/FBref 被反爬 |
| API-Football 深挖 | ✅ lineups + injuries + player stats 可用 |

---

## 一、即日（5/6 - 5/7）：跑完首次结算

**不需要写代码，系统自动运行。**

| 时间 | 事件 |
|:---|:---|
| 5/7 凌晨 | 拜仁 vs PSG + Shabab Al Ahli 开打 |
| 5/7 08:00 | daily_runner 自动拉取新比赛 + 自动结算昨日两场 |
| 5/7 08:01 | QQ Bot 推送结算结果 |

---

## 二、本周（5/7 - 5/12）：完成纸盘验证

**目标：积累 ≥25 场推荐，CLV > 0 占比 > 50%**

| 任务 | 预估时间 | 说明 |
|:---|:--:|:---|
| 2.1 观察 Cron 稳定性 | 每日监控 | 确认 8:00 准时跑，QQ 准时推 |
| 2.2 更新 P0-P2-TRACKER | 0.5h | 同步最新状态、策略切换记录 |
| 2.3 手动处理 CLV 缺失 | 按需 | 如果 API 赛后不给 closing odds，用赛前快照替代 |
| 2.4 写 7 天纸盘总结报告 | 5/12 | `--summary` 全量 CLV 分桶 + ROI |

**这一周的核心纪律：不动生产代码。只观察，只记录。**

---

## 三、V3 世界杯模型（5/13 - 5/25）

**目标：11 月世界杯开赛前，模型回测通过**

### 3.1 数据准备（5/13 - 5/15）

| 任务 | 来源 | 说明 |
|:---|:---|:---|
| 国家队 Elo 积分 | eloratings.net 爬取 | 历史 Elo + 动态更新 |
| 32 强全队身价 | Transfermarkt 爬取 | 构建 Perception Gap 因子 |
| 主帅保守指数 | 人工标注 | 1-10 量表，基于历史大赛风格 |
| 2018/2022 W杯历史 | API-Football | 比赛结果 + 赔率 |

### 3.2 特征构建（5/16 - 5/18）

> 文件：`engine/wc_model.py`

```
Input:
  Elo_home, Elo_away        → Elo Diff → Base Win Probability
  MarketValue_home/away     → Perception Gap (= EloRank - ValueRank)
  Manager_Conservative       → 1-10 标签
  
Output:
  Strategy A: Underdog AH +1.25/+1.5 (Perception Gap > 阈值)
  Strategy B: FT/HT Draw (淘汰赛 + 双保守主帅)
  Strategy C: 小组赛第三轮博弈修正
```

### 3.3 回测（5/19 - 5/25）

| 任务 | 说明 |
|:---|:---|
| 2018 世界杯 64 场回测 | 用 Elo+身价模型模拟投注 |
| 2022 世界杯 64 场回测 | 同上 |
| CLV 评估 | 如果能拿到历史收盘赔率 |
| 命中率 + ROI | 最低门槛：>50% 命中·ROI>0 |

---

## 四、V4 五大联赛进阶模型（5/13 - 6/15）

**目标：为 2026/27 赛季准备 xG 驱动的定价模型**

### 4.1 数据管道建设（5/13 - 5/20）

| 阶段 | 数据源 | 方案 | 产出 |
|:---|:---|:---|:---|
| A | Understat | requests + regex（需绕过 SPA） | xG/xGA/PPDA 历史库 |
| B | FBref | Selenium + CSV 下载 | 完整进阶数据 |
| C | FotMob | 逆向 `matchDetails` API | 实时 xG + 首发 |
| D | API-Football | 现有订阅 | 伤停 + 赛程 + 赔率 |

**优先顺序：D(已有) → A(最易) → C(最值) → B(最全)**

### 4.2 因子开发（5/21 - 5/31）

> 文件：`engine/v4_factors.py`

| 因子 | 公式 | 权重 |
|:---|:---|:--:|
| xG 均值回归 | `(xG - actual_goals) / games` | 40% |
| PPDA 压制差 | `ppda_home - ppda_away` | 25% |
| 伤停折损 | `Σ(core_player_weight × is_injured)` | 20% |
| 赛季阶段 | 前8/中段/后8 分桶 | 15% |

### 4.3 回测（6/1 - 6/15）

| 联赛 | 赛季 | 场次 |
|:---|:---|:--:|
| 英超 | 2024/25 | 380场 |
| 西甲 | 2024/25 | 380场 |
| 德甲 | 2024/25 | 306场 |
| 意甲 | 2024/25 | 380场 |
| 法甲 | 2024/25 | 306场 |

---

## 五、策略路由架构（5/13 - 5/20）

**目标：重构成多策略统一入口**

```
                    daily_runner.py（每天 8:00）
                           │
                    ┌──────┴──────┐
                    │  Strategy   │
                    │  Router     │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ V2       │    │ V3       │    │ V4       │
    │ HT Draw  │    │ WC Model │    │ xG Model │
    │ (日常)   │    │ (杯赛)   │    │ (五大)   │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
                  ┌──────────┐
                  │ Kelly    │
                  │ Sizing   │
                  └──────────┘
```

**实现文件**：`engine/strategy_router.py`（~100行）

```python
def route(fixture):
    if fixture.league in WORLD_CUP_LEAGUES:
        return wc_model.evaluate(fixture)
    elif fixture.league in TOP_5_LEAGUES:
        if v4_factors.xg_available(fixture):
            return v4_model.evaluate(fixture)
        else:
            return v2_model.evaluate(fixture)  # fallback
    else:
        return v2_model.evaluate(fixture)       # 冷门联赛 V2 收割
```

---

## 六、时间线总览

```
5/6  ─┬─ 纸盘 Day 1·代码冻结
      │
5/7  ─┼─ 首次自动结算（拜仁vs巴黎）
      │
5/12 ─┼─ 纸盘 7 天完成 → 决策：切盘/继续
      │
5/13 ─┼─ 策略路由框架 + 免费数据管道建设
      │  ├─ FotMob 逆向工程（第一阶段）
      │  ├─ Understat 数据采集
      │  ├─ V3 世界杯 Elo 数据准备
      │  └─ API-Football 伤停模块接入
      │
5/20 ─┼─ 策略路由上线 + V4 因子 v0.1
      │
5/25 ─┼─ V3 世界杯回测完成
      │
6/15 ─┼─ V4 五大联赛回测完成
      │
7-10 ─┼─ 休赛期打磨 + 实盘准备
      │
11月  ─┴─ 🏆 世界杯实盘
```

---

## 七、关键决策节点

| 时间 | 决策 | 条件 |
|:---|:---|:---|
| 5/12 | V2 切盘 | CLV>0 & ROI≥3% & MDD≤12% |
| 5/15 | 数据管道选型 | 哪个免费源最先打通 |
| 5/25 | V3 是否投钱 | 回测 ROI > 0 |
| 6/15 | V4 是否投钱 | 回测 ROI > 3% & CLV > 0 |

---

## 八、预算

| 项目 | 月费 | 说明 |
|:---|:--:|:---|
| API-Football Pro | $19 | 赛程+赔率+伤停+首发 |
| DeepSeek API | ~$5 | V4-Pro 重型分析 |
| 其余数据源 | $0 | FotMob/Understat/FBref 全免费 |
| **合计** | **$24/月** | |

---

> 💡 **一句话总结**：本周只观察不写码 → 5/13 启动策略路由 + 免费数据管道 → 6 月前 V3/V4 回测完成 → 休赛期打磨 → 11 月世界杯亮剑
