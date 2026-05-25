# V3V4_DASHBOARD_CANDIDATE_DISPLAY_INTEGRITY_AND_VALIDATION_NA_FIX_20260526

- 结论：`V3V4_DASHBOARD_CANDIDATE_DISPLAY_INTEGRITY_VALIDATION_NA_FIX_PASS`

## 关键结果
1. A2/B0 但 B区有卡：根因是 `v3v4_dashboard_candidate_view_20260525.json` 内存在 B placeholder（`fixture_id=None`、`：(无) vs UNKNOWN`、`TBD`、`time_bins 待补齐`），renderer 未过滤直接渲染。
2. 已修复：B=0 时 B级候选区显示 0 场且无比赛卡。UNKNOWN/TBD/(无) 不再进入正式 A/B 卡片。
3. 中文名异常：resolver 旧逻辑会输出“中文名缺失：xxx”前缀，且 alias 覆盖不足。已补齐 alias 并改 resolver/renderer，active 主标题不再出现该前缀。
4. 昨日验证 N/A：重新定性为“安全显示”，不代表 validation 链路成功。
5. 累计验证主口径：`A 25/41 · 61.0%`，`B 50/89 · 56.2%`，`A+B 75/130 · 57.7%`，标注 `A/B-only · 不含C`。

## HTTP 复测
- `127.0.0.1:8765`：200
- `192.168.1.2:8765`：200

## 禁止项确认
- full_scan_ran=false
- capture_ran=false
- validation_recomputed=false
- strategy_changed=false
- candidate_changed=false
- candidate_rating_changed=false
- result_validation_changed=false
- script_validation_changed=false
- brief_used_for_hit_rate=false
- scan_date_used_for_validation=false
- live_bet_real_records_modified=false
- v2_restored=false
- v33_active=false
- outside_57_mixed_into_official=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- secrets_printed=false
- secrets_committed=false
