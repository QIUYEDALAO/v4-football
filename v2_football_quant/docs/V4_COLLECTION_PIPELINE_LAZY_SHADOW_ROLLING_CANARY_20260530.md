# V4 Collection Pipeline Lazy Shadow Rolling Canary (2026-05-30)

## 范围
- 本轮不是正式切换。
- 本轮是多日期 rolling canary。
- `official_legacy` 仍是默认生产模式。
- `rf_lazy_shadow` 仍需显式 `--collection-mode rf_lazy_shadow`。

## 为什么需要多日期验证
- 单日 `max-fixtures=5` 只能证明点状可用，不能证明稳定。
- 必须跨日期确认：
  - 不再出现 `rf_lazy_shadow` 的 `scout=0` 风险。
  - common fixtures 的 official grade 不被 shadow 覆盖。
  - H2H / Events / CPL lazy 采集节省具备连续性。

## 执行口径
- 日期：`20260530, 20260529, 20260528`
- window：`midday`
- fixture_universe：`whitelist`
- scan_engine：`serial`
- 每日都显式运行两条链路：
  - `official_legacy`
  - `rf_lazy_shadow`
- 每日都 `--no-push`
- 每日都 `--max-fixtures 5`

## 每日结果（手机可读）
- 20260530
  - official raw/scout/A/B/C/SKIP: `5/1/0/0/0/0`
  - lazy raw/scout/A/B/C/SKIP: `5/5/0/0/0/0`
  - common fixtures: `1`
  - official grade mismatch: `0`
  - estimated_saved: `11`
- 20260529
  - official raw/scout/A/B/C/SKIP: `5/0/0/0/0/0`
  - lazy raw/scout/A/B/C/SKIP: `5/5/0/0/0/0`
  - common fixtures: `0`
  - official grade mismatch: `0`
  - estimated_saved: `13`
- 20260528
  - official raw/scout/A/B/C/SKIP: `5/0/0/0/0/0`
  - lazy raw/scout/A/B/C/SKIP: `5/5/0/0/0/0`
  - common fixtures: `0`
  - official grade mismatch: `0`
  - estimated_saved: `7`

## 聚合结论
- total_official_scout: `1`
- total_lazy_scout: `15`
- total_common_fixtures: `1`
- total_official_grade_mismatch: `0`
- total_expensive_calls_saved: `31`
- `rf_lazy_shadow` 未出现 `raw>0 且 scout=0`。

## 关于 scout 行保留差异
- 本轮发现：`official_legacy` 与 `rf_lazy_shadow` 的 scout 保留口径不同（lazy 保留更多行）。
- 该差异本轮仅用于 canary 观测，不代表正式推荐、也不进入 validation/live bet/QQ。

## H2H / Events / CPL 节省观测（3日汇总）
- h2h_required true/false: `7/8`
- h2h_collected/skipped: `7/8`
- events_required true/false: `7/8`
- events_collected/skipped: `1/8`
- cpl_required true/false: `0/15`
- cpl_collected/skipped: `0/15`
- estimated_expensive_calls_saved: `31`

## 安全边界确认
- 未修改 DEFAULT_RULES。
- 未修改 A/B 阈值。
- 未修改 cron。
- 未重算 validation。
- 未修改 validation 历史。
- 未修改 live bet 原始记录。
- 未推 QQ。
- 未切换生产默认。

## 为什么不能直接改 12:00 cron
- 当前仅完成 rolling canary，对“口径差异下的生产治理策略”尚未完成正式签署。
- 在 BOSS 单独授权前，`official_legacy` 必须继续作为 cron 默认。

## 后续门槛（仅记录）
- 若要正式切换，必须 BOSS 单独授权。
- 切换前至少需要：
  - 更多日期窗口连续稳定。
  - 口径差异与下游消费（todo/validation/live bet/QQ）策略明确。
