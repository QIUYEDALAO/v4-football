# ⚽ V2 量化系统 — P0-P2 执行任务清单（更新版）

> 数据源: API-Football Pro | 联赛: 56个 | 预算: $19/月
> 核心KPI: ROI > 3% | CLV > 0 | 命中率 > 58%（HT 1X2）
> **最后更新：2026-05-06 23:09**

---

## 版本变更记录

| 日期 | 变更 |
|:---|:---|
| 5/5 16:10 | 初始版本，V38 半场大球策略 |
| 5/6 23:09 | 策略切换：HT 1X2（半场胜平负）；fetcher+aligner 完成；纸盘开跑；V3/V4 蓝图确定 |

---

## 一、已完成（打勾确认）

| 任务 | 完成日期 | 说明 |
|:---|:--:|:---|
| fixtures_results 表 | 5/5 | SQL schema |
| odds_snapshots 表 | 5/5 | SQL schema |
| p0_day1_validate.py | 5/5 | 单场 API 链路验证 |
| clv.py v0.1 | 5/5 | CLV 计算底层 |
| team_cn_map.py | 5/5 | 320 条球队中英映射 |
| fetcher.py | 5/5 | 批量拉取（限频+重试） |
| aligner.py | 5/5 | 时序对齐 + H2H 自引用检测 |
| scoring_engine_v0.py | 5/5 | 5 维度等权评分 |
| backtest_pipeline_v0.py | 5/5 | 回测 → CSV 2322 行 |
| oos_monitor.py | 5/5 | OOS 对抗验证 |
| wc_model.py | 5/5 | W杯 3 维独立模型 |
| daily_runner.py v2.0 | 5/6 | HT 1X2 → 8:00 Cron |
| paper_trading.py v2.0 | 5/6 | True CLV + 赛后结算 |
| bankroll.py v2.0 | 5/6 | 纯 Kelly + 低价值过滤 |
| odds_monitor.py | 5/6 | 预留给实盘轮询 |
| QQ Bot 通道 | 5/6 | 替代微信推送 |
| 6 Bug 修复 | 5/6 | Stake/NoneType/Kelly/平局/旧纸盘/收盘 |
| 5/5 首场结算 | 5/6 | Al Khaleej HT 1-1 · PnL +86.1u |
| 5/6 纸盘首跑 | 5/6 | 35场 → 2场推荐 |

---

## 二、P0 剩余任务

| # | 任务 | 状态 | 时间 |
|---|------|:--:|:--:|
| 1 | 评分引擎权重校准（H2H 20%→60%） | ❌ | 待纸盘数据后做 |
| 2 | 缺失 14 联赛数据补拉 | ❌ | 休赛期 |

---

## 三、P1 模型迭代（纸盘后启动）

| # | 任务 | 状态 |
|---|------|:--:|
| 1 | 用回测结果替代主观权重（网格搜索） | ☐ |
| 2 | 动态权重 + 时间衰减 + 联赛修正 | ☐ |
| 3 | 0-0 防守机制改为动态阈值 | ☐ |
| 4 | 拉取 2018/2022 W杯历史数据 | ☐ |
| 5 | W杯赛制因子设计 | ☐ |
| 6 | 日职/韩K 等亚洲联赛单独统计 | ☐ |

---

## 四、P2 W杯备战 + V3/V4 开发

> 详见 `docs/NEXT_STEPS.md` 和 `docs/TASK_LIST.md`

| 阶段 | 目标 | 时间 |
|:---|:---|:---|
| 📋 Phase 0 | 基础设施（映射表+目录+Git） | 5/6 今晚 |
| 🛤️ Phase 1 | 策略路由框架 | 5/13 |
| 📡 Phase 2 | 免费数据管道（FotMob/Understat/FBref） | 5/20 |
| 🏆 Phase 3 | V3 W杯模型 | 5/25 |
| 🏴 Phase 4 | V4 五大联赛 xG 模型 | 6/15 |

---

## 五、不可触碰的红线

| # | 规则 |
|---|------|
| 1 | 信号抓取与交易执行彻底分离 |
| 2 | V2 生产代码冻结期不碰 daily_runner/bankroll/paper_trading |
| 3 | 所有新代码在独立目录开发，通过 Strategy Router 接入 |
| 4 | 绝不把 8:00 快照直接接下单 API |
| 5 | 赔率涨跌不改变已成交的 PnL，CLV 的符号才是 Alpha 的证据 |
