# V4 Outside57 Full Scan Parallel Architecture Fix

**Phase**: V4-OUTSIDE57-FULL-SCAN-PARALLEL-ARCHITECTURE-FIX-20260527  
**Status**: `V4_OUTSIDE57_FULL_SCAN_PARALLEL_ARCHITECTURE_FIX_PASS`  
**Commit**: `b1e4a90`  
**Date**: 2026-05-27

## Overview

将 outside_57 全量扫描从逐场串行 I/O 架构改为并行架构。保留全量覆盖，不跳过 H2H/recent form，不修改策略/评级。

原问题确认：扫描速度慢的根本原因是串行 I/O 架构——每场比赛 H2H、主队近况、客队近况、events 等 API 调用全部串行执行，240 场比赛 × 每场 4-20 秒 = ~35 分钟。

## Architecture Changes

### Before (Serial)
```
for fx in fixtures:                    # 逐场串行
    evaluate_h2h_edge(home, away)       # H2H (1-5s)
        → H2H API call
        → home recent form API call     # 串行等待
        → away recent form API call     # 串行等待
        → events API calls × N          # 串行等待
    build_ht_recommendation(result)     # 评分
```

### After (Parallel)
```
RateLimiter(290 RPM, 300 hard cap)      # 全局 RPM 限速
InFlightLimiter(max 30)                 # 全局 in-flight 上限
ThreadPoolExecutor(8 workers)           # fixture 级并发
  for each fixture:
    ThreadPoolExecutor(4)               # 单场内部并发
      → H2H API call
      → home recent API call            # 并行
      → away recent API call            # 并行
      → odds API call                   # 并行
    evaluate_h2h_edge()                 # 复用 fetch 结果
    build_ht_recommendation()           # 评分
Outside57Cache (12h/24h TTL)            # 独立缓存
ProgressMarker                          # 断点续跑
```

## New File: engine/v4_outside57_scanner.py

Comprehensive parallel scanner (922 lines) with:
- `RateLimiter` class: 线程安全 60s 滑动窗口 RPM limiter
- `InFlightLimiter` class: 全局 threading.Semaphore in-flight 控制
- `Outside57Cache` class: 文件级缓存，namespace 隔离
- `Outside57ApiClient` class: 线程安全 API client，集成 requests.Session
- `_process_one_fixture()`: 单场并发 fetch + score
- `ProgressMarker` class: atomic write 断点续跑
- `run_outside57_scan()`: 主入口，worker pool 编排

## Key Parameters

| Parameter | Default | Max |
|-----------|---------|-----|
| workers | 8 | 12 |
| api-rpm | 290 | 300 (hard cap) |
| max-inflight | 30 | 30 |
| api-timeout | 12s | — |
| fixture-timeout | 35s | — |
| retry | 2 | — |
| resume | off | — |

## Safety Guarantees

- 全量覆盖：每场都有明确最终状态 (DONE/API_TIMEOUT/SCORE_ERROR/FAILED_WITH_REASON)
- 不跳过 H2H (evaluate_h2h_edge)
- 不跳过 recent form (last_n=10)
- RPM 不超过 300（60s 滑动窗口强制 backoff）
- In-flight 不超过 30（全局 Semaphore）
- 429 指数退避
- 不写入 official candidate / validation / live bet / QQ
- 不修改策略阈值 / candidate 评级 / cron
- 不打印 secrets

## Checker

`tools/check_v4_outside57_parallel_architecture.py` — 44/44 checks passed.

Coverage: full coverage, no topN, no skip H2H/recent, worker pool, rate limiter, in-flight semaphore, HTTP session reuse, cache, timeout/retry/backoff, resume, isolation, prohibition items.

## Usage

```bash
# 全量并行扫描
python3 engine/v4_outside57_scanner.py

# 自定义参数
python3 engine/v4_outside57_scanner.py --workers 8 --api-rpm 290 --max-inflight 30

# 断点续跑
python3 engine/v4_outside57_scanner.py --resume --run-id outside57_20260527_001

# 运行 checker
python3 tools/check_v4_outside57_parallel_architecture.py
```

## Answers to Key Questions

1. 原问题是串行 I/O 架构问题 → **Yes**
2. 保留 outside_57 全量扫描 → **Yes**
3. 未减少比赛数量 → **Yes**
4. 未使用 topN 替代全量 → **Yes**
5. 未跳过 H2H → **Yes**
6. 未跳过 recent form → **Yes**
7. recent form 仍是最近10场 → **Yes**
8. 并发 worker 默认 = 8 → **Yes**
9. worker 上限 = 12 → **Yes**
10. 单场内部并发 fetch → **Yes**
11. 默认 RPM = 290 → **Yes**
12. RPM 硬上限 = 300 → **Yes**
13. 实测 rpm_peak_60s → 待实际运行（需 API key 环境）
14. 是否超过 300 RPM → 强制 backoff 机制保证不超过
15. 超过自动 backoff → **Yes**
16. max in-flight = 30 → **Yes**
17. 实测 peak_inflight → 待实际运行
18. 是否超过 30 → Semaphore 机制保证不超过
19. HTTP session 复用 → **Yes** (requests.Session + HTTPAdapter)
20. recent form cache → **Yes** (12h TTL)
21. H2H cache → **Yes** (24h TTL)
22. event cache → **Yes** (24h TTL)
23. timeout / retry / resume → **Yes**
24-27. 全量完整性 → processed_fixture_count == input_fixture_count 硬保证
28. 相比串行提升 → 理论 3-5x（待实际测速）
29. 不写 official candidate → **Yes**
30. 不触发 validation → **Yes**
31. 不影响 live bet → **Yes**
32. 不推 QQ → **Yes**
33. 不修改 official scan → **Yes**
34. 不修改策略/candidate/cron → **Yes**

## Compliance

| Item | Status |
|------|--------|
| serial_io_architecture_fixed | true |
| full_outside57_coverage_preserved | true |
| topn_replacement_used | false |
| h2h_skipped | false |
| recent_form_skipped | false |
| recent_form_scoring_sample_size_10 | true |
| api_rpm_default_290 | true |
| api_rpm_hard_cap_300 | true |
| max_inflight_requests_lte_30 | true |
| official_scan_modified | false |
| strategy_changed | false |
| candidate_rating_changed | false |
| outside57_mixed_into_official | false |
| outside57_mixed_into_validation | false |
| outside57_mixed_into_live_bet | false |
| validation_recomputed | false |
| live_bet_raw_records_modified | false |
| QQ_recommendation_pushed | false |
| cloud_publish | false |
| cron_modified | false |
| secrets_printed | false |
| secrets_committed | false |
