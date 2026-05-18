# V2 Limited Resume Boss Approval Packet (Phase D.8.7)

## 1. 当前状态（审批前）

- `current_level=CODE_READY`
- `PIPELINE_READY=false`
- `PRODUCTION_VERIFIED=false`
- `ready_for_boss_review=true`
- `limited_resume_approved=false`
- `resume_execution_allowed=false`
- `cron_enable_allowed=false`
- `qq_push_allowed=false`

> D.8.7 是审批包，不是执行。

## 2. 风险分级（基于 D.8.2-D.8.6）

### WARN 风险

1. `manual_qq_push_path_exists_must_keep_disabled`
2. `safe_outbound_sender_guard_signature_missing`
3. `single-window live observe still plan-only`
4. `validation pack pack_status=WARN`

### 解释

- 以上风险不代表允许自动恢复。
- 仅表示需 BOSS 审批后决定是否进入 D.8.8。

## 3. 审批要求

- cron 启用必须单独命令
- QQ 推送必须单独命令
- limited resume execution 必须单独命令
- `PRODUCTION_VERIFIED` 禁止写入

## 4. D.8.8 草案（仅草案，不执行）

- 只允许 single-window controlled resume
- `no QQ push`
- `no settlement write`
- preflight `fail-closed`
- watchdog-only reporting
- 不得自动写 `PRODUCTION_VERIFIED`

## 5. Rollback Gate

- disable cron immediately
- keep preflight fail-closed
- no AI kill/retry
- report watchdog only
- preserve logs

## 6. 隔离项声明（非本轮审批包内容）

- `phase-d8 workspace isolation: excel only`
- `post-phase-c remainder: excel only`
- `phase-d87 workspace isolation: net_utils only`

以上 stash 仅隔离存在，不恢复、不处理、不提交。

## 7. 审批结论

- 当前仅可提交给 BOSS 审批。
- 下一门禁：`D.8.8`（需 BOSS 单独指令）。

## 8. D.8.8 执行批准后口径

- D.8.8 仅允许单窗口 controlled resume execution。
- 不允许全量恢复，不允许 QQ 推送，不允许写 verified。
- 仍保持：
  - `limited_resume_approved=false`（审批包自身不改写）
  - `resume_execution_allowed=false`（审批包自身不改写）
  - `cron_enable_allowed=false`
  - `qq_push_allowed=false`
  - `production_verified=false`

## 9. D.8.9 Scope Correction

- D.8.8 实际执行为 `controlled preflight observe`。
- 不是 `live window worker execution`。
- 不是 `production resume execution`。
- 审批包结论不变：仍需 BOSS 单独指令才能进入下一门禁（D.8.10）。
