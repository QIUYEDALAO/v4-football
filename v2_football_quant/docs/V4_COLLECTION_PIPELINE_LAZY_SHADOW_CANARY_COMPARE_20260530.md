# V4_COLLECTION_PIPELINE_LAZY_SHADOW_CANARY_COMPARE_20260530

## 1) 本轮定位
本轮是 canary compare，不是正式切换。

## 2) 默认仍不变
`official_legacy` 仍是默认模式；`rf_lazy_shadow` 仍需显式传参 `--collection-mode rf_lazy_shadow`。

## 3) 为什么要做双链路对比
直接切换生产风险高。需要在相同日期、相同样本池、相同 `max-fixtures` 下，量化比较 old/new 两条链路的产物与成本差异。

## 4) 对比方法
工具 `tools/run_v4_collection_pipeline_canary_compare.py` 强制：
- `--no-push`
- `--scan-engine serial`
- 同一 `scan_date/window/fixture_universe/max_fixtures`
- 先跑 `official_legacy`，再跑 `rf_lazy_shadow`

## 5) 如何判断 scout row 是否丢失
核心看：
- official_legacy `scout_row_count`
- rf_lazy_shadow `scout_row_count`
- `no_scout_zero` 标志

如果 lazy 出现 `scout_row_count=0`，视为阻断。

## 6) 如何判断 official grade 是否未被覆盖
通过 fixture_id 交集逐场比较 official grade：
- `common fixture` 的 official grade 是否一致
- `comparison.no_regrade.ok` 必须为 true

## 7) 如何判断 H2H / Events / CPL 节省
仅看 lazy 产物字段：
- `h2h_required/collected/skipped`
- `events_required/collected/skipped`
- `cpl_required/collected/skipped`
- `estimated_expensive_calls_saved`

该值是采集层估算，不是生产收益结论。

## 8) 为什么不能直接改 12:00 cron
canary 仍是小样本、显式参数运行；尚未形成多日稳定证据。未经 BOSS 单独授权，不得把 `rf_lazy_shadow` 写入正式 cron 默认。

## 9) 安全边界
本轮保持：
- 不改 official grade
- 不改 DEFAULT_RULES
- 不改 A/B 阈值
- 不改 cron
- 不重算 validation
- 不改 live bet
- 不推 QQ
- 不提交 runtime artifact

## 10) 后续门槛
若要正式切换，必须满足：
1. 连续多日 canary compare 稳定
2. 无 scout=0 风险
3. 无 regrade 风险
4. BOSS 单独授权
