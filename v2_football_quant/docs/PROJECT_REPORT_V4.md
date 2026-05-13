# V4 HT 赛前情报推荐系统 — 上半场进球基因引擎

**一句话定位：** 纯情报型上半场推荐引擎。不投注、只判断比赛 HT 进球基因，A/B/C/SKIP 四级分级，赛后自动验证。

---

## 核心策略

### HT_PREMATCH_RECOMMEND — 上半场进球基因判断

不负责投注决策，只回答一个问题：**这场比赛的上半场有多大可能出现进球？**

**推荐分级逻辑（四档）：**

| 等级 | 核心条件 | 显示标签 |
|:---|:---|:---|
| **A 级** | HT ≥ 70, H2H ≥ 65%, recent ≥ 70%, attack ≥ 70%, 11-45min ≥ 55% | 上半场强推荐 🔥 |
| **B 级** | HT ≥ 60, H2H ≥ 55%, recent ≥ 60%, attack ≥ 60%, 11-45min ≥ 45% | 上半场达标推荐 |
| **C 级** | HT ≥ 50 | 仅情报观察 |
| **SKIP** | 不满足以上条件 | 上半场基因不足 |

### 因子体系

| 因子 | 来源 | 权重 |
|:---|:---|:---:|
| **H2H（历史交锋）** | H2H 引擎，近 N 场交锋 HT 进球率 | 主因子 |
| **HT（上半场基因）** | 多维度综合评分 | 主因子 |
| **recent（近期状态）** | 近 5 场 HT 进球率 | 辅因子 |
| **attack（进攻火力）** | 球队赛季场均进球、xG | 辅因子 |
| **time_bins（时间分布）** | 0-15/16-30/31-45 进球时段分布 | 形态因子 |

### 赛后验证

每日自动对比预测 vs 赛果，计算 A+B 命中率、C 级命中率，反馈至仪表盘。

---

## 架构与文件清单

| 文件 | 行数 | 职责 |
|:---|:---:|:---|
| `engine/v4_runner.py` | 699 | V4 球探扫描器，拉 fixtures + H2H + odds，纯情报模式 |
| `engine/v4_dashboard.py` | 1,174 | 交互式 HTML 情报台，日期切换，A/B/C/SKIP 分级展示 |
| `engine/v4_match_intelligence.py` | 401 | HT 推荐引擎（build_ht_recommendation），A/B/C/SKIP 分级 |
| `engine/v4_ht_result_validator.py` | 207 | 赛后验证器，拉赛果对比预测 |
| `engine/v4_scout_report.py` | 525 | 战术指挥面板 / 卡片渲染 |
| `engine/data_sources/h2h_engine.py` | 660 | H2H 引擎，进球事件解析，time_bins |

**总计：约 3,666 行**

### 辅助组件
- `engine/v4_data_logger.py`（31 行）— 数据落盘
- `engine/v4_job_runner.py`（114 行）— 作业调度
- `engine/v4_strategy_eval.py`（185 行）— 策略评估
- `engine/context_enrichment.py`（55 行）— 场次富化
- `engine/team_cn_map.json` + `engine/team_cn_map.py` — 球队中文名映射

---

## Cron 任务表

| 时间 | 脚本 | 用途 |
|:---|:---|:---|
| 10:30 | `v4_dashboard.py` + 验证 | V4 每日复盘（赛后验证 + 仪表盘生成） |
| 12:20 | `v4_runner.py` | V4 扫描-午间（给 V2 20 分钟缓冲） |
| 16:20 | `v4_runner.py` | V4 扫描-傍晚（给 V2 20 分钟缓冲） |

---

## 关键数据与修复记录

### 关键修复（2026-05-13）

| 问题 | 修复 |
|:---|:---|
| time_bins 全 0 | 设置 `RECENT_PROFILE_INCLUDE_EVENTS = True` |
| fast_mode 跳过事件解析 | 移除 include_events 守卫 |
| macOS 系统代理干扰 | 127.0.0.1:10808 绕过，API-Football 直连 |
| pullback_fit 全 WEAK | 调整为 STRONG×6 / OK×10 / WEAK×7 分布 |
| 首个 A 级推荐产生 | 西雅图海湾人 vs 圣何塞地震 ✅ |

### 仪表盘特性
- 10 天历史数据一键切换（5/5 - 5/14）
- 赛后验证面板：A+B 命中率 / C 命中率
- 时间分布可视化：0-15 / 16-30 / 31-45 时段
- 默认展示所有比赛，按开赛时间排序
- 自动拷贝至 canvas 嵌入式展示

---

## 当前状态

**运行中 — 每日 12:20 / 16:20 两频扫描 ✅**

- 纯情报模式，不与任何策略/交易耦合
- A/B/C/SKIP 四级推荐，赛后自动验证
- 第一个 A 级推荐已产生（西雅图海湾人 vs 圣何塞地震）
- 交互式 HTML 仪表盘每日更新，10 天回溯

---

## 已废弃 / 停用的组件

以下组件在 V4 早期阶段开发，已全部退役：

- V4 走地赔率采集（A_candidate / B_shadow / C_slice）
- V4 走地监控 / 赔率快照 / 半场结算
- V4 采集调度 / Universe 缺口修复 / 预算审计 / 进度报告
- PAPER_ONLY / BUY_NOW / WAIT_LINE / SH_OBSERVE_ONLY（走地交易指令）
- 策略路由中 V4 断路器（已删除）
- V4 退出 CLV 审判台

---

## 已知问题 / 待办

- 二级联赛的 team_cn_map 覆盖率不足 → 需补充 mapping
- H2H 引擎偶发 fetch 失败（API-Football 限流），需增加指数退避
- 当前无实盘耦合，待纸盘验证积累足够数据后评估是否接入交易
- time_bins 数据从 v4_runner 到仪表盘的传递链偶有数据中断
- dashboard 的 HTML 自动打开功能在 SSH 环境下需降级为静默生成
- 当前扫 12:20 / 16:20 两频，但某些 03:00 比赛可能覆盖不到最新 H2H
