# V4 Collection Pipeline Daily Shadow Canary (2026-05-30)

## 目标边界
- 本轮不是正式切换。
- 本轮新增的是每日观察工具，不是生产任务切换。
- daily shadow canary 不接入 12:00 正式 cron。
- `official_legacy` 仍是默认生产链路。
- `rf_lazy_shadow` 仍需显式传参。

## daily 工具口径
- runner: `tools/run_v4_collection_pipeline_daily_shadow_canary.py`
- checker: `tools/check_v4_collection_pipeline_daily_shadow_canary.py`
- 默认参数：
  - `window=midday`
  - `fixture-universe=whitelist`
  - `scan-engine=serial`
  - `max-fixtures=15`
  - `no-push=true`
- 每次都显式运行：
  - `official_legacy`
  - `rf_lazy_shadow`

## 本次执行（样例）
- 命令：
  - `python3 tools/run_v4_collection_pipeline_daily_shadow_canary.py --scan-date 20260530 --max-fixtures 15`
  - `python3 tools/check_v4_collection_pipeline_daily_shadow_canary.py`
- 结果摘要：
  - official raw/scout/A/B/C/SKIP: `15/4/0/0/0/0`
  - lazy raw/scout/A/B/C/SKIP: `15/15/0/0/0/0`
  - lazy scout=0 风险：`False`
  - official grade mismatch: `0`
  - official fixture 覆盖：`True`
  - shadow-only pending hits：`0`
  - estimated_saved：`27`

## 安全结论
- daily canary 只做观察，不进入正式推荐链路。
- 不进入 validation。
- 不进入 live bet。
- 不推 QQ。
- 不提交 runtime artifact。

## 红线确认
- DEFAULT_RULES 未改。
- A/B 阈值未改。
- cron 未改。
- validation 未重算。
- validation 历史未改。
- live bet 原始记录未改。
- QQ 未推。

## 后续约束
- 如需接入自动定时（含 cron），必须 BOSS 单独授权。
- 在授权前，daily shadow canary 仅用于手动/准自动观测。
