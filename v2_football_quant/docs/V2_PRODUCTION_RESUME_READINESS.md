# V2 Production Resume Readiness (Phase D.8)

> 本文档只定义 **readiness gate**，不恢复生产、不启用 cron、不推 QQ。

## 1. D.8 定位

- D.8 是恢复生产前的只读门禁。
- D.8 不是恢复生产执行。
- D.8 不会触发 DAILY_POOL / window_checker / settlement。

## 2. 当前固定口径

- `current_level=CODE_READY`
- `PIPELINE_READY=false`
- `PRODUCTION_VERIFIED=false`
- `resume_allowed_now=false`
- `boss_approval_required=true`

## 3. D.7.3 前置证明（同日可验证）

- 20260517 preflight 为 BLOCK。
- wrapper block test 通过：
  - `exit_code=2`
  - verified `hash/mtime/size` 不变
  - 7 个主 blocker reason codes 全命中
  - watchdog `BLOCKED_PREFLIGHT`
  - verify_date 未调用
- 不需要等待明天来证明 preflight 拦截。

## 4. 历史污染保留

- `known_historical_fail=true` 必须持续保留。
- D.5.1 的历史冲突 FAIL 继续归档，不得清除或弱化。
- readiness 通过不等于历史冲突已修复。

## 5. 禁止事项（D.8）

- 不恢复生产运行
- 不启用 cron
- 不推 QQ
- 不写 `PRODUCTION_VERIFIED`
- 不替换正式 V2 数据源
- 不让 cache/shadow 进入正式链路

## 6. 下一步选项（需 BOSS 单独审批）

1. D.8.1 Controlled Resume Plan  
2. Phase E V4 Scan Standardization  
3. Pause architecture and observe manually

## 7. D.8.1 计划门禁固定值

- `resume_execution_allowed=false`
- `cron_change_allowed=false`
- `qq_push_allowed=false`
- `boss_approval_required=true`

说明：D.8.1 只输出受控恢复计划与回滚方案，不执行恢复动作。

## 8. D.8.2-D.8.6 Validation Pack 口径

- D.8.2-D.8.6 仅做 dry-run/plan/validation。
- 不恢复生产，不启用 cron，不推 QQ，不写 verified。
- 不写 `PRODUCTION_VERIFIED`，不声明 `PIPELINE_READY`。
- 下一步仅允许 `D.8.7_BOSS_APPROVAL_ONLY`。
