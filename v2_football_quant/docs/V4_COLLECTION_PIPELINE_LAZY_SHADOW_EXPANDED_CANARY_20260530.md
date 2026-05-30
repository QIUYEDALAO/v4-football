# V4 Collection Pipeline Lazy Shadow Expanded Canary (2026-05-30)

## 结论范围
- 本轮不是正式切换。
- 本轮是 `max-fixtures=15` 的扩大 canary。
- `official_legacy` 仍是默认生产模式。
- `rf_lazy_shadow` 仍需显式 `--collection-mode rf_lazy_shadow`。

## 为什么要扩大样本
- `max-fixtures=5` 只能验证小样本稳定性。
- 扩大到 15 后，才能更有效验证：
  - lazy 模式是否仍避免 `scout=0` 风险。
  - common fixtures 上 official grade 是否保持一致。
  - official fixture 覆盖与 shadow-only 隔离是否稳定。
  - H2H/events/CPL 节省量在更大样本下是否持续。

## 执行口径
- dates: `20260530, 20260529, 20260528`
- window: `midday`
- fixture_universe: `whitelist`
- scan_engine: `serial`
- max_fixtures: `15`（每个日期固定）
- 每个日期两条链路都显式执行：
  - `official_legacy`
  - `rf_lazy_shadow`
- 全部 `--no-push`

## 每日期结果
- 20260530
  - official raw/scout/A/B/C/SKIP: `15/4/0/0/0/0`
  - lazy raw/scout/A/B/C/SKIP: `15/15/0/0/0/0`
  - common fixtures mismatch: `0`
  - official fixture 覆盖缺失: `0`
  - official A/B 覆盖缺失: `0`
  - estimated saved: `27`
- 20260529
  - official raw/scout/A/B/C/SKIP: `15/1/0/0/0/0`
  - lazy raw/scout/A/B/C/SKIP: `15/15/0/0/0/0`
  - common fixtures mismatch: `0`
  - official fixture 覆盖缺失: `0`
  - official A/B 覆盖缺失: `0`
  - estimated saved: `32`
- 20260528
  - official raw/scout/A/B/C/SKIP: `15/0/0/0/0/0`
  - lazy raw/scout/A/B/C/SKIP: `15/15/0/0/0/0`
  - common fixtures mismatch: `0`
  - official fixture 覆盖缺失: `0`
  - official A/B 覆盖缺失: `0`
  - estimated saved: `29`

## 聚合结果
- dates_total/passed/blocked: `3/3/0`
- total_official_scout: `5`
- total_lazy_scout: `45`
- total_common_fixtures: `5`
- total_official_grade_mismatch: `0`
- total_expensive_calls_saved: `88`
- any_scout_zero: `False`
- any_regrade: `False`

## 关键稳定性结论
- lazy 在本轮未出现 `raw>0 且 scout=0`。
- common fixtures official grade mismatch = `0`。
- official fixture IDs 全部被 lazy 覆盖。
- official A/B fixture IDs 全部被 lazy 覆盖（本轮为 0，故 vacuously true）。

## shadow-only 隔离结论
- `shadow_only_not_in_pending_bet_candidates`: `hits=0`。
- validation 未使用 shadow grade（dashboard review checker PASS）。
- live bet 未使用 shadow grade（dashboard review checker PASS）。
- QQ 未使用 shadow grade（dashboard review checker PASS）。

## H2H / Events / CPL 节省统计（expanded checker聚合）
- h2h_required true/false: `25/20`
- h2h_collected/skipped: `25/20`
- events_required true/false: `22/23`
- events_collected/skipped: `4/23`
- cpl_required true/false: `0/45`
- cpl_collected/skipped: `0/45`
- estimated_expensive_calls_saved: `88`

## 红线确认
- DEFAULT_RULES 未改。
- A/B 阈值未改。
- cron 未改。
- validation 未重算。
- validation 历史未改。
- live bet 原始记录未改。
- QQ 未推。
- runtime artifact 未提交。

## 为什么还不能直接改 12:00 cron
- 本轮仍是 canary 观测，不是生产切换授权。
- 需要 BOSS 单独授权，才可讨论默认链路切换。

## 下一步边界
- 仍不得把 `rf_lazy_shadow` 设为默认。
- 仍不得进入正式切换。
- 任何 cron 变更需 BOSS 单独授权。
