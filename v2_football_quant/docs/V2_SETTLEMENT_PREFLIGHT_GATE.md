# V2 Settlement Production Preflight Gate

> Phase D.7 / D.7.1 / D.7.2 / D.7.3 收口说明（fail-closed）。

## Gate Rule（正式口径）

Settlement 必须先通过 preflight；任一条件不满足即 BLOCK：

1. `official_bet_locked > 0`
2. `window_checker new_locks_count > 0`
3. settlement target 具备 `lock_owner=window_checker`
4. missed candidates 不得进入 settlement targets
5. settlement target 数量与 official/window 锁定数量一致
6. status/audit marker 可读

缺任一项：`settlement_allowed=false` + `fail_closed=true`。

## D.7.3 测试覆盖闭合

本轮完成并固定以下检查：

1. Self-test 至少 6 case（含 count mismatch blocker）。
2. Wrapper-level block test（真实 wrapper 入口）。
3. Wrapper 强制 `exit_code=2`（`0/1/其他` 均判 FAIL）。
4. `verified_YYYYMMDD.json` 的 `hash/mtime/size/exists` 全量不变检查。
5. 7 个主 blocker reason codes 强校验：
   - `OFFICIAL_BET_LOCKED_ZERO`
   - `WINDOW_CHECKER_NEW_LOCKS_ZERO`
   - `LOCK_OWNER_MISSING`
   - `MISSED_CANDIDATES_PRESENT`
   - `SETTLEMENT_WITHOUT_OFFICIAL_LOCKS`
   - `SETTLEMENT_WITHOUT_WINDOW_LOCKS`
   - `HISTORICAL_SETTLEMENT_CONTAMINATION`
6. watchdog 强校验 `status=BLOCKED_PREFLIGHT`。
7. verify_date 未调用校验（结合 `exit_code=2` + verified 不变 + BLOCK 语义）。

## 20260517 同日验证结论

- 20260517 可同日回放验证为 BLOCK；
- 不需要等明天自然验证；
- 历史污染冲突被稳定拦截。

## 当前等级与边界

- `current_level=CODE_READY`
- `PIPELINE_READY=false`
- `PRODUCTION_VERIFIED=false`
- 该 gate 是工程链路防误写保护，不等于业务通过。
- D.8 readiness gate 仍要求：
  - `resume_allowed_now=false`
  - `boss_approval_required=true`
  - 不自动恢复生产
- D.8.1 Controlled Resume Plan 仍要求：
  - `resume_execution_allowed=false`
  - `cron_change_allowed=false`
  - `qq_push_allowed=false`
  - 仅可提交计划，不可执行恢复

## 禁止事项

- 不得修改历史 verified
- 不得补推
- 不得补记 BET_LOCKED
- 不得接 cron
- 不得推 QQ
- 恢复生产运行必须 BOSS 单独指令
