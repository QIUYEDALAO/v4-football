# Intel Web Dashboard 合约

> 生效日期：2026-05-21

---

## 1. 功能定义

Intel Web Dashboard 是情报台的前端展示页面，用于显示 V4 上半场情报系统当日输出。

## 2. 关键约束

| 项目 | 值 |
|:---|:---:|
| 可多次刷新 | ✅ 是（前端页面刷新） |
| 是否触发 V4 scan | ❌ **否** |
| 读取方式 | 只读 |
| 数据源 | 当天最新 V4 scan 文件 |
| 是否写 state | ❌ 否 |
| 是否写 verified | ❌ 否 |
| 是否推 QQ | ❌ 否 |
| 是否启用 cron | ❌ 否 |

## 3. 数据读取规则

- 从 `v4_openclaw_brief_YYYYMMDD.txt` 读取当天 V4 数据；
- 从 `v4_openclaw_brief_qq_YYYYMMDD.txt` 读取 QQ 版；
- 若当天无 V4 scan 文件，显示 `V4_TODAY_SOURCE_MISSING`；
- **禁止 fallback 到旧快照**；
- 禁止调用任何 V4 scan/capture 脚本；
- 禁止修改 V4 A/B/C/SKIP 评级；
- 禁止将 C/SKIP 展示为推荐。

## 4. 展示规则

- A/B 级展示为主推荐；
- C 级展示为观察；
- SKIP 默认不展示单场，只统计数量；
- QQ 版仅为预览，不自动推送。

## 5. 合规标记

```
CAN_REFRESH_MULTIPLE_TIMES=true
TRIGGERS_V4_SCAN=false
READONLY=true
NO_STATE_WRITE=true
NO_VERIFIED_WRITE=true
NO_QQ_PUSH=true
NO_CRON=true
C_OBSERVATION_ONLY=true
SKIP_NOT_RECOMMENDATION=true
```
