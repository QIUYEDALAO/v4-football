# PHASE_C_API_SNAPSHOT_CACHE

当前阶段状态：`CODE_READY`

本文件描述的是 Phase C 的**框架与验证层**，不是生产接入说明。

## 范围（仅框架）
本阶段当前只落地 **API Snapshot / Cache 框架 + 只读 dry-run**。

明确不做：
- 不接入生产 cron；
- 不改 V2/V3/V4 策略；
- 不改 BET_LOCKED；
- 不让 V2/V4 正式链路立刻依赖 cache；
- 不调用外部 API；
- 不推 QQ；
- 不写 PRODUCTION_VERIFIED。

## 新增组件
- `engine/api_snapshot_cache.py`
  - 统一 canonical runtime root；
  - 按模块发现只读源文件；
  - 生成 snapshot bundle（`schema_version=api_snapshot_cache.v1`）；
  - 写入 `data/runtime/cache/api_snapshot/YYYYMMDD/bundle.json`。

- `tools/api_snapshot_cache_dryrun.py`
  - 执行只读 dry-run；
  - 支持 `--module all|v2|v4_scan|v4_review|dashboard|ledger`；
  - 支持 `--check`（仅调用本地 checker）；
  - 写状态 marker：
    - `data/runtime/status/api_snapshot_cache_dryrun_YYYYMMDD.json`

- `tools/check_api_snapshot_cache.py`
  - 独立校验 bundle schema / integrity / secret 风险；
  - 写 checker marker：
    - `data/runtime/status/api_snapshot_cache_check_YYYYMMDD.json`

## 运行方式
```bash
python3 tools/api_snapshot_cache_dryrun.py --date 20260517 --module all
python3 tools/check_api_snapshot_cache.py --date 20260517
# 或一次执行
python3 tools/api_snapshot_cache_dryrun.py --date 20260517 --module all --check
```

## 输出
- bundle：
  - `data/runtime/cache/api_snapshot/20260517/bundle.json`
- marker：
  - `data/runtime/status/api_snapshot_cache_dryrun_20260517.json`

## 口径
1. 主源固定项目内 runtime root：`data/runtime`。  
2. workspace 根 runtime 只允许 warning，不允许作为主源。  
3. reading/status 结果不等于 production verified。  
4. dry-run 仅用于框架验证，不代表生产任务完成。  
5. `production_dependency=false` 必须维持，V2/V4 正式链路不得依赖 cache。  
6. `no_api/no_push/no_strategy_recompute/no_cron` 必须为 true。  
7. 当前禁止写 `PRODUCTION_VERIFIED`。  

## 路线图约束
- Phase C.2：仅做 schema/checker/只读展示增强（当前阶段）。
- Phase C.3：controlled ingest **simulation**（本地模拟，不触发真实 API）。
- Phase C.4：可讨论 controlled real ingest（必须 BOSS 单独确认）。
- Phase C.5：可讨论非关键模块只读接 cache（仍需 BOSS 单独确认）。
- **V2/V4 正式链路接 cache 必须另开 BOSS 确认，且不在当前阶段实施。**

## Phase C.3（本轮）规则
1. 只生成 `controlled_ingest_plan.json` 与 status/check marker。  
2. 不调用真实 API。  
3. 不读取真实 `APIFOOTBALL_KEY`。  
4. 不写真实 snapshot。  
5. 不更新生产 cache 索引。  
6. 不让 V2/V4 正式链路依赖 cache。  
7. 不推 QQ，不接 cron，不写 `PRODUCTION_VERIFIED`。  

## C.4 预告（未开始）
## C.4 Controlled Real Ingest（Smoke Test 口径）
首次真实 API 调用必须满足：
- 只允许最小 endpoint 与最小样本；
- 明确 timeout / retry 上限；
- 明确日志脱敏；
- 明确 no-push/no-cron/no-strategy-change；
- 先本地验证，再由 BOSS 决定是否继续。

本仓 C.4 约束：
- 只允许 1 次请求（`max_requests=1`）；
- `timeout <= 10s`；
- `retry_count = 0`；
- 仅 smoke test，禁止批量抓取；
- 不接生产链路；
- 不改策略；
- 不推QQ；
- 不接 cron；
- 不写 `PRODUCTION_VERIFIED`；
- 不提交 runtime 产物；
- 真实响应仅落项目内 `data/runtime/cache/api_snapshot/YYYYMMDD/real_ingest/`；
- 严禁在 marker/log/snapshot 中泄露 API key。

## Phase C.5：Cache Read Adapter（本轮）
### 目标
- 仅新增只读读取层（reader/adapter），读取已有 `api_snapshot` 缓存产物；
- 不调用 API；
- 不读取 `APIFOOTBALL_KEY`；
- 不修改 cache/snapshot；
- 不接入 V2/V4 正式链路；
- 不替换正式 API 调用；
- 不推 QQ；
- 不接 cron；
- 不写 `PRODUCTION_VERIFIED`。

### 新增组件
- `engine/api_cache_reader.py`
  - 只读读取 `data/runtime/cache/api_snapshot/YYYYMMDD/`；
  - 输出 `api_cache_reader.v1` summary；
  - 提供边界校验（`no_api/no_key_read/no_push/no_strategy_recompute/no_cron`）。

- `tools/api_cache_reader_dryrun.py`
  - 运行 reader 并写 marker：
  - `data/runtime/status/api_cache_reader_dryrun_YYYYMMDD.json`

- `tools/check_api_cache_reader.py`
  - 校验 reader dryrun schema / boundary / secret；
  - 额外静态检查 reader 源码是否包含网络调用与 key 读取；
  - 写 checker marker：
  - `data/runtime/status/api_cache_reader_check_YYYYMMDD.json`

### Dashboard 展示
- API Snapshot / Cache 卡片增加 Cache Reader 状态（只读）：
  - reader 状态；
  - reader checker；
  - API调用=否；
  - 读取key=否；
  - snapshot 数量；
  - bundle / real snapshot 存在性；
  - secret 检查；
  - production_dependency=false；
  - production_verified=false。

## 后续路线（仍需 BOSS 单独确认）
- Phase C.6：shadow read（只读对照，不影响生产路径）
- Phase C.7：非关键链路灰度评估
- **V2/V4 正式接 cache 仍需单独 BOSS 指令 + 生产验证阶段**

## Phase C.6：Cache Shadow Read Baseline（本轮）
### 目标
- 建立 cache 只读旁路对账基线（shadow read）；
- 正式链路继续使用原数据源；
- 不接 V2/V4，不替换正式 API 调用；
- 不调用 API，不读取 API key；
- 不修改 cache，不写生产 sent marker；
- 不推QQ，不接 cron，不写 `PRODUCTION_VERIFIED`。

### 新增组件
- `engine/api_shadow_read.py`
  - 读取 cache reader summary / bundle / real ingest marker / real snapshot；
  - 输出 `api_shadow_read.v1` 对账报告；
  - 对账状态仅限 `MATCH / MISMATCH / MISSING / NOT_COMPARABLE`；
  - 明确 `business_scope.v2_production_compared=false`、
    `business_scope.v4_production_compared=false`。

- `tools/api_shadow_read_dryrun.py`
  - 生成 shadow 对账 dry-run marker：
  - `data/runtime/status/api_shadow_read_dryrun_YYYYMMDD.json`

- `tools/check_api_shadow_read.py`
  - 校验 shadow schema / boundary / secret；
  - 校验源码无网络调用、无 key 读取；
  - 写 checker marker：
  - `data/runtime/status/api_shadow_read_check_YYYYMMDD.json`

### 当前限制
- 当前真实 cache 业务面仅有最小 `status` endpoint；
- 只能做 cache 元数据与可用性对账；
- 不能代表 V2/V4 业务策略级对账结果；
- 因此 `NOT_COMPARABLE` / `WARN` 在当前阶段可接受（非边界失败）。

### 下一阶段边界
- C.7 才考虑非关键模块只读灰度；
- V2/V4 正式接 cache 仍需单独 BOSS 指令与生产验证阶段。

## Phase C.7：Non-critical Shadow Consumer（本轮）
### 目标
- 仅允许非关键模块通过 shadow consumer 旁路读取 cache；
- 允许范围：`dashboard / replay / audit`；
- 禁止范围：`v2_daily_pool / v2_window_checker / v2_settlement / v4_scan / v4_review / qq_sender`；
- 正式 V2/V4 链路继续使用原数据源；
- 保留 fallback 到原始来源能力；
- 不调用 API、不读取 API key、不改 cache、不接 cron、不推QQ、不写 `PRODUCTION_VERIFIED`。

### 核心边界
- `production_dependency=false`
- `production_verified=false`
- `production_path_untouched=true`
- `fallback_to_original_source=true`
- `cache_reader_used_as_primary=false`（replay 仅展示 shadow 状态，不替换主源）

### 当前业务范围说明
- 当前 cache 业务样本仍以 `status` endpoint 为主；
- C.7 只能证明“非关键旁路消费机制可用”，不能证明 V2/V4 业务数据一致；
- 任何把 shadow consumer 升级为生产主源的行为均不在本阶段范围内。

### 下一阶段边界
- C.8 才考虑非关键模块实际页面灰度；
- V2/V4 正式接 cache 仍需单独 BOSS 指令。

## Phase C.8：Non-critical Page-level Gray Display（本轮）
### 目标
- 新增 Dashboard 页面级灰度诊断页（API cache diagnostics）；
- 仅只读展示 cache reader / shadow read / shadow consumer / real ingest smoke 状态；
- 不改变 V2/V4 正式数据源；
- 不调用 API；
- 不读取 API key；
- 不触发任务；
- 不推QQ；
- 不接 cron；
- 不写 `PRODUCTION_VERIFIED`。

### 边界
- 本页属于工程诊断页，不代表生产接入通过；
- 本页不得提供执行按钮（run/trigger/refresh/push）；
- 正式 V2/V4 卡片继续走原来源；
- 当前仍不能说明 V2/V4 业务数据一致性。

### 下一阶段
- C.9 才考虑非关键模块“辅助展示级”使用 cache 数据（仍不接生产链路）；
- V2/V4 正式接 cache 仍需单独 BOSS 指令。

### iPhone 刷新提示（C.8.1）
- 若手机端看不到 `API缓存` 导航入口：
  1. Safari 下拉刷新；
  2. 关闭页面后重新打开；
  3. 如仍为旧版，删除主屏幕图标后重新添加。

## Phase C.9：Non-critical Auxiliary Display Gray Consumer（本轮）
### 目标
- C.9 只做“辅助展示”消费层；
- 只允许 Dashboard / Replay / Audit 展示 cache 辅助状态；
- 不替换任何正式数据源；
- 不影响推荐、结算、推送、评级。

### 严格边界
- 正式 V2/V4 卡片继续使用原来源；
- `v2_formal_cards_use_cache=false`；
- `v4_formal_cards_use_cache=false`；
- `qq_uses_cache=false`；
- 不调用 API；
- 不读取 API key；
- 不替换正式 API 调用；
- 不推 QQ；
- 不接 cron；
- 不写 `PRODUCTION_VERIFIED`。

### 本轮新增
- `engine/api_aux_display.py`：辅助展示报告聚合；
- `tools/api_aux_display_dryrun.py`：辅助展示 dry-run；
- `tools/check_api_aux_display.py`：辅助展示边界与标签检查；
- Dashboard `api_cache.html` 增加辅助展示卡片（标记“辅助展示，不作生产证据”）；
- 首页 API 缓存卡显示 aux 状态；
- Replay marker 增加 `aux_display_status`，仅展示，不改主源。

### 当前能力说明
- C.9 仅证明“非关键辅助展示层可用”；
- 当前结果仍不能说明 V2/V4 业务数据一致；
- 生产链路继续严格隔离。

### 下一阶段边界
- C.10 才考虑非关键页面局部读取 cache 数据作为辅助详情；
- V2/V4 正式接 cache 必须另开 BOSS 指令。

## Phase C.10：Non-critical Local Cache Detail Gray Display（本轮）
### 目标
- C.10 只做“局部 cache 辅助详情”展示；
- 只允许 Dashboard / Replay / Audit 看到辅助详情状态；
- 正式 V2/V4 卡片继续使用原来源；
- 不影响推荐、结算、推送、评级。

### 边界
- 仅展示 metadata，不展示 raw response 全文；
- `raw_response_hidden=true`，`raw_response_visible=false`；
- `v2_formal_cards_use_cache=false`；
- `v4_formal_cards_use_cache=false`；
- `qq_uses_cache=false`；
- 不调用 API；
- 不读取 key；
- 不替换正式 API 调用；
- 不推 QQ；
- 不接 cron；
- 不写 `PRODUCTION_VERIFIED`。

### 本轮新增
- `engine/api_aux_detail.py`：局部辅助详情聚合；
- `tools/api_aux_detail_dryrun.py`：局部详情 dry-run；
- `tools/check_api_aux_detail.py`：局部详情边界与隐藏策略检查；
- `api_cache.html` 增加局部详情卡（真实 smoke / reader / shadow）；
- 首页 API Cache 卡增加 aux detail 状态；
- replay marker 增加 `aux_detail_status`，仅展示，不改主源。

### 当前限制
- 当前仍不能说明 V2/V4 业务数据一致；
- C.10 仅证明非关键局部辅助详情层可用。

### 下一阶段边界
- C.11 才考虑“非关键页面读 cache detail 作为辅助解释”；
- V2/V4 正式接 cache 仍需另开 BOSS 指令。

## Phase C.11：Non-critical Cache Detail Explanation Layer（本轮）
### 目标
- C.11 只做 cache detail 辅助解释层；
- 只允许 Dashboard / Replay / Audit 查看解释状态；
- 正式 V2/V4 卡片继续使用原来源；
- 不影响推荐、结算、推送、评级。

### 边界
- 不调用 API；
- 不读取 key；
- 不替换正式 API 调用；
- 不推 QQ；
- 不接 cron；
- 不写 `PRODUCTION_VERIFIED`；
- 只展示解释文本与 metadata，不展示 raw response 全文；
- 明确“不能代表 V2/V4 业务一致，不能替换正式链路”。

### 本轮新增
- `engine/api_aux_explain.py`：辅助解释报告聚合（能力/限制/边界卡）；
- `tools/api_aux_explain_dryrun.py`：解释层 dry-run；
- `tools/check_api_aux_explain.py`：解释层边界/文案/secret 校验；
- `api_cache.html` 增加 cache 辅助解释区域（能证明什么/不能证明什么/生产边界/下一步缺口）；
- 首页 API Cache 卡增加 aux explain 状态；
- replay marker 增加 `aux_explain_status`，仅展示，不改主源。

### 当前限制
- 当前只能解释 cache 工程能力，不代表 V2/V4 业务一致；
- 正式 V2/V4 仍禁用 cache 作为主数据源；
- 正式链路接 cache 仍需独立生产验证阶段。

### 下一阶段边界
- C.12 才做 Cache Health Daily Summary；
- V2/V4 正式接 cache 必须另开 BOSS 指令。

## Phase C.12：API Cache Health Daily Summary（本轮）
### 目标
- C.12 只做 API Cache 工程链路的每日健康摘要；
- 汇总 C.1-C.11 的 dry-run/checker/灰度状态；
- 统一 PASS/WARN/FAIL/BLOCKER 口径；
- 持续确认正式链路隔离与安全边界。

### 严格边界
- 不调用 API；
- 不读取 key；
- 不替换正式 API 调用；
- 不推 QQ；
- 不接 cron；
- 不写 `PRODUCTION_VERIFIED`；
- 不代表 V2/V4 业务数据一致；
- 不代表 cache 已生产接入。

### 本轮新增
- `engine/api_cache_health.py`
  - 聚合 C.1-C.11 状态；
  - 统一 `overall_status` 与计数；
  - 输出 formal link / secret / raw-response 边界判定。
- `tools/api_cache_health_summary.py`
  - 生成每日健康摘要 marker：
  - `data/runtime/status/api_cache_health_summary_YYYYMMDD.json`
- `tools/check_api_cache_health.py`
  - 校验 schema / boundary / counts / limitations / secret；
  - 输出 checker marker：
  - `data/runtime/status/api_cache_health_check_YYYYMMDD.json`
- Dashboard `api_cache.html`、首页与 `system.html`
  - 接入每日健康摘要总览；
  - 展示 C.1-C.11 阶段状态汇总（只读）；
  - 保持证据路径折叠，不展示 raw response 与 key。

### 下一阶段边界
- C.13 才做 Phase C 总验收 / PR / main 合并准备；
- V2/V4 正式接 cache 必须另开 BOSS 指令。
