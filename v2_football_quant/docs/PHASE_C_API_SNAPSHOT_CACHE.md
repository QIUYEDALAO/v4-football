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

## C.5（后续，未开始）
- 可讨论非关键模块只读读取 cache；
- V2/V4 正式接 cache 仍需单独 BOSS 指令与生产验证阶段。
