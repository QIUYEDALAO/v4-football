# V2 Shadow Integration Boundary

> Phase D.1 — Inventory & Boundary Definition
> 本轮只盘点，不接入，不改生产。

---

## 1. V2 正式链路概述

V2 半场平赔率带策略生产链路：

```
DAILY_POOL (12:35)
  → 生成候选池 pool，只写 candidate_stage
  → 不锁定，不推QQ

window_checker (每小时 05/35)
  → 读取 pool，按窗口逻辑生成 BET_LOCKED
  → 唯一写 lock_owner=window_checker
  → 唯一写 official_bet_locked=true
  → 唯一触发正式QQ推荐

settlement (15:37)
  → 只结算: official_bet_locked=true + lock_owner=window_checker
  → missed candidates 不结算

daily status push
  → 每日状态回执（含无单回执）
```

## 2. 各组件权责

### 2.1 DAILY_POOL (daily_runner.py)

**允许：**
- 生成 pool
- 写 `action_code`: `WATCH_EARLY`, `CANDIDATE`, `FINAL_RECORD`, `ODDS_OUT`, `SKIP_LOW`, `WATCH_HIGH`
- 写 `candidate_stage`
- 写 `lock_owner=DAILY_POOL_PENDING`
- 写 `official_bet_locked=false`
- 写 `qq_required=false`
- 写 `settlement_required=false`

**禁止：**
- 写 `action_code=BET_LOCKED`
- 写 `locked_stage`
- 写 `lock_owner=window_checker`
- 写 `official_bet_locked=true`
- 触发 QQ 推送
- 触发结算

### 2.2 Window Checker (v2_window_checker_with_watchdog.py)

**允许：**
- 读取 pool
- 按 T-90m / T-45m 窗口逻辑生成 BET_LOCKED
- 写 `new_locks`
- 写 `lock_owner=window_checker`
- 写 `official_bet_locked=true`
- 作为 QQ 推荐唯一来源
- 写 notify marker

**禁止：**
- 从非 pool 源生成 BET_LOCKED
- 绕过窗口时间判 BET_LOCKED

### 2.3 Settlement (v2_settle_with_watchdog.py)

**允许：**
- 只结算: `official_bet_locked=true` + `lock_owner=window_checker`
- 写 verified 文件

**禁止：**
- 结算 `candidate_stage` 记录
- 结算 `missed candidates`
- 结算非 `window_checker` 锁定的记录
- 结算 DAILY_POOL 直接标 `BET_LOCKED` 的记录

### 2.4 Missed Candidates (audit)

**允许：**
- 审计标记
- 写入 audit 文件

**禁止：**
- 补推 QQ
- 补记 BET_LOCKED
- 补结算
- missed candidates 不补推、不补记、不结算

### 2.5 Daily Status Push

**允许：**
- 每日状态回执
- 明确 BET_LOCKED=0 时也要推回执
- 不静默

**禁止：**
- 把 missed candidates 当作正式 BET_LOCKED 推送

---

## 3. BET_LOCKED 正式口径

一条记录被认定为正式推荐，必须同时满足：

1. `action_code == "BET_LOCKED"`
2. `official_bet_locked == true`
3. `lock_owner == "window_checker"`
4. 由 `v2_window_checker_with_watchdog.py` 在 T-90m 或 T-45m 窗口生成
5. 有对应 notify marker

不满足以上任一条件 → 不是正式推荐。

---

## 4. Phase D Shadow 边界

### D.1 当前（本轮）
- ✅ 只盘点 inventory
- ✅ 只定义 boundary
- ✅ 只新增只读 checker

### D.2 后续
- 只读 V2 shadow read baseline
- 对照 DAILY_POOL input 与 window_checker output
- 记录 shadow 每日对照结果
- 不替代正式数据源

### Shadow 硬边界
- ❌ shadow 只能对照，不能影响正式链路
- ❌ shadow 不能替代正式链路
- ❌ cache 不能替代正式数据源
- ❌ shadow 不能推 QQ
- ❌ shadow 不能结算
- ❌ shadow 不能写 production_verified
- ❌ shadow 不能接 cron

---

## 5. 禁止事项

- 不改 V2 策略
- 不改 BET_LOCKED 规则
- 不改 window_checker 正式行为
- 不改 settlement 正式行为
- 不让 cache 进入正式链路
- 不让 shadow 影响生产
- 不接 cron
- 不推 QQ
- 不写 PRODUCTION_VERIFIED
- production_verified=false

---

## 6. Phase D.2：V2 Shadow Read Baseline

D.2 是 V2 Shadow Read Baseline，只读聚合 V2 正式链路状态。

### 覆盖范围

| 组件 | 只读源 | 输出字段 |
|:-----|:-------|:--------|
| DAILY_POOL | summary / push marker | candidate_count, writes_bet_locked |
| window_checker | notify marker | new_locks_count, bet_locked_count |
| daily_status | status push marker | official_bet_locked, missed_candidates |
| missed_candidates | audit file | count, leaked checks |
| settlement | settle push / task status | targets, only_window_checker |

### 硬边界

- baseline 只读聚合，不替代正式源
- baseline 不推 QQ
- baseline 不结算
- baseline 不写 BET_LOCKED
- baseline 不接 cron
- baseline 不调用 API
- baseline 不写入正式 marker

### 新文件

- `engine/v2_shadow_baseline.py` — 核心只读聚合模块
- `tools/v2_shadow_baseline_dryrun.py` — dry-run 入口
- `tools/check_v2_shadow_baseline.py` — baseline checker

### D.2.1 Evidence Hardening

D.2.1 是 baseline evidence hardening，补强所有组件的证据读取。

**关键变更：**
- settlement `only_window_checker_locks` 不再按设计假定 true
- 必须从 verified 文件 / task status 中解析
- 引入 `evidence_sources` / `evidence_quality` / `unknown_fields` / `assumptions`
- lock_owner 字段缺失 → evidence_quality=partial → max WARN
- no targets → evidence_quality=partial → max WARN（no_targets_to_verify）
- 有 targets 但无 lock_owner → 标注 `lock_owner_unavailable`
- hardcoded assumption → checker 判 FAIL

**evidence_quality 语义：**

| evidence_quality | 允许最高状态 |
|:----------------|:----------|
| strong | PASS |
| partial | WARN |
| missing | WARN (最低) |

**unknown_fields 规则：**
- 有 unknown_fields → 至少 WARN
- 不能假 PASS

---

### D.3 DAILY_POOL Input Shadow Compare

D.3 是 DAILY_POOL Input Shadow Compare，只读对照 DAILY_POOL 输入与 window_checker 输出。

**功能：**
- 只读追踪 candidate_stage → window_checker output 对应关系
- 统计 matched / locked / missed / unmatched
- 不生成 BET_LOCKED，不推 QQ，不结算
- lock_owner 缺字段 → WARN，不伪造 PASS

**新文件：**
- `engine/v2_shadow_compare.py` — compare 核心模块
- `tools/v2_shadow_compare_dryrun.py` — dry-run 入口
- `tools/check_v2_shadow_compare.py` — compare checker

---

### D.3.1 Compare Guard Hardening

D.3.1 修复 compare guard 中 `lock_owner_gap_preserved` 恒 true 表达式。

**修复：** 通过 `_compute_lg_preserved/is_warning/evidence_quality()` 三函数计算真实 guard 值。
- `gap_preserved=true` = 缺口被保留上报，不代表证据完整
- `evidence_quality=partial/missing` → max WARN
- 非 window_checker lock_owner → FAIL

---

### D.4 window_checker Shadow Compare

D.4 是 window_checker Shadow Compare，只读对照 window_checker 输出与 daily status / missed audit / settlement guard 一致性。

- 不重跑 window_checker
- 不模拟策略
- 不生成 BET_LOCKED
- lock_owner 缺字段 → WARN

---

### D.4.1 Guard Semantics Fix

D.4.1 修复 lock_owner gap 语义冲突。

**修复前：** `gap_preserved = evidence_quality != "strong"`（no-locks 场景下 evidence=strong 导致 gap=false）

**修复后：** 新增 `not_applicable` 状态区分无锁场景。
- new_locks=0 → not_applicable → gap_preserved=true, gap_is_warning=false
- 有锁缺lock_owner → partial → WARN

---

## D.7.3 Settlement Preflight Coverage Closure

### 本轮定位并收口

- D.7.2 的 wrapper test 缺口已补齐：
  - `exit_code` 必须严格等于 `2`
  - verified `hash/mtime/size/exists` 变化即 FAIL
  - 7 个主 blocker reason codes 强校验
  - watchdog `BLOCKED_PREFLIGHT` 强校验
  - wrapper marker 进入 preflight checker 统一校验

### 当前语义（必须保留）

- `phase_d_engineering_complete=true`
- `phase_d_business_pass=false`
- `known_historical_fail=true`
- `settlement_preflight_gate_installed=true`
- `wrapper_block_test_passed=true`
- `PIPELINE_READY=false`
- `PRODUCTION_VERIFIED=false`

### 同日回放结论

- 20260517 已可同日回放验证 BLOCK；
- 不需要等待明天；
- 该结论是工程链路闭合，不是生产恢复授权。

---

### D.5 Settlement Shadow Guard Reinforcement

D.5 是 Settlement Shadow Guard，只读核对 settlement 与 window_checker/daily_status/missed_audit 的边界一致性。
- 不重跑 settlement
- 不写 verified
- missed candidates 进入 settlement → FAIL
- lock_owner 缺字段 → WARN

---

### D.5.1 Settlement Guard Conflict Hardening

D.5.1 修正判定逻辑，固化历史冲突。

**修正前：** targets=2 vs official=0 仍写 match=true ❌
**修正后：** 数量对比直接判定 false + FAIL

**20260517 冲突归类：**
- MISSED_IN_SETTLEMENT：2 missed candidates 出现在 verified targets
- SETTLEMENT_TARGETS_OFFICIAL_LOCKS_CONFLICT：2 targets vs 0 official
- SETTLEMENT_TARGETS_WINDOW_LOCKS_CONFLICT：2 targets vs 0 window locks
- lock_owner 缺字段 → evidence partial

**该冲突不得修历史数据，不得补推/补记/重跑。**

---

### D.6 Completion Audit & Risk Archive

D.6 是 Phase D 总验收。

**结论：** 工程链路完成，`business_pass=false`，20260517 历史 settlement 污染已归档。
- phase_d_engineering_complete=true
- phase_d_business_pass=false
- known_historical_fail=true
- 当前 CODE_READY
- 下一阶段需 BOSS 单独指令

---

## 7. 下一阶段计划

| Phase | 内容 | 状态 |
|:------|:-----|:----:|
| D.1 | Inventory + Boundary | ✅ 本轮 |
| D.2 | V2 Shadow Read Baseline | 待指令 |
| D.3 | DAILY_POOL input shadow compare | 待指令 |
| D.4 | window_checker shadow compare | 待指令 |
| D.5 | settlement guard reinforcement | 待指令 |

---

*Generated: 2026-05-18 Phase D.1*
