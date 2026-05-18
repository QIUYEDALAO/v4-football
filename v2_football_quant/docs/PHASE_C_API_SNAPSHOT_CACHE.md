# PHASE_C_API_SNAPSHOT_CACHE

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
  - 生成 snapshot bundle；
  - 写入 `data/runtime/cache/api_snapshot/YYYYMMDD/bundle.json`。

- `tools/api_snapshot_cache_dryrun.py`
  - 执行只读 dry-run；
  - 支持 `--module all|v2|v4_scan|v4_review|dashboard|ledger`；
  - 写状态 marker：
    - `data/runtime/status/api_snapshot_cache_dryrun_YYYYMMDD.json`

## 运行方式
```bash
python3 tools/api_snapshot_cache_dryrun.py --date 20260517 --module all
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

