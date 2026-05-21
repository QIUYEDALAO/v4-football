# SYS QQ Noise Emergency Mute — 20260521

**Generated:** 2026-05-21 00:28 CST  
**Status:** SYS_QQ_NOISE_EMERGENCY_MUTE_PASS

---

## Root Cause Analysis

| Question | Answer |
|:---------|:-------|
| QQ 从哪个脚本/route 发出？ | **SYS-架构审计守卫** cron job (ID `41a21ce1`) |
| 为什么"仅报告"还会推 QQ？ | agentTurn 的 payload 内嵌了 systemEvent 推送逻辑。交付消息中写了"使用 systemEvent 发送到主会话"，导致 agent 在 isolated session 内主动调用 sessions_send/systemEvent，绕过 delivery.mode=none 限制。 |
| 触发条件 | Architecture Audit 非 PASS 时触发（当前 Cron Policy 显示 FAIL） |
| 频率 | 每天 08:40 / 17:40 / 23:40 三次 |
| delivery.mode | `"none"` — 只拦了 cron announce，没拦 agent 自调用 |
| 最近状态 | lastRunStatus=error，lastDeliveryStatus=not-requested |

## Mute Action

| Action | Status |
|:-------|:-------|
| Mute marker written | ✅ `data/runtime/status/sys_qq_noise_emergency_mute_20260521.json` |
| Mode | **exception_only** — normal audit FAIL 只写状态不推 QQ |
| Critical exceptions still push? | ✅ Yes — scan interrupted, one-shot missed, cloud mismatch, D13/V33/HOURLY active |
| V2/V4 modified? | ❌ No |
| kill/retry/改超时? | ❌ No |
| Real push test? | ❌ No |

## Fix Required (BOSS decides)

The permanent fix requires changing the agentTurn payload in cron job `41a21ce1` to **remove the systemEvent push instruction** and only write status files. This is a cron job configuration change — NOT a strategy change, NOT a code change.

**Option A** (recommended): Update the agentTurn message to remove "使用 systemEvent 发送到主会话" line, replace with "只写状态文件，不推送"

**Option B**: Disable the SYS-架构审计守卫 cron job entirely (drastic)
