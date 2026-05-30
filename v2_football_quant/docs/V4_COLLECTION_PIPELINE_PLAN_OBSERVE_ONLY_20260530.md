# V4_COLLECTION_PIPELINE_PLAN_OBSERVE_ONLY_20260530

## 背景

- Phase 3A 的激进版本（commit `6d06be0b6e256ed2d72ec47d2419d246536e4bf4`）在正式入口 dry-run 上出现多日 `scanned=0`，存在 12:00 正式扫描空产物风险。
- 失败点不是“是否做 Lazy 方向”，而是“过早让 lazy gating 影响了 official scan 链路与 scout row 生成”。

## 本轮目标

仅新增 **observe-only** 计划字段，不启用真实 lazy skip，不改变 official grading。

- 记录“如果未来启用 lazy，会如何决策”
- 保留旧 official 采集链路（H2H / events / CPL 路径）
- 保证 scout 行生成不受 planned 字段影响

## observe-only 与真实 lazy skip 的区别

- observe-only：只写 `planned_*` 字段，作为影子计划与可观测数据。
- 真实 lazy skip：会根据 gating 直接跳过采集调用，影响运行时行为。

本轮只做前者，明确不做后者。

## Plan 字段与 Actual 字段分离

### Plan（计划）

- `collection_plan_mode=OBSERVE_ONLY`
- `collection_plan_observe_only=true`
- `planned_collection_stage`
- `planned_h2h_required`
- `planned_h2h_skipped_reason`
- `planned_events_required`
- `planned_events_skipped_reason`
- `planned_cpl_required`
- `planned_cpl_skipped_reason`
- `planned_expensive_calls_saved`
- `planned_collection_reason`

### Actual（真实执行）

- `actual_h2h_collected`
- `actual_events_collected`
- `actual_cpl_collected`
- `actual_collection_stage`
- `actual_collection_reason`

约束：`planned_*` 不控制 `actual_*`，不控制 scout row 是否生成。

## 风险控制

- 不修改 official grade
- 不修改 DEFAULT_RULES
- 不修改 A/B 阈值
- 不修改 H2H runtime 正式判级语义
- 不修改 cron
- 不重算 validation
- 不修改 validation 历史
- 不修改 live bet 原始记录
- 不推 QQ

## 关于 API 节省

本轮 **不宣称真实节省 API 请求**。
`planned_expensive_calls_saved` 仅为“未来启用 lazy 时的估算指标”，非真实运行节省结果。

## 后续启用真实 lazy skip 的前置条件

- observe-only 连续多日稳定
- scout 行数稳定，不丢行
- shadow 计划与 official 结果可解释对齐
- 单独 BOSS 授权后再进入真实 gating 开关评估
- 在灰度/可回滚机制下逐步启用，禁止直接切主链路
