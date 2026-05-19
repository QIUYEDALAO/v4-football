# V4 Refactor Roadmap

## Global Default Gates

- `qq_push_allowed=false`
- `production_allowed=false`
- `production_verified=false`

## V4-B Output schema & renderer guard

- 目标：统一 V4 输出 schema 与 renderer 约束。
- 禁止项：不得绕过 guard，不得新增非 A/B/C/SKIP 输出。
- 验收标准：schema + renderer checker PASS/WARN，口径锁定。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-C QQ brief guard

- 目标：建立 QQ 简报内容 guard 与 route/sent 前置检查。
- 禁止项：不得直推 QQ，不得跳过 route/sent marker。
- 验收标准：QQ guard checker PASS/WARN，拒绝无 guard 发送。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-D watchdog / state / lock

- 目标：梳理 watchdog、状态机、并发锁和超时边界。
- 禁止项：不得 AI 自由 kill/retry，不得越过 lock。
- 验收标准：watchdog + lock 契约检查通过。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-E attribution system

- 目标：建立赛后归因链路与异常归因标准。
- 禁止项：不得无归因改规则。
- 验收标准：attribution schema 与 checker 通过。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-F rolling validation

- 目标：建立滚动验证指标和窗口化追踪。
- 禁止项：不得把单日结果当长期稳定性证明。
- 验收标准：rolling validation 结构化产物可审计。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-G daily / weekly / monthly reports

- 目标：日报/周报/月报统一模板与一致性校验。
- 禁止项：不得混入口径外字段，不得引用 V33（仅可在 deprecated/forbidden 说明中出现）。
- 验收标准：report schema + guard checker 通过。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-H production readiness gate

- 目标：构建 V4 生产就绪门禁。
- 禁止项：不得直接放开生产执行权限。
- 验收标准：readiness gate 仅输出评审结论。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-I controlled observe

- 目标：在严格边界下进行受控观察计划。
- 禁止项：不得自动进入真实生产路径。
- 验收标准：observe plan 审批化、可回滚、可阻断。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false

## V4-J PRODUCTION_VERIFIED gate

- 目标：建立最终 PRODUCTION_VERIFIED 审批门。
- 禁止项：不得自动写 PRODUCTION_VERIFIED。
- 验收标准：仅在全量证据满足且 BOSS 批准后可进入候选态。
- qq_push_allowed=false
- production_allowed=false
- production_verified=false
