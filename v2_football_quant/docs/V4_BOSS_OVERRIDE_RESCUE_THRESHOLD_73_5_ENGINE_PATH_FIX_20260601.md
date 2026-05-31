# V4_BOSS_OVERRIDE_RESCUE_THRESHOLD_73_5_ENGINE_PATH_FIX_20260601

## 背景
- `6261df2` 已将 replay 工具默认阈值切到 `73.5`。
- OpenClaw 验收判定为 `REPLAY_ONLY_SWITCH`：真实 engine path 仍残留默认 `77.0`。
- 本轮为 Phase 3K-FIX，目标是修复 engine 默认路径，不扩大范围。

## 本轮修复
1. 已修复 `engine/rf_shadow_fields.py`：
   - 新增 `DEFAULT_RESCUE_THRESHOLD = 73.5`
   - rescue 判级从硬编码 `score >= 77.0` 改为 `score >= rescue_threshold`
   - below gate 从硬编码 `score < 77.0` 改为 `score < rescue_threshold`
2. replay 工具默认阈值保持 `73.5`。
3. rollback 能力保留：`--rescue-threshold 77` 仍可复现旧口径。

## 关键结论
- `engine` 与 `replay` 默认阈值已对齐为 `73.5`。
- `77.0` 不再作为 engine rescue 默认门槛，仅保留为回放参数基线。
- 本轮结论从 replay-only 修复为 engine-path 生效。

## 口径修正（必须一致）
- `artifact_count_sufficient = 15`
- `official-present sufficient date count = 2`
- `official-missing sufficient count = 13`
- `aggregate fixture_count = 157`

## 安全门结果（本轮）
- default(73.5): shadow `1/35/36/20`
- rollback(77): shadow `1/32/39/20`
- `A expansion = 0`
- `SKIP_to_B = 0`
- `market_alone = 0`
- `safety_violations = 0`

## 安全边界（保持）
1. 不改 official grade。
2. 不改 production_grade_mode。
3. 不写 pending。
4. 不推 QQ。
5. 不重扫，不调 API。
6. 不改 validation / live bet / cron。
7. 不改 DEFAULT_RULES。
8. 不改官方 A/B 阈值。

## 风险说明
- 本轮是 BOSS override 下的默认阈值切换与 engine path 修复。
- 不是样本充分后的自动 promotion，不等同“实盘收益确认”。

## 回滚方式
1. 运行参数回滚：`--rescue-threshold 77`。
2. 代码回滚：后续 commit 可将 engine/replay 默认阈值恢复到 `77.0`。
