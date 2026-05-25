# V3V4_DASHBOARD_VALIDATION_NA_AND_CUMULATIVE_RECOUNT_CORRECTION_20260526

## 结论
- 最终结论：`V3V4_DASHBOARD_VALIDATION_NA_CUMULATIVE_CORRECTION_PASS`
- 昨日验证 `N/A` 已重新定性为“安全显示”，**不是**“验证链路成功”。
- 活跃 dashboard 已去除误导性 `124/140 · 88.6%` 主累计口径，恢复为 `A/B-only · 不含C`：`75/130 · 57.7%`。

## 关键回答
1. 昨日验证为什么 N/A：`--no-api` 模式 + 昨日目标日无可信已结算样本。
2. N/A 是安全显示还是验证链路成功：安全显示，不是链路成功。
3. 13:00 validation 是否真实运行：是（dry-run marker 存在，状态 READY）。
4. 14:00 final 是否真实运行：是（final marker 存在，`final_validation_ran=true`）。
5. API 是否启用：该链路对昨日结算为 `--no-api`。
6. 累计 AB=140·88.6% 来源：`v3v4_validation_summary_20260525.json` 的历史恢复口径。
7. 是否旧口径回流：是，已从主累计展示移除。
8. 当前 dashboard 最终显示：
   - 昨日：A/B/A+B = N/A（并明确“链路未视为成功”）
   - 累计：A `25/41 · 61.0%`，B `50/89 · 56.2%`，A+B `75/130 · 57.7%`
   - 标签：`A/B-only · 不含C`
9. 是否改策略：否。
10. 是否重算 validation：否。
11. 是否需要 BOSS 授权真实 API validation：是（如需把昨日 N/A 变为真实结算值）。

## 本地复测
- `http://127.0.0.1:8765/intel_ops_console.html`：HTTP 200
- `http://192.168.1.2:8765/intel_ops_console.html`：HTTP 200

## 禁止项确认
- `full_scan_ran=false`
- `capture_ran=false`
- `validation_recomputed=false`
- `strategy_changed=false`
- `candidate_changed=false`
- `result_validation_changed=false`
- `script_validation_changed=false`
- `brief_used_for_hit_rate=false`
- `scan_date_used_for_validation=false`
- `v2_restored=false`
- `v33_active=false`
- `outside_57_mixed_into_official=false`
- `QQ_push=false`
- `cloud_publish=false`
- `cron_modified=false`
- `secrets_printed=false`
