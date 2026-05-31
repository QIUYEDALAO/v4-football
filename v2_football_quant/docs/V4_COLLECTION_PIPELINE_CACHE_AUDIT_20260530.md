# V4_COLLECTION_PIPELINE_CACHE_AUDIT_20260530

## 1. 目标与边界
- 本轮是 **缓存审计**，不是正式切换。
- 审计范围：`official_legacy` + `rf_lazy_shadow` 下的采集缓存与 lazy skip 行为。
- 未修改 `DEFAULT_RULES`、A/B 阈值、official grade、cron、validation、live bet、QQ 推送。

## 2. 缓存审计结论（代码级 + 近期 canary 运行态证据）

### 2.1 Recent Form cache
- 状态：已存在。
- 位置：`/Users/liudehua/.openclaw/workspace/v2_football_quant/engine/data_sources/h2h_engine.py`
- key 形状：`(team_id, last_n, include_events)`。
- 证据：`_RECENT_PROFILE_CACHE`、`_query_recent_goal_profile`、`warm_recent_goal_profiles`、`recent_profile_cache_stats`。
- 风险评估：`LOW`（同 run 内 team 级重复请求已显著抑制）。

### 2.2 Pair H2H cache
- 状态：已存在（通过 API endpoint 归一化缓存）。
- 位置：
  - `engine/v4_runner.py`：`_cached_api_client` + `_normalize_endpoint`
  - `engine/data_sources/h2h_engine.py`：`fixtures/headtohead?h2h=<home>-<away>`
- key 形状：`normalized endpoint fixtures/headtohead?h2h=<home>-<away>`（run 内内存缓存）。
- 风险评估：`LOW`。

### 2.3 Opening Market cache
- 状态：已存在（通过 API endpoint 归一化缓存）。
- 位置：`engine/v4_runner.py`（`odds?fixture=<fixture_id>`）。
- key 形状：`normalized endpoint odds?fixture=<fixture_id>`（run 内内存缓存）。
- 风险评估：`LOW`。
- 额外确认：`NO_MARKET` 会写入状态字段，不会无限重查同一 fixture。

### 2.4 Events / Time Bin cache
- 状态：已存在（通过 API endpoint 归一化缓存）。
- 位置：
  - `engine/data_sources/h2h_engine.py`：`fixtures/events?fixture=<fixture_id>`
  - `engine/v4_runner.py`：统一走 `_cached_api_client`
- key 形状：`normalized endpoint fixtures/events?fixture=<fixture_id>`（run 内内存缓存）。
- 风险评估：`MEDIUM`（无独立持久层，仅依赖本轮 endpoint 缓存；安全但可持续观察）。

### 2.5 CPL cache / placeholder
- 状态：仍为 placeholder-only。
- 位置：`engine/v4_runner.py`
- 结论：
  - `cpl_collected=False`
  - `cpl_required=true` 时仅标记 `PLACEHOLDER_ONLY`
  - 不触发外部 CPL 数据调用
- 风险评估：`LOW`（不影响官方判级）。

## 3. Lazy skip 行为审计
- `h2h_required=false`：跳过 H2H enrich，保留 scout row。
- `events_required=false`：跳过 events enrich，保留 scout row。
- `cpl_required=false`：跳过 CPL，保留占位字段。
- 运行证据来源：最近 daily shadow canary artifact（`max-fixtures=15`）与 direct lazy shadow checker。

## 4. 安全边界审计
- official grade 污染风险：未发现（common fixtures mismatch=0）。
- validation 风险：未发现（未触碰）。
- live bet 风险：未发现（未触碰）。
- QQ 推送风险：未发现（未推）。
- cron 风险：未发现（未改，`official_legacy` 仍默认）。

## 5. 重复请求风险总体评估
- Recent Form：LOW
- Pair H2H：LOW
- Opening Market：LOW
- Events：MEDIUM（仅 run 内 endpoint cache，建议持续观测）
- CPL：LOW（placeholder）

## 6. REVIEW_REQUIRED 项
- 当前无阻断级问题。
- 建议持续观察项：
  - Events 仅 run 内缓存策略在更大样本/更长窗口的稳定性（非本轮改造项）。

## 7. 结论
- 本轮结论：**PASS**（缓存审计完成，未发现 official/validation/live bet/QQ 污染）。
- 本轮不代表正式切换，不启用 cron lazy。
- 如需后续“补缓存/持久缓存层”改造，需 BOSS 单独授权。
