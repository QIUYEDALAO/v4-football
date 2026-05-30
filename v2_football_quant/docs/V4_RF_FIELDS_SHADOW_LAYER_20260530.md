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

- 数据源: `engine/v4_outside57_scanner.py` 单场并发抓取的 `fixtures?team=...&last=10&status=FT`。
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

- 以上 recent10/recent5/primary 全字段均透传到 `scout_v4_YYYYMMDD.json`（adapter 映射层）。

## 5) 进入 candidate_view 的字段

- 以上 recent10/recent5/primary 全字段均透传到 `v3v4_dashboard_candidate_view_YYYYMMDD.json` 的 A/B 候选条目。

## 6) 进入 dashboard model 的字段

- `tools/build_v4_control_center_model.py` 在 `candidates.items`（以及 A/B 列表项）合并并输出全部 RF shadow 字段。
- 缺失时统一输出 `DATA_MISSING/UNKNOWN/LOW_SAMPLE`，避免 `undefined/null/NaN`。

## 7) 为什么本轮不改 official grade

- 未修改 `engine/v4_match_intelligence.py` 的 `DEFAULT_RULES`、A/B/C/SKIP 判级阈值和判级流程。
- RF 新字段仅作为 shadow explain data，不参与正式评级输入。

## 8) 为什么本轮不改 H2H runtime

- 未改 `engine/data_sources/h2h_engine.py` 的正式 gating 逻辑与阈值。
- RF shadow 计算放在 adapter 扫描链路（outside57 scanner）后置补充，不回写 H2H 判级门槛。

## 9) checker 如何验证 no-regrade

- 新增 `tools/check_v4_rf_fields_shadow_layer.py`:
  - 验证 RF 字段在 adapter/model 代码映射存在。
  - 验证 dashboard model 中 RF 字段可读且无 `undefined/null/NaN`。
  - 验证 official grade 逻辑文件未引用 RF shadow 字段。
  - 串联 `check_v4_production_default_rules_guard.py`、系统/NO_MARKET/goal-distribution/playbook 等 guard。

## 10) Phase 2 如何基于本层生成 rf_shadow_grade

- 以本轮 `recent_form_primary_score/level/reason` 为输入，新增独立 `rf_shadow_grade`（A/B/C/SKIP-like shadow tag）。
- 与 official grade 并行展示，先离线对照验证，不进入正式 gating。
- 对 stale/low-sample 建立 shadow 降权规则，最终通过 checker 对比 “shadow 变化 vs official 不变”。
