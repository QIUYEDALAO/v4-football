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

---

## 4. Phase D 禁止事项

- 不接 cache 到 V2 正式链路
- 不让 shadow 影响正式链路
- 不推 QQ
- 不接 cron
- 不写 PRODUCTION_VERIFIED
- shadow 不得进入 settlement / window_checker / daily status

---

## 5. 下一阶段

Phase D 工程链路完成。后续选项：

1. **Phase E**：V4 扫描五窗口标准化
2. **恢复生产运行**：提前结束架构建设，等待明天自然验证
3. **Phase D.7**：V2 production marker schema hardening

必须由 BOSS 单独确认。不得自动进入。
