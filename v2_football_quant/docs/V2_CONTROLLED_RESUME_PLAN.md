# V2 Controlled Resume Plan (Phase D.8.1)

> 本文档定义 **受控恢复计划**，不执行恢复。

## 1. 当前结论

- `current_level=CODE_READY`
- `PIPELINE_READY=false`
- `PRODUCTION_VERIFIED=false`
- D.8 readiness 已完成（`READY_FOR_BOSS_REVIEW/WARN`）
- 本轮仅计划，不执行恢复
- `resume_execution_allowed=false`
- `cron_change_allowed=false`
- `qq_push_allowed=false`
- `boss_approval_required=true`

## 2. 受控恢复分阶段（后续独立审批）

1. D.8.2 controlled cron dry-run validation  
2. D.8.3 controlled no-push production dry-run  
3. D.8.4 QQ route dry-run validation  
4. D.8.5 single-window live observe  
5. D.8.6 settlement preflight live guard observe  
6. D.8.7 BOSS approval for limited production resume

## 3. 回滚计划

- 立即禁用 cron
- 保留 preflight fail-closed
- 不允许 AI 自由 kill/retry
- 仅报告 watchdog 状态
- 保留日志与 marker，不删除证据

## 4. 硬前置门禁

- settlement preflight gate 必须保持启用
- wrapper block test 必须保持 PASS
- verified `hash/mtime/size` 不变性证据必须持续存在
- known historical fail 必须保留归档

## 5. 禁止事项（D.8.1）

- 不恢复生产
- 不启用 cron
- 不推 QQ
- 不写 verified
- 不写 `PRODUCTION_VERIFIED`
- 不进入 Phase E

## 6. 说明

- D.8.1 是 Controlled Resume Plan，不是 Controlled Resume Execution。
- 如需执行恢复，必须由 BOSS 另发 D.8.2+ 指令链。

## 7. D.8.2-D.8.6 Validation Pack（只读）

- D.8.2：cron dry-run validation（只读盘点，不改 cron）。
- D.8.3：no-push production dry-run（只做路径与门禁校验，不执行任务）。
- D.8.4：QQ route dry-run validation（只读检查，不发送消息）。
- D.8.5：single-window live observe plan（仅计划，不执行 live）。
- D.8.6：settlement preflight live guard observe plan（仅计划，不执行 live）。

固定结论：
- `resume_execution_allowed=false`
- `cron_change_allowed=false`
- `qq_push_allowed=false`
- `production_verified=false`
- 下一门禁：`D.8.7_BOSS_APPROVAL_ONLY`
