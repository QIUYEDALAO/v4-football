# V4_RESCUE_THRESHOLD_SENSITIVITY_REPLAY_20260601

## 范围
本轮是 **Phase 3H — V4_RESCUE_THRESHOLD_SENSITIVITY_REPLAY_SHADOW_ONLY**。  
只做 shadow-only 阈值敏感性回放，不做 promotion 上线，不做 official 切换。

## 关键原则
1. 默认 rescue threshold 仍是 `77`。
2. `75` / `73.5` 仅用于 sensitivity replay 场景。
3. 不修改 official grade。
4. 不写 pending。
5. 不推 QQ。
6. 不重算 validation。
7. 不触碰 live bet。
8. 不修改 cron。
9. 不调用 API，不重扫。

## 新增能力
在 `tools/run_v4_rf_shadow_promotion_dryrun_replay.py` 增加：
- `--rescue-threshold`（单阈值）
- `--rescue-thresholds`（多阈值）
- `--sensitivity`（多阈值对比模式）

默认（不传参数）行为保持原样，仍按 `77` 执行并输出原 replay 报告。

## Sensitivity 输出
多阈值输出包含：
- `sensitivity_thresholds`
- `threshold_results`
- 每档 `official/shadow A-B-C-SKIP`
- 每档 `B_to_C/B_to_B`
- 每档 `rescue_to_B/rescue_to_A/SKIP_to_B`
- 每档 `market_assisted_rescue_to_B_count`
- 每档 `market_alone_manufactured_AB_count`
- 每档 `safety_violations_count`
- 每档 `rescued_fixture_list`
- 每档 `new_rescues_vs_default`
- 每档 `risk_flags`

## 安全约束
任一阈值档都必须满足：
- `rescue_to_A_count = 0`
- `SKIP_to_B_count = 0`
- `market_alone_manufactured_AB_count = 0`
- `safety_violations_count = 0`

## 结论口径
本阶段只提供“是否值得继续讨论阈值调整”的离线证据，  
不等于 production promotion 授权。若后续要改默认阈值，必须 BOSS 单独授权并走 OpenClaw 验收。
