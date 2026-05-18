# V2 Controlled Single-window Resume (Phase D.8.8)

> 本文档定义 D.8.8 单窗口受控执行与审计口径。

## 1. 定位

- D.8.8 是单窗口受控执行（controlled single-window observe）。
- 本轮实际执行范围是 `preflight_observe_only`。
- 不是真实 window worker live。
- 不是生产恢复执行。
- 不是全量恢复生产。
- 不进入 Phase E。

## 2. 固定边界

- 不推 QQ
- 不写 verified
- 不写 `PRODUCTION_VERIFIED`
- 不启用全局 cron
- 不调用 API / 不读取 API key
- 不允许 AI 自由 kill/retry

## 3. 执行模式

- 仅允许 `window=midday`
- 必须同时开启：`--no-push --no-settlement-write --require-preflight`
- settlement preflight 必须参与路径
- block 时不调用 `verify_date`（沿用 D.7.3 证据）
- block 时不写 verified（沿用 D.7.3 证据）

执行范围字段必须为：
- `controlled_preflight_observe_performed=true`
- `live_window_worker_executed=false`
- `production_resume_executed=false`
- `production_task_triggered=false`
- `execution_scope=preflight_observe_only`

## 4. 安全降级

- 若无法安全调用正式 worker，降级为 `plan-only WARN`。
- 降级不等于失败，但必须可审计并解释原因。
- 失败只报告 watchdog 状态。

## 5. 结果判定

- `execution_status=PASS/WARN/FAIL/BLOCKER`
- `execution_performed=true` 仅表示 preflight observe 已运行，不表示真实 worker 已运行
- `qq_sent=false`
- `verified_written=false`
- `cron_modified=false`
- `full_cron_enabled=false`
- `production_verified=false`

## 6. 下一步

- D.8.9 才能进入 post-run review。
- 如需真实 single-window worker observe，必须单独进入 D.8.10 指令。
- Phase E 仍不得自动进入。
