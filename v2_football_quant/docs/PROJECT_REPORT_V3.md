# V3 世界杯/大赛引擎 — Perception Gap 狙击系统

**一句话定位：** 专为 2026 世界杯设计的大赛策略引擎，利用 Elo 积分与身价偏差（Perception Gap）捕捉市场情绪偏见。

---

## 核心策略与模型

### 模型架构

基于 Elo 积分系统的国家队实力评估引擎，覆盖 2018/2022 世界杯、2020/2024 欧洲杯共四届大赛 88 场数据。

**核心公式：**
```
Perception Gap = log(全队身价比) - log(Elo 比)
```

- **身价** — Transfermarkt 全队总身价，代表公众认知/热度
- **Elo 积分** — eloratings.net 基准胜率，代表真实实力
- **Gap > 0** = 身价高于 Elo 预期（偏高估，泡沫区）
- **Gap < 0** = 身价低于 Elo 预期（低估，价值洼地）

### 三大策略

| 策略 | 场景 | 动作 |
|:---|:---|:---|
| **V3_PERCEPTION_GAP_SNIPER** | Gap > 1.0（极度泡沫区） | 下盘不败，平赔 4-6x |
| 策略 B（淘汰赛平局） | 双方主帅保守指数均 ≥ 7 | 全场/半场平局 |
| 策略 C（小组赛末轮默契球） | 小组第三轮 | 概率强制修正 |

**发现：** Gap > 1.0 的极度泡沫区，下盘不败率达 33.3%，但赔率回报丰厚（平赔 4-6x）。

### 状态管理

- **赛季隔离机制：** 非大赛季自动 `SKIP_OFF_SEASON`
- 当前（2026-05-13）：处于 **Season Wait** 状态

---

## 架构与文件清单

| 文件 | 行数 | 职责 |
|:---|:---:|:---|
| `engine/wc_model.py` | 265 | W 杯 Elo 模型，Perception Gap 计算引擎 |
| `engine/data_sources/elo_scraper.py` | 86 | Elo 积分爬虫（eloratings.net） |
| `engine/data_sources/proxy_xg_engine.py` | 125 | 伪 xG 引擎（大赛缺少高质量 xG 数据的替代方案） |
| `engine/data_sources/apifootball_deep.py` | 264 | API-Football 深挖（伤停+首发+战力折损） |
| `config/core_players_weight.json` | — | 12 队核心球员权重（首发折损量化） |
| `config/v3_thresholds.json` | — | V3 开枪红线配置（Gap 阈值等） |
| `config/fair_odds_matrix_top5_v2.json` | — | 五大联赛公平赔率矩阵（V3 部分引用） |

**总计：约 740 行**

---

## Cron 任务表

V3 当前处于赛季隔离状态，无活跃 Cron 任务。待 2026 世界杯临近时启用。

---

## 关键数据与验证结果

### 测试验证
- **英 vs 日 模拟：** BUY Japan AH+1.25 通过测试
- **三轮 Code Review：** 共修复 9 个 Bug
- Phase 3 已完成，引擎核心功能验证通过

### 核心发现
- 极度泡沫区（Gap > 1.0）：下盘不败率 33.3%，平赔 4-6x
- 身价比 + Elo 比双因子相比单一 Elo 模型，信号更早、更稳定
- 主帅保守指数作为淘汰赛平局信号，与 Perception Gap 互补

---

## 当前状态

**Phase 3 — 完成 ✅**
- W 杯引擎核心（Elo + Perception Gap）开发完成并测试通过
- 三轮 Code Review 完成，9 个 Bug 已修复
- 模拟交易验证（英 vs 日）通过

**Phase 2B（FotMob）— 已废弃 ❌**
- 被 Cloudflare Turnstile 拦截，Kill 决策

**Phase 4（V4 五大联赛）— Paused until Aug**
- 当前资源集中在 V4 赛前情报系统

**当前状态：Season Wait** — 等待 2026 世界杯临近时激活。

---

## 已知问题 / 待办

- 大赛数据仅覆盖 88 场（4 届大赛），样本量偏小 → 临赛前需追加更多历史大赛数据
- 主帅保守指数目前为人工标注 → 需制定客观量化标准
- Perceptron Gap 应用场景受限于大赛（非大赛季 SKIP）
- Phase 2B 被 Cloudflare 封锁后，FotMob 数据源无替代方案
- 需提前 3 个月启动热身（数据重新采集 + 引擎热更新 + 模拟盘验证）
