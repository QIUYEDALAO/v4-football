# V2 Live Worker Safety Wrapper (Phase D.8.11)

## 1. 定位

- D.8.11 仅生成 `safety wrapper` 计划与门禁。
- 本轮是 `plan-only`，不执行 live worker，不执行 supervisor。
- 不是生产恢复，不等于 `PIPELINE_READY` / `PRODUCTION_VERIFIED`。

## 2. 强制参数

执行命令必须包含：

- `--plan-only`
- `--no-push`
- `--no-formal-state-write`
- `--no-verified-write`
- `--no-supervisor`

缺任一参数直接 `BLOCKER`。

## 3. 禁止行为

- 禁止调用 `engine/v2_window_checker_with_watchdog.py`
- 禁止调用正式 `engine/v2_window_worker.py` live 写入
- 禁止写正式 `data/state/selected_fixtures_*.json`
- 禁止推 QQ、写 verified、改 cron、调用 API、读取 key

## 4. future live observe plan

- `allowed_future_scope=single_window_only`
- `supervisor_allowed=false`
- `no_push_required=true`
- `no_formal_state_write_required=true`
- `no_verified_write_required=true`
- `preflight_required=true`
- `watchdog_required=true`
- `boss_approval_required=true`
- `next_gate=D.8.12_LIVE_WORKER_OBSERVE_APPROVAL`

## 5. 结论口径

- D.8.11 只做 safety wrapper，未执行 live。
- `live_worker_executed=false`
- `supervisor_executed=false`
- `formal_state_written=false`
- `qq_sent=false`
- `verified_written=false`
- `cron_modified=false`
- `api_called=false`

## 6. 下一步

- 已进入 D.8.12 审批门禁（approval gate only）。
- D.8.12 不执行 live worker、不执行 supervisor，只做 readiness 审核。
- Phase E 仍不得自动进入。
