# V4_RF_SHADOW_PROMOTION_DRYRUN_REPLAY_20260601

## 阶段定义
本轮为 **Phase 3D-F — V4_RF_SHADOW_PROMOTION_REPLAY_FIELD_COMPLETENESS_FIX**。
只做 dryrun/replay 字段完整性修复，不做 official promotion，不做上线切换。

## 核心结论口径
`sufficient fixture sample` 不等于 `sufficient field coverage`。

Promotion replay 判断必须同时满足：
1. sample_count sufficient；
2. official artifact present；
3. recent5 bilateral gate field coverage sufficient；
4. B-floor exception field coverage sufficient；
5. market/H2H/events/CPL safety field coverage sufficient。

任一条件不满足，不得给出 promotion-ready 类结论。

## 本轮新增修复点
1. **official artifact resolver**
- 优先读取 `--official-artifact`
- 否则读取 `data/runtime/status/v3v4_dashboard_candidate_view_<date>.json`
- 若不存在，标记 `official_artifact_status=MISSING`
- 不再把 missing official 伪装为 `0/0/0/0`

2. **delta 分类修复**
- 新增区分：`OFFICIAL_MISSING_SHADOW_ONLY`
- 与 `TRUE_SHADOW_ONLY` 分离，避免误把 artifact 缺失当业务结果

3. **recent5 gate coverage 修复**
- 新增：
  - `recent5_gate_field_coverage_status`
  - `recent5_gate_reconstructable`
  - `recent5_gate_available_count`
  - `recent5_gate_unknown_count`
  - `recent5_gate_missing_fields`
- 缺字段时输出 UNKNOWN，不得按 0 计作 PASS。

4. **B-floor coverage 修复**
- 新增：
  - `bfloor_exception_field_coverage_status`
  - `bfloor_exception_available_count`
  - `bfloor_exception_unknown_count`
  - `bfloor_exception_missing_fields`
- 例外仍只允许保 B，不允许升 A。

5. **safety coverage 修复**
- 新增：
  - `safety_field_coverage_status`
  - `market_safety_coverage_status`
  - `h2h_safety_coverage_status`
  - `events_safety_coverage_status`
  - `cpl_safety_coverage_status`
  - `safety_unknown_count`
  - `safety_missing_fields`
- 缺字段不再默认 NO。

6. **strict mode**
- `--strict-field-coverage` 打开后：
  - official missing 或 recent5 coverage incomplete 时，不允许 baseline-ready。

7. **market rescue 字段重命名清理（Phase 3F-N）**
- 新增：
  - `market_assisted_rescue_to_B_count/list`（合法 rescue）
  - `market_alone_manufactured_AB_count/list`（非法 market-alone 制造）
  - `market_rescue_safety_status`
  - `market_rescue_naming_status`
- 旧字段 `market_manufactured_AB_found` 保留为 deprecated alias，仅用于兼容旧读取方，禁止作为 safety violation blocker。

## 产物与工具
- Runner：`tools/run_v4_rf_shadow_promotion_dryrun_replay.py`
- Checker：`tools/check_v4_rf_shadow_promotion_dryrun.py`
- Runtime artifact（仅观察，不提交）：
  - `data/runtime/acceptance/v4_rf_shadow_promotion_dryrun_replay_<date>.json`
  - `data/runtime/acceptance/v4_rf_shadow_promotion_dryrun_replay_<date>.md`

## 安全红线（保持不变）
1. 不改 official grade。
2. 不改 production_grade_mode。
3. 不写 pending。
4. 不推 QQ。
5. 不重算 validation。
6. 不改 live bet。
7. 不改 cron。
8. 不调 API，不重扫。

## 结论状态码
- `SUFFICIENT_SAMPLE_REPLAY_BASELINE_READY`
- `SUFFICIENT_SAMPLE_BUT_FIELD_COVERAGE_INCOMPLETE`
- `OFFICIAL_ARTIFACT_MISSING_BLOCKER`
- `RECENT5_GATE_COVERAGE_INCOMPLETE_BLOCKER`
- `FAIL_NEED_CODE_REVIEW`

## 说明
本阶段仍是 dryrun-only。后续如要进入正式 promotion 或生产切换，必须 BOSS 单独授权并经过 OpenClaw 验收。

## Phase 3F 调优补充
- replay 增加 `shadow_dryrun_grade_before_tuning` 与 `shadow_dryrun_grade_after_tuning`，用于对比 B→C / B→B 变化。
- 新增 recent5/B-floor rescue 统计与阻断统计（tier4 / extreme veto / baseline-only / market-no-data）。
- 目标是减少不合理 B→C，不扩大 A，不越过 official B 上限，不触发任何 official/pending/QQ 变更。
