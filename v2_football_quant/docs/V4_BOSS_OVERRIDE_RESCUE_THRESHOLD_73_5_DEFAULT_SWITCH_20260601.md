# V4_BOSS_OVERRIDE_RESCUE_THRESHOLD_73_5_DEFAULT_SWITCH_20260601

## 变更性质
本次为 **BOSS override**。  
目标是把 shadow rescue 默认阈值从 `77.0` 改为 `73.5`。  
这是代码默认值切换，不是 official 切换，不是 QQ 推送授权。

## 变更范围
1. `tools/run_v4_rf_shadow_promotion_dryrun_replay.py`
   - 默认 `--rescue-threshold` 改为 `73.5`
   - 默认 `default_rescue_threshold` 改为 `73.5`
2. 保留参数化回放：
   - `--rescue-threshold 77` 可复现旧默认结果
   - `--rescue-thresholds 77,73.5` 可做 sensitivity 对比
3. multi-artifact 基线与候选参数仍保留：
   - baseline `77`
   - candidate `73.5`

## 安全边界（保持不变）
1. 不修改 official grade。
2. 不修改 production_grade_mode。
3. 不写 pending。
4. 不推 QQ。
5. 不重算 validation。
6. 不修改 live bet。
7. 不修改 cron。
8. 不调用 API，不重扫。
9. 不提交 runtime artifact。

## 已知结果（回放口径）
### 默认（73.5）
- shadow A/B/C/SKIP = `1/35/36/20`
- B_to_C = `1`
- B_to_B = `35`
- rescue_to_B = `8`
- rescue_to_A = `0`
- SKIP_to_B = `0`
- market_alone = `0`
- safety_violations = `0`

### 参数回滚（77）
- shadow A/B/C/SKIP = `1/32/39/20`

## 风险说明
- 口径修正：`artifact_count_sufficient=15`，其中 `official-present sufficient=2`、`official-missing sufficient=13`，aggregate `fixture_count=157`。
当前 official-present sufficient artifact 仍有限（历史多日 candidate_view 缺失）。  
本次切换依据：BOSS override + 现有 replay/canary 安全门通过。  
不等同于“已完成实盘收益验证”。

## 回滚方式
1. 临时回滚（无代码改动）：运行时显式传 `--rescue-threshold 77`。  
2. 永久回滚（代码层）：后续提交把默认阈值改回 `77.0`。
