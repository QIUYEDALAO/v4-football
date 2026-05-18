# Phase D Completion Report — V2 Shadow Integration

> Date: 2026-05-18 | Level: CODE_READY | Engineering: Complete | Business: FAIL (historical)

---

## 1. Phase D 总览

| Step | Commit | 内容 | 状态 |
|:----:|:------|:-----|:----:|
| D.1 | `394e7fa` | V2 shadow boundary inventory + checker | ✅ |
| D.2 | `827ad91` | V2 shadow baseline read model | ✅ |
| D.2.1 | `84ef906` | Baseline evidence hardening | ✅ |
| D.3 | `a071799` | DAILY_POOL input shadow compare | ✅ |
| D.3.1 | `090092f` | Compare guard hardening (fix tautology) | ✅ |
| D.4 | `cc48e2f` | window_checker shadow compare | ✅ |
| D.4.1 | `ac2f7c0` | Window guard semantics (not_applicable state) | ✅ |
| D.5 | `e7f50e9` | Settlement shadow guard (detected FAIL) | ⚠️ |
| D.5.1 | `83deae7` | Settlement conflict hardening (classified FAIL) | ⚠️ |
| D.7 | `2f54627` | Settlement preflight gate (entry block) | ✅ |
| D.7.1 | `df5a752` | Preflight entry fix (key + lock order) | ✅ |
| D.7.2 | `afb0e88` | Preflight test coverage v1 | ✅ |
| D.7.3 | `1eea1c5` | Preflight coverage closure (strict wrapper/checker/docs) | ✅ |
| D.8 | `c7a7213` | Production resume readiness gate (read-only) | ✅ |
| D.8.1 | `5ba5113` | Controlled resume plan (plan-only, no execution) | ✅ |
| D.8.2 | `TBD` | Controlled cron dry-run validation (read-only) | ✅ |
| D.8.3 | `TBD` | Controlled no-push production dry-run (read-only) | ✅ |
| D.8.4 | `TBD` | QQ route dry-run validation (read-only) | ✅ |
| D.8.5 | `TBD` | Single-window live observe plan (plan-only) | ✅ |
| D.8.6 | `TBD` | Settlement preflight live guard observe plan (plan-only) | ✅ |
| D.8.8 | `a3b47c5` | Controlled preflight observe (single-window, not live worker) | ✅ |
| D.8.9 | `8c94cca` | Controlled resume post-run review & scope correction | ✅ |
| D.8.10 | `TBD` | Window worker sandbox observe (no supervisor/no formal write) | ✅ |

**新增 20+ 文件，0 次策略改动，0 次 API 调用，0 次 QQ 推送。**

---

## 2. 当前结论

| 断言 | 值 |
|:-----|:---|
| engineering_complete | true |
| business_pass | **false** |
| known_historical_fail | **true** |
| current_level | CODE_READY |
| PIPELINE_READY | false |
| PRODUCTION_VERIFIED | false |
| V2 formal link uses cache | false |
| shadow affects formal link | false |

---

## 3. 20260517 风险归档

### 历史 settlement 污染

| 证据 | 数据 |
|:-----|:----:|
| DAILY_POOL summary | 缺失 |
| window_checker new_locks | 0 |
| official_bet_locked | 0 |
| missed_candidates | 2 |
| settlement verified targets | **2** |
| missed candidates in targets | **是** (1506982, 1506983) |
| verified has lock_owner | 否 |
| verified has official_bet_locked | 否 |

**根因：** DAILY_POOL 延迟建池 → window_checker skipped → 无正式 BET_LOCKED，但 settlement 仍结算了 pool 中候选。

**处置：**
- ❌ 不得修改历史 verified
- ❌ 不得补推 QQ
- ❌ 不得补记 BET_LOCKED
- ❌ 不得重跑 settlement
- ✅ 历史冲突已固化为 D.5.1 FAIL
- ✅ D.7.3 preflight 已确保冲突日期同日 BLOCK（wrapper exit_code=2）

---

## 4. D.7.3 收口结论（同日可验证）

- self-test：6/6 PASS（含 count mismatch blocker）。
- wrapper-level block test：PASS。
- `exit_code=2`：强制检查通过。
- verified 文件：`hash/mtime/size/exists` 均未变化。
- 7 个主 blocker reason codes：全部命中。
- watchdog：`BLOCKED_PREFLIGHT` 命中。
- verify_date：未调用。

这意味着 20260517 在同日即可通过工程回放判定为 BLOCK，**不需要等待明天**。

---

## 5. Phase D 禁止事项

- 不接 cache 到 V2 正式链路
- 不让 shadow 影响正式链路
- 不推 QQ
- 不接 cron
- 不写 PRODUCTION_VERIFIED
- shadow 不得进入 settlement / window_checker / daily status

---

## 6. 下一阶段

Phase D 工程链路完成（engineering_complete=true），但 business_pass=false。后续选项：

1. **Phase D.8.1**：Controlled Resume Plan（需 BOSS 单独审批）
2. **Phase E**：V4 扫描五窗口标准化（需 BOSS 单独指令）
3. **恢复生产运行**：需 BOSS 单独指令（不得自动执行）

必须由 BOSS 单独确认。不得自动进入。

---

## 7. D.8 Readiness Gate 结论

- D.8 只做 readiness gate，不恢复生产。
- D.8 不启用 cron，不推 QQ，不写 `PRODUCTION_VERIFIED`。
- D.7.3 已证明 20260517 同日可 BLOCK，不需要等明天。
- `known_historical_fail=true` 持续保留。
- `resume_allowed_now=false`，`boss_approval_required=true`。

---

## 8. D.8.1 Controlled Resume Plan 结论

- D.8.1 只做计划与门禁，不执行恢复。
- 固定值：
  - `resume_execution_allowed=false`
  - `cron_change_allowed=false`
  - `qq_push_allowed=false`
  - `production_verified=false`
- 生产恢复必须走 D.8.2~D.8.7 分阶段审批流程。
- 本阶段仍不进入 Phase E。

---

## 9. D.8.2-D.8.6 Validation Pack 结论

- D.8.2-D.8.6 已完成受控验证总包（dry-run/plan/validation）。
- 本轮未恢复生产，未启用 cron，未推 QQ，未写 verified。
- 固定输出：
  - `ready_for_boss_review=true`
  - `resume_execution_allowed=false`
  - `cron_enable_allowed=false`
  - `qq_push_allowed=false`
  - `production_verified=false`
- 下一步仅允许：`D.8.7_BOSS_APPROVAL_ONLY`。

---

## 10. D.8.7 Limited Resume Approval Packet

- D.8.7 只做审批包，不执行恢复。
- 固定口径：
  - `current_level=CODE_READY`
  - `PIPELINE_READY=false`
  - `PRODUCTION_VERIFIED=false`
  - `limited_resume_approved=false`
  - `resume_execution_allowed=false`
  - `cron_enable_allowed=false`
  - `qq_push_allowed=false`
- WARN 风险分类必须保留：
  - manual QQ push path exists
  - safe_outbound_sender guard signature missing
  - single-window live observe still plan-only
  - validation pack status = WARN
- D.8.8 已执行受控 preflight observe，但不等于真实 worker 执行。
- rollback gate 要求：
  - disable cron immediately
  - keep preflight fail-closed
  - no AI kill/retry
  - report watchdog only
  - preserve logs

隔离项说明（非审批包执行范围）：
- `phase-d8 workspace isolation: excel only`
- `post-phase-c remainder: excel only`
- `phase-d87 workspace isolation: net_utils only`

---

## 11. D.8.8 Controlled Single-window Resume

- D.8.8 是单窗口受控观察，不是全量恢复。
- D.8.8 实际执行范围：`preflight_observe_only`。
- `execution_performed=true` 仅表示 preflight observe 已运行。
- `live_window_worker_executed=false`。
- `production_resume_executed=false`。
- 固定禁止：
  - 不推 QQ
  - 不写 verified
  - 不写 `PRODUCTION_VERIFIED`
  - 不启用全局 cron
- 若无法安全执行正式 worker，可降级为 plan-only WARN（必须可审计）。
- 失败只报告 watchdog 状态；不允许 AI 自由 kill/retry。
- D.8.9 已确认 scope correction：D.8.8 不等于 live worker / production resume。

## 12. D.8.10 Window Worker Sandbox Observe

- D.8.10 仅执行 `sandbox_worker_logic_only`。
- 不执行 `v2_window_checker_with_watchdog.py` supervisor。
- 不执行正式 live worker 子进程写回正式 state。
- 正式 `data/state/selected_fixtures_YYYYMMDD.json` 必须保持不变。
- `formal_state_written=false`、`formal_state_unchanged=true`。
- `qq_sent=false`、`verified_written=false`、`cron_modified=false`、`api_called=false`。
- D.8.10 不是生产恢复，不等于 `PIPELINE_READY` / `PRODUCTION_VERIFIED`。
- 如需真实 live worker observe，必须单独进入 D.8.11 或 D.8.12 指令；Phase E 仍不得自动进入。
