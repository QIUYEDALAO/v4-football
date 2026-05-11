# V4 全量执行总清单

## P0 数据底座
- [x] 全量比赛池 `data/universe/fixtures_universe_YYYYMMDD.jsonl`
- [x] 决策日志 `data/decision_logs/v4_decision_log_YYYYMMDD.jsonl`
- [x] 影子回测池 `data/shadow_backtest/shadow_entry_YYYYMMDD.jsonl`
- [x] 执行仿真日志 `data/execution/live_execution_sim_YYYYMMDD.jsonl`

## P1 概率与 EV
- [x] 亚洲盘 EV 函数 `engine/asian_ev.py`
- [x] 分钟条件概率模型 `engine/ht_goal_hazard_model.py`
- [x] 分钟 EV 引擎（替换固定水位）

## P2 回测与证伪
- [x] walk-forward 回测框架
- [x] 多策略候选记录 `data/research/strategy_candidates.jsonl`
- [x] 校准报告 `engine/v4_calibration_report.py`
- [x] 死亡条件 `config/kill_criteria.yaml`

## P3 成交与滑点
- [x] 执行成本模型 `engine/execution_cost_model.py`
- [x] raw/slippage/conservative 三套ROI日报

## P4-P6 分层与风控
- [x] 联赛分层阈值 `engine/league_hierarchical_threshold.py`
- [x] 风控守卫 `engine/risk_guard.py`
- [x] 最优分钟窗口模型 `engine/line_decay_model.py`

## P7 下半场独立策略
- [x] `V4_SH_LIVE_OVER` 独立仓与评估闭环

## P8 扩展因子
- [x] 天气/场地/裁判采集与边际贡献检验（观测层V1）

## 一键总控
- [x] 总控脚本 `engine/v4_master_run.py`

### 常用命令
- `python3 engine/v4_master_run.py --date 20260512 --phase full`
- `python3 engine/v4_master_run.py --date 20260512 --phase prematch`
- `python3 engine/v4_master_run.py --date 20260512 --phase ht`
- `python3 engine/v4_master_run.py --date 20260512 --phase sh`
- `python3 engine/v4_master_run.py --date 20260512 --phase reports`
