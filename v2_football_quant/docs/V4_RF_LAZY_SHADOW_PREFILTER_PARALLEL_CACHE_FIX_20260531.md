# V4_RF_LAZY_SHADOW_PREFILTER_PARALLEL_CACHE_FIX_20260531

## 目标
本轮修复的是 `rf_lazy_shadow` 的串行设计瓶颈，不是把问题归咎于 API-Football 网络。

## 背景结论
- OpenClaw 审计已确认：API endpoint RTT 不是主因。
- 慢因来自代码链路：单场 prefilter 串行调用 recent_home、recent_away、odds、coverage。
- 历史日志出现 H2H 间隔 47-74s，属于链路等待放大。

## 本轮改动
1. 仅在 `collection_mode=rf_lazy_shadow` 启用 per-fixture prefilter 并行。
2. 每场 prefilter 内部并行 4 个任务（`max_workers=4`）：
   - home recent form
   - away recent form
   - opening odds
   - league coverage
3. 保持 `official_legacy` 链路不变。
4. 子任务异常时降级为安全默认值，不删除 scout row。

## Cache 设计（per-run 内存级）
- Recent Form: `team_id + last_n + include_events`
- Opening Odds: `fixture_id`
- Coverage: `league_id + season`
- H2H: `home_team_id + away_team_id`
- Events: `fixture_id`

说明：仅运行期内存缓存，不做持久化缓存。

## Runtime Cost Profile
新增全局与逐场性能字段，用于直接定位慢因：
- 全局：`runtime_cost_profile`（总耗时、平均每场、分模块总耗时、分模块 API 调用数、cache hit/miss、slowest top5）
- 每场：`prefilter_elapsed_ms`、`recent_home_elapsed_ms`、`recent_away_elapsed_ms`、`odds_elapsed_ms`、`coverage_elapsed_ms`、`h2h_elapsed_ms`、`events_elapsed_ms`、`slowest_stage`、`api_call_count`、`cache_hit_count`、`cache_miss_count`

## 安全边界确认
- official_legacy 未改。
- official grade 未改。
- DEFAULT_RULES 未改。
- cron 未改。
- validation / validation history 未改。
- live bet 未改。
- QQ 未推。

## 结论
本轮是 `rf_lazy_shadow` 性能链路修复，不代表正式切换。
正式切换与 cron 调整仍需 BOSS 单独授权。
