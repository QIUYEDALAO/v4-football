# V3V4_TEAM_CN_BAD_FIX_ROLLBACK_AND_DATA_RESTORE_20260525

## Phase
V3V4-TEAM-CN-BAD-FIX-ROLLBACK-AND-DATA-RESTORE-20260525

## Step 状态
- Step 1 冻结与损坏审计: PASS
- Step 2 根因定位: PASS
- Step 3 数据口径恢复: PASS
- Step 4 display-only 中文修复: PASS
- Step 5 本地/内网 HTTP 复测: PASS
- Step 6 防回归 checker: PASS
- Step 7 Git 同步: PASS
- Step 8 local-only closeout: PASS

## 核心修复结果
- 已恢复 dashboard 为正确数据口径：
1. 昨日验证：A 2/3 · 66.7%，B 6/8 · 75.0%，A+B 8/11 · 72.7%
2. 累计验证：A 25/41 · 61.0%，B 50/89 · 56.2%，A+B 75/130 · 57.7%（A/B-only · 不含C）
3. 剧本验证：昨日 A+B 8/12 · 66.7%，累计 A+B 69/124 · 55.6%
- 已清除错误回归：20260522 stale fallback、124/140、HT7270/HT6140/HT7340、昨日/剧本验证 N/A。
- 中文名修复仅作用于显示层主标题；并新增 EN 审计小字，不改任何候选/验证数字。

## 问题回答
1. 数据为什么被修坏？
- 页面被错误重建到 stale source（20260522），而不是沿用正确的 last-good 数据页面。
2. 为什么回退到 20260522？
- 生成器按 latest candidate file 取数，当前目录仅有 `intel_desk_v4_candidate_view_20260522.json`（无 20260524），因此回退。
3. 为什么 124/140 回流？
- stale rebuild 重新渲染了旧累计验证口径（A/B 累计 124/140）。
4. 为什么昨日验证丢失？
- stale rebuild 没有加载到正确昨日验证 summary，渲染成 N/A。
5. 为什么剧本验证丢失？
- 同上，stale summary 路径导致剧本验证被渲染为 N/A。
6. 为什么 HT 字段异常？
- stale candidate 文件中 `ht_score` 本身是异常值（7270/6140/7340），被直接渲染。
7. 已经恢复到什么数据？
- 恢复为上述 8/11、75/130、8/12、69/124 口径。
8. 中文名现在如何显示？
- 主标题中文；英文保留为 `EN: xxx vs yyy` 审计小字。
9. 是否还需要每天手工翻译？
- 不需要每天手工修当前页面；但完整覆盖仍建议继续补 alias/resolver 映射库。
10. 是否改策略？
- 否。
11. 是否改 candidate？
- 否（数量与评级保持）。
12. 是否改验证数字？
- 否（恢复到既定正确口径，不做重算）。
13. 是否运行 scan？
- 否。
14. 是否 cloud publish？
- 否。
15. commit sha 是什么？
- 23d249507aa97b376f5578aa6ae56762747168eb

## 本地 HTTP 结果
- 127 intel: 200
- 127 outside57: 200
- 192 intel: 200
- 192 outside57: 200

## 禁止项确认
- full_scan_ran=false
- validation_recomputed=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- strategy_changed=false
- candidate_changed=false
- result_validation_changed=false
- script_validation_changed=false
- outside_57_official=false
- v2_restored=false
- v33_active=false
- c_validation_visible=false
- last_7d_visible=false
- secrets_printed=false
- secrets_synced=false


## 最终结论
V3V4_TEAM_CN_BAD_FIX_ROLLBACK_DATA_RESTORE_WARN_ONLY
