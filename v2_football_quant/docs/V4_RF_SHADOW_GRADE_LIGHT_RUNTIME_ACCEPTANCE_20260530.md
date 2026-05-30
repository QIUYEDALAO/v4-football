# V4 RF Shadow Grade Light Runtime Acceptance (2026-05-30)

## 背景

在 `V4_RF_SHADOW_GRADE_CODE_READY` 之后，仍需补“运行态字段闭环”证据，但当前阶段不允许执行正式入口长耗时扫描，也不允许调用 API。

因此新增 **Light Runtime Acceptance**：

- 只读取已有 `scout_v4_*.json`
- 用当前代码重新计算 shadow 字段
- 产出临时 acceptance artifact
- 验证字段从 `scout-like -> candidate_view-like -> dashboard_model-like` 的闭环

## 与正式 serial dry-run 的区别

Light acceptance 不是正式生产扫描验收：

- 不调用 API
- 不运行 `engine/v4_scan_and_brief.py`
- 不覆盖正式 candidate/scout/brief 业务产物
- 不改官方分级（official grade）

它的作用是“字段闭环与 no-regrade 安全性”验证，不替代后续真实生产日补验。

## 本轮新增

1. `tools/run_v4_rf_shadow_grade_light_runtime_acceptance.py`
2. `tools/check_v4_rf_shadow_grade_light_runtime_acceptance.py`

### run 工具职责

- 自动定位最近非空 scout 样本
- 对每行调用 `build_rf_shadow_grade_layer(...)`
- 生成 enriched rows
- 生成 candidate_view-like / dashboard_model-like 结构
- 输出 summary + 规则样例验证结果

输出目录：

- `data/runtime/acceptance/v4_rf_shadow_grade_light_acceptance_YYYYMMDD_HHMMSS.json`

注意：该目录在 `data/` 下，不应纳入提交。

### checker 职责

- 检查 acceptance artifact 存在且行数 > 0
- 检查 RF shadow / Team Balance / H2H bonus-only / Opening Market 字段覆盖
- 检查 candidate_view-like / dashboard_model-like 都包含 shadow 字段
- 检查 `no_regrade`（`grade` / `official_grade` 不被覆盖）
- 检查规则样例全 PASS
- 检查未调用 API、未执行正式 scan
- 检查 acceptance artifact 未被 stage、无 secrets staged
- 联动关键 guard（DEFAULT_RULES / whitelist-cron / validation-livebet）

## 验收边界声明

- 本轮结论仅对应：`V4_RF_SHADOW_GRADE_LIGHT_RUNTIME_ACCEPTANCE_*`
- **不等同** 正式生产 `serial whitelist no-push` dry-run PASS
- 未经 BOSS 单独授权，不进入 Phase 4/5/6

## 状态收口规则

若 light acceptance 与 checker 通过，可更新为：

- `V4_RF_SHADOW_GRADE_LIGHT_RUNTIME_ACCEPTANCE_PASS`

否则按规则收口为：

- `V4_RF_SHADOW_GRADE_LIGHT_RUNTIME_ACCEPTANCE_BLOCKED`
- 或 `V4_RF_SHADOW_GRADE_LIGHT_RUNTIME_ACCEPTANCE_FAIL`
