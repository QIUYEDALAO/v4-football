# V4 Fixture ID Validation Blocked Closeout Safety Acceptance

**Date:** 2026-05-25  
**Final Status:** V4_FIXTURE_ID_VALIDATION_BLOCKED_CLOSEOUT_SAFE  

---

## 1. 当前为何 BLOCKED？

API_PROVIDER_OR_HEADER_BLOCKED。本地 `config.secrets.API_KEY` 不可用。
但 cron 环境通过 `export APIFOOTBALL_KEY=$OPENC_APIFOOTBALL_KEY` 配置了 API key。

## 2. 是否因为 API key 缺失？

**是。** 本地开发环境（无 cron 上下文）无法获取 API key。cron 执行时 API key 存在。

## 3. 已新增接线是否会影响明天 cron？

**不会。** 已验证：
- `run_v3v4_dashboard_daily_update.py` 13:00/13:30 runner：新增的 fixture_id 调用使用 `subprocess.run()` 带 `timeout=240` 和 `capture_output=True`。API key 缺失时返回 `returncode != 0`，runner 将其加入 warnings 而非 blockers，不影响 dashboard 刷新。
- `run_v3v4_validation_final_and_dashboard_refresh.py` 14:00 runner：同样用 `run_step()` 封装，`timeout=120`，异常不影响主流程。

## 4. API 缺失时是否 hard fail？

**否。** `net_utils.api_get()` 在 API key 缺失时返回 `None`，不抛异常。
`fixture_id_validator` 处理 `None` 为 `{}`，标记 `API_ERROR` 并跳过该场。安全降级。

## 5. API 缺失时 dashboard 会显示什么？

`safe_na_reason` 写入验证摘要。dashboard 显示 N/A + `OFFICIAL_SETTLED_SAMPLE_MISSING_OR_API_TIMEOUT`。
不会伪造命中率。不会标记 validation success。

## 6. 13:00 runner 是否安全？

**是。** `V4_VALIDATION_DRY_RUN` 使用 `v4_ht_result_validator.py`，未修改。与 fixture_id 无关。

## 7. 14:00 final runner 是否安全？

**是。** 修改为调用 `run_v4_official_fixture_id_validation.py`。使用 `subprocess` + `timeout=120` + `capture_output=True` + try/except JSON 解析。API key 缺失时返回非零但不中断主流程。

## 8. 是否需要回滚？

**不需要。** 所有新增/修改都是安全降级设计。即使 API key 缺失也不会导致 cron 失败。
如需保留旧 match_date 路径作为 fallback，可后续加 feature gate，但当前状态已安全。

## 9. 是否需要 BOSS 配置 API key？

**本地开发需要。** 当前 `config.secrets.API_KEY` 未配置。cron 环境正常工作。
如需本地开发验证 fixture_id 路径，需在 OpenClaw `.env` 或 `openclaw.json` 中配置 `API_FOOTBALL_KEY` 或 `OPENCLAW_APIFOOTBALL_KEY`。

## 10. 是否改了策略？

**否。**

## 11. 是否改了 candidate？

**否。**

## 12. 是否改了 validation 历史数字？

**否。** `result_validation_history_changed=false`，`script_validation_history_changed=false`。

## 13. 是否运行 full scan？

**否。** `full_scan_ran=false`。

## 14. 是否 cloud / QQ / cron？

全部 `false`。

## 15. 是否可以带着 safe fallback 等待 API key 后再验收？

**可以。** 当前状态：
- 所有 runner 在 API key 缺失时返回 safe N/A
- Dashboard 不伪造数据
- 累计验证不受影响
- 候选区不受影响
- 无 hard crash

只需 BOSS 配置本地 API key 后即可验收 fixture_id validation 的真实输出。

---

## 禁止项确认

| 项目 | 状态 |
|:--|:--:|
| full_scan_ran | false |
| capture_ran | false |
| strategy_changed | false |
| candidate_changed | false |
| candidate_rating_changed | false |
| result_validation_history_changed | false |
| script_validation_history_changed | false |
| brief_used_for_hit_rate | false |
| scan_date_used_for_validation | false |
| scout_full_pool_used | false |
| outside_57_mixed_into_official | false |
| live_bet_real_records_modified | false |
| v2_restored | false |
| v33_active | false |
| QQ_push | false |
| cloud_publish | false |
| cron_modified | false |
| secrets_printed | false |
| secrets_committed | false |
