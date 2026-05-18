# V2 Live Worker Observe Approval Gate (Phase D.8.12)

## 1. 定位

- D.8.12 是 live worker observe 执行前的**最终审批门禁**。
- 本轮只做 approval gate / readiness review，不执行 live worker。
- 本轮不执行 supervisor，不推 QQ，不写正式 state，不写 verified。

## 2. 固定口径

- `current_level=CODE_READY`
- `PIPELINE_READY=false`
- `PRODUCTION_VERIFIED=false`
- `live_worker_observe_approved=false`
- `live_worker_execution_allowed=false`
- `supervisor_execution_allowed=false`
- `formal_state_write_allowed=false`
- `qq_push_allowed=false`
- `verified_write_allowed=false`
- `cron_enable_allowed=false`

## 3. 审批门禁检查项

- D.8.10 sandbox 证据是否完整并保持 formal state unchanged。
- D.8.11 safety wrapper 是否 plan-only 且未执行 live。
- supervisor 直接 QQ 推送风险是否仍存在。
- worker 正式 state 写回风险是否仍存在。
- no-push / no-formal-state-write / no-verified-write hook 是否完整。
- safe sender guard 是否完整。
- watchdog-only failure reporting 是否可用。

## 4. 决策规则

- 若证据缺失或越界：`BLOCKER`。
- 若门禁不完整（如 no-write hook/safe-sender guard 缺口）：`NOT_READY` 或 `WARN`。
- 仅当风险闭合并且仍需 BOSS 审批时才可 `READY_FOR_BOSS_REVIEW`。
- 任何情况下本轮都不得变更为 `PRODUCTION_VERIFIED`。

## 5. 下一步

- 仅在 BOSS 明确批准后，才可进入 D.8.13 草案或后续执行门禁。
- Phase E 仍不得自动进入。
