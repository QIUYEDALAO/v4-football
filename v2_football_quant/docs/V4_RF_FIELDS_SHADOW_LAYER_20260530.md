# V4 RF Fields Shadow Layer (2026-05-30)

## 1) 本轮新增 RF 字段

### recent10 主口径
- `home_recent10_fh_involved_rate`
- `away_recent10_fh_involved_rate`
- `combined_recent10_fh_involved_rate`
- `home_recent10_fh_score_rate`
- `away_recent10_fh_score_rate`
- `home_recent10_fh_concede_rate`
- `away_recent10_fh_concede_rate`
- `recent10_sample_count_home`
- `recent10_sample_count_away`
- `recent10_window_days_home`
- `recent10_window_days_away`
- `recent_freshness_status`

### recent5 动量口径
- `home_recent5_fh_involved_rate`
- `away_recent5_fh_involved_rate`
- `combined_recent5_fh_involved_rate`
- `home_recent5_fh_score_rate`
- `away_recent5_fh_score_rate`
- `home_recent5_fh_concede_rate`
- `away_recent5_fh_concede_rate`
- `recent5_momentum_status`

### RF 综合口径
- `recent_form_primary_score`
- `recent_form_primary_level`
- `recent_form_primary_reason`

## 2) 字段计算规则

- 数据源: `engine/rf_shadow_fields.py` 统一计算 helper，供 parallel (`engine/v4_outside57_scanner.py`) 与 whitelist serial (`engine/v4_runner.py`) 复用。
- 正式入口链路: `engine/v4_scan_and_brief.py -> engine/v4_scan_worker.py -> engine/v4_runner.py`。
- 样本口径: 每队最近最多 10 场，且必须有 HT 比分（`halftime.home/away` 非空）才进入 FH 统计。
- `*_fh_involved_rate`: 上半场任意进球场次 / 有效样本数。
- `*_fh_score_rate`: 本队上半场进球场次 / 有效样本数。
- `*_fh_concede_rate`: 本队上半场失球场次 / 有效样本数。
- `combined_recent10_fh_involved_rate`: 主客 recent10 involved rate 简单平均。
- recent5: 从 recent10 有效样本中取最近 5 场同口径计算。
- `recent10_window_days_*`: 该队 recent10 有效样本时间跨度（最早到最晚）。
- `recent_freshness_status`:
  - `FRESH`: 0-90 天
  - `NORMAL`: 91-120 天
  - `STALE`: 121-180 天
  - `EXPIRED`: >180 天
  - `UNKNOWN`: 缺样本或缺日期
- `recent5_momentum_status`:
  - `HEATING_UP`: recent5 比 recent10 高 >10pct
  - `COOLING_DOWN`: recent5 比 recent10 低 >10pct
  - `STABLE`: 其余
  - `LOW_SAMPLE`/`DATA_MISSING`: 样本不足或缺失
- `recent_form_primary_score`: `recent10*0.7 + recent5*0.3`（百分制）。
- `recent_form_primary_level`:
  - `STRONG` / `MEDIUM` / `WEAK`
  - `LOW_SAMPLE` / `DATA_MISSING`
  - `STALE_SAMPLE` / `EXPIRED_SAMPLE`（freshness 覆盖）
- `recent_form_primary_reason`: 人类可读解释文案。

## 3) 缺失值处理

- 不伪造 0%。
- rate 类字段缺失时写 `DATA_MISSING`（dashboard 端保证不出现 `undefined/null/NaN`）。
- recent5 样本不足写 `LOW_SAMPLE`。
- freshness 无法计算写 `UNKNOWN`。
- primary 在样本不足/缺失时输出 `LOW_SAMPLE`/`DATA_MISSING` 与对应 reason。

## 4) 进入 scout 的字段

- 以上 recent10/recent5/primary 全字段均进入正式入口新产物 `scout_v4_YYYYMMDD.json`。
- 本轮正式入口验证日期:
  - 当前业务日: `20260530`（whitelist，no-push，serial）
  - fallback: `20260529`（whitelist，no-push，serial；用于满足 5 场抽样验证）

## 5) 进入 candidate_view 的字段

- `engine/v4_scan_and_brief.py` 的 serial adapter 已包含全部 RF 字段映射。
- 20260529/20260530 两次正式入口 dry-run 均为 `A=0, B=0`，所以 `A_candidates/B_candidates` 为空（属于“当日无 A/B”而非链路断裂）。
- 因无 A/B 条目，本轮 candidate_view 字段验证以“映射代码存在 + scout/模型字段落地 + checker serial-path 证明”为准。

## 6) 进入 dashboard model 的字段

- `tools/build_v4_control_center_model.py` 已合并输出全部 RF shadow 字段。
- 无候选时 `candidate_items_empty` 为 WARN_ONLY；不判定为数据链路断裂。
- RF checker 要求 dashboard 不出现 `undefined/null/NaN`。

## 7) 为什么本轮不改 official grade

- 未修改 `engine/v4_match_intelligence.py` 的 `DEFAULT_RULES`、A/B/C/SKIP 判级阈值和判级流程。
- RF 新字段仅作为 shadow explain data，不参与正式评级输入。

## 8) 为什么本轮不改 H2H runtime

- 未改 `engine/data_sources/h2h_engine.py` 的正式 gating 逻辑与阈值。
- RF shadow 只在扫描结果层补充，不回写 H2H 判级门槛。

## 9) 本轮 watchdog 诊断与修复结论

- 上一轮不能 PASS 的根因:
  - 只做了 parallel 路径验证，不能代表正式 `12:00 whitelist serial` 入口。
  - 并且观察到 `task_status` 长时间 `RUNNING 0/0`，误判为卡住风险。
- 本轮诊断结果:
  - 进程真实活跃（`v4_scan_and_brief.py` 与 `v4_scan_worker.py` 存活）。
  - 日志持续推进（H2H 查询进度前进），最终自然完成。
  - `RUNNING/DELAYED + current=0/0` 是状态进度字段未细分，不是死锁。
- 本轮最小修复:
  - `tools/check_v4_rf_fields_shadow_layer.py` 改为优先读取 `task_status_v4_scan_midday.json` 的 `output_files`，避免误抓旧日期产物。
  - checker 明确区分正式 serial 路径，并在“无候选”场景使用 WARN_ONLY 逻辑，不掩盖真实 blocker。
  - `tools/check_v4_true_goal_time_distribution.py`、`tools/check_v4_playbook_script_and_time_distribution.py` 在无候选时输出 WARN_ONLY。
  - `tools/check_v4_no_market_core_validation_skip.py` 将历史数据集造成的非核心误报降级为 WARN_ONLY（不改 NO_MARKET 业务逻辑）。

## 10) 正式入口 dry-run 记录与证据

- 正式入口命令（no-push）:
  - `python3 -u engine/v4_scan_and_brief.py --date 20260530 --fixture-universe whitelist --no-push`
  - `python3 -u engine/v4_scan_and_brief.py --date 20260529 --fixture-universe whitelist --no-push`（fallback）
- `20260529` 新产物（本轮重新生成）:
  - `total_fixtures=73`, `scouted_count=17`, `A=0`, `B=0`, `C=0`, `SKIP=17`
  - `fixture_universe=whitelist`, `no_push=true`, `qq_sent=false`
- RF 字段运行态验证:
  - 在新 `scout_v4_20260529.json` 完整存在（17/17，0 条缺失/NaN）。
  - 抽样 5 场均有 `recent10/recent5/primary` 字段与可读 reason。
- official-grade 安全性:
  - `DEFAULT_RULES guard PASS`
  - `official grade` 未接入 RF shadow 字段
  - `H2H runtime` 未改
  - `cron` 未改
  - `validation` 未重算
  - `live bet` 未改
  - `QQ` 未推

## 11) Phase 边界

- 本轮只完成 RF shadow fields 正式入口运行态验收，不进入 Phase 3。
- Phase 3 待办（仅列计划，不在本轮实施）:
  - 近10 7/10 入池
  - 近5评级
  - H2H近5只加分
  - Team Balance
  - Opening Market Confirm / Veto
