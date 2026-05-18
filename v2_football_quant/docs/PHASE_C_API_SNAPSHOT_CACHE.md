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
- Phase C.3：可讨论 controlled ingest 设计（仍需 BOSS 单独确认，不落生产）。
- Phase C.4：可讨论非关键模块只读接 cache（仍需 BOSS 单独确认）。
- **V2/V4 正式链路接 cache 必须另开 BOSS 确认，且不在当前阶段实施。**
