# V4 每日一次只读扫描策略

> 生效日期：2026-05-21
> 上次修订：2026-05-21

---

## 1. 扫描频率

| 项目 | 值 |
|:---|:---:|
| 扫描频率 | **每日一次 (daily_once)** |
| 推荐时间窗口 | 12:00–14:00 CST |
| 是否允许多窗口 | **否** |
| 是否根据赔率多次扫描 | **否** |

## 2. 策略依据

V4 是上半场进球情报系统，核心依据是 **历史交锋数据**，而非动态赔率。

- 赔率变化不影响已扫描的比赛推荐等级；
- 不需要多窗口重复扫描；
- 多窗口扫描不会提高命中率，只会增加系统负载和噪声。

## 3. 扫描执行规则

- 每日 **12:00–14:00 CST** 执行一次只读扫描；
- 扫描范围：当日所有符合联赛白名单的比赛；
- 输出：仅产生 `v4_openclaw_brief_YYYYMMDD.txt` 正文版和 QQ 版；
- 不写 state；
- 不写 verified；
- 不推 QQ；
- 不接 cron；
- 不进入 Phase E。

## 4. 与情报台的关系

| 组件 | 可多次执行 | 是否触发 V4 scan |
|:---|:---:|:---:|
| 情报台/Intel Web Dashboard | ✅ 可多次刷新 | ❌ 不触发 V4 scan |
| Intel Ops Refresh | ✅ 可多次刷新 | ❌ 不触发 V4 scan |
| **V4 扫描** | ❌ 每日仅一次 | — |

## 5. Source Resolver 规则

- V4 source resolver 每天只读取当天最新 V4 scan 文件；
- 若当天无 V4 scan 文件，显示 `V4_TODAY_SOURCE_MISSING`；
- **不允许 fallback 到旧快照**。

## 6. 禁止项

- ❌ 不得每日多次扫描；
- ❌ 不得根据盘口变化触发二次扫描；
- ❌ 不得在 12:00–14:00 窗口外执行 V4 scan；
- ❌ 不得通过情报台 refresh 触发 V4 scan；
- ❌ 不得自动推 QQ；
- ❌ 不得写 state/verified；
- ❌ 不得启用 cron；
- ❌ 不得进入 Phase E。

## 7. 合规标记

```
DAILY_ONCE=true
NO_MULTI_INTRADAY_SCAN=true
INTEL_REFRESH_DOES_NOT_TRIGGER_V4_SCAN=true
SOURCE_RESOLVER_READONLY=true
QQ_PUSH_ALLOWED=false
STATE_WRITE_ALLOWED=false
VERIFIED_WRITE_ALLOWED=false
CRON_ENABLED=false
PHASE_E=false
```
