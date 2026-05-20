# Intel Ops Refresh 合约

> 生效日期：2026-05-21

---

## 1. 功能定义

Intel Ops Refresh 是情报操作台的刷新机制，用于刷新情报台展示数据。

## 2. 关键约束

| 项目 | 值 |
|:---|:---:|
| 可多次执行 | ✅ 是 |
| 是否触发 V4 scan | ❌ **否** |
| 读取方式 | 只读 |
| 是否写 state | ❌ 否 |
| 是否写 verified | ❌ 否 |
| 是否推 QQ | ❌ 否 |
| 是否启用 cron | ❌ 否 |

## 3. 数据源规则

- 只读取当天最新 V4 scan 文件（`v4_openclaw_brief_YYYYMMDD.txt`）；
- 若当天无 V4 scan 文件，显示 `V4_TODAY_SOURCE_MISSING`；
- **禁止 fallback 到旧快照**；
- 禁止调用 V4 scan 脚本；
- 禁止修改 V4 A/B/C/SKIP 评级。

## 4. 刷新频率

- 无硬性限制，可按需多次刷新；
- 每次刷新仅读取已存在的文件，不产生新的采集。

## 5. 合规标记

```
CAN_REFRESH_MULTIPLE_TIMES=true
TRIGGERS_V4_SCAN=false
READONLY=true
NO_STATE_WRITE=true
NO_VERIFIED_WRITE=true
NO_QQ_PUSH=true
NO_CRON=true
```
