# V3V4 Dashboard Today Auto-Update Missing — Root Cause & Recovery

**Date:** 2026-05-25  
**Final Status:** V3V4_DASHBOARD_TODAY_AUTO_UPDATE_MISSING_RECOVERY_PASS  

---

## 1. 今天 12:00 scan 是否跑了？

**是。** 12:00 V4_DAILY_SCAN_READONLY 扫描完成。用时 269s，产出 6 条球探报告。
日志: `data/runtime/logs/v4_scan_midday_20260525.log`

## 2. 今日 scan 产物是否存在？

**是。** 
- scout: `data/daily_reports/scout_v4_20260525.json` ✅
- scan_perf: `data/daily_reports/scan_perf_v4_20260525.json` ✅

## 3. after-scan refresh 为什么没更新？

**原因：allowlist 日期未更新。**
允许列表文件 `v3v4_dashboard_active_source_allowlist_20260525.json` 只含 20260524 路径。
20260525 的 candidate_view / brief_resolution / validation_summary 被阻断 →
`CANDIDATE_SOURCE_NOT_ALLOWLISTED` + `VALIDATION_SOURCE_NOT_ALLOWLISTED` →
`dashboard_refreshed=false`

**修复：** 将 20260525 路径加入 allowlist，重新运行 after-scan refresh。结果：
`blockers=[]`, `dashboard_refreshed=true`, `candidate_touched=true`

## 4. 昨日 validation 是否跑了？

**是。** 13:00 V4_VALIDATION_DRY_RUN 运行成功（26s），14:00 最终验证也运行了。
但昨日（2026-05-24）的 match_date 可信记录为 0（API disabled）。
dashboard 显示昨日验证为 N/A，累计验证 AB=140场 | 88.6%。

## 5. 昨日 result validation 是否有可信 summary？

**有。** `v3v4_validation_summary_20260525.json` 包含：
- 累计 AB: 140 条，124 命中，**88.6%**
- 昨日 match_date 2026-05-24: 0 条（API 未启用，trusted attribution only）
- 昨日显示 N/A（有 reason: no_trusted_history_for_yesterday_or_api_disabled）

## 6. 昨日 script validation 是否有可信 summary？

**有。** `v4_script_validation_summary_20260525.json` 包含：
- 累计 AB: 124 条，69 命中，**55.6%**
- 昨日 match_date 2026-05-24: 0 条，显示 N/A

## 7. after-validation / final 为什么没更新？

after-validation: 同样被 allowlist 阻断。
final: `NOOP_AFTER_VALIDATION_RERUN` — source_hash 未变。已在 after-scan 修复且 after-validation 刷新后获取正确数据。

## 8. dashboard 现在是否显示今日扫描？

**是。** 已通过 `tools/run_v3v4_dashboard_daily_update.py --date 20260525 --phase after-scan --mode apply` 刷新。
dashboard mtime: 2026-05-25 14:06

## 9. dashboard 现在是否显示昨日验证？

**是。** yesterday_validation=N/A（合理——昨日 match_date 无 trusted records）。累计验证显示 AB=140/88.6%。

## 10. 是否运行了 full scan？

**否。**

## 11. 是否重算了 validation？

**否。**

## 12. 是否修改了策略？

**否。**

## 13. 是否修改了 candidate？

**否。** `candidate_touched=true`（从 today scan 更新），但 `v4_candidate_numbers_changed=false`。

## 14. 是否修改了 cron？

**否。** `cron_modified=false`

## 15. 是否推 QQ / cloud publish？

**否。** `QQ_push=false`, `cloud_publish=false`

## 16. 是否需要 BOSS 授权下一步？

**否。** 自动修复成功。dashboard 已恢复。

---

## 根因结论

```
ROOT_CAUSE: SOURCE_HASH_ALLOWLIST_STALE
FIX: 更新 allowlist 包含 20260525 路径 → 重跑 after-scan refresh
```

### 禁止项确认

| 项目 | 状态 |
|:--|:--:|
| full_scan_ran | false |
| capture_ran | false |
| validation_recomputed | false |
| strategy_changed | false |
| candidate_changed | false |
| result_validation_changed | false |
| script_validation_changed | false |
| live_bet_real_records_modified | false |
| v2_restored | false |
| v33_active | false |
| outside_57_mixed_into_official | false |
| QQ_push | false |
| cloud_publish | false |
| cron_modified | false |
| secrets_printed | false |
| secrets_committed | false |

---

**V3V4_DASHBOARD_TODAY_AUTO_UPDATE_MISSING_RECOVERY_PASS**
