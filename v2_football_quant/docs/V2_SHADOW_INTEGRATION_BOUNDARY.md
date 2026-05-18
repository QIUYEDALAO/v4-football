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

## 6. 下一阶段计划

| Phase | 内容 | 状态 |
|:------|:-----|:----:|
| D.1 | Inventory + Boundary | ✅ 本轮 |
| D.2 | V2 Shadow Read Baseline | 待指令 |
| D.3 | DAILY_POOL input shadow compare | 待指令 |
| D.4 | window_checker shadow compare | 待指令 |
| D.5 | settlement guard reinforcement | 待指令 |

---

*Generated: 2026-05-18 Phase D.1*
