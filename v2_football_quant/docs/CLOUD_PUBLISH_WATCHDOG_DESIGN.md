# Cloud Publish Watchdog Design

## 1. 定位

Watchdog 是本地守护检查逻辑，不依赖外部调度器。
只在 dashboard hash 变化时才触发 publish。

## 2. 核心规则

### 2.1 检查周期

每 5 分钟检查一次 dashboard hash。

- 检查对象：`data/runtime/dashboard/intel_ops_console.html` 的 SHA256
- 对比对象：上一次成功 publish 的 manifest sha256
- hash 未变化 → 跳过，不执行任何操作
- hash 变化 → 触发 publish pipeline

### 2.2 Publish 失败处理

- publish 失败 → 写 WARN 到 `data/runtime/status/cloud_publish_watchdog.json`
- WARN 不影响本地生产
- 30 秒后重试，最多 3 次
- 3 次均失败 → 不再重试，等待下一周期

### 2.3 连续失败升级

- 连续 3 次 publish 失败 → 升级为 BLOCKER
- BLOCKER 写入 watchdog status
- BLOCKER 不自动解除，需要人工检查

### 2.4 Stale 检测

- 距离上次成功 publish 超过 10 分钟 → WARN "cloud mirror stale"
- 不自动重试，等待下一周期

### 2.5 禁止行为

- **不允许** kill watchdog 进程
- **不允许** 自动 retry 超过 3 次
- **不允许** 修改超时参数
- **不允许** 云端主动拉取
- **不允许** 双向同步

## 3. 状态文件

`data/runtime/status/cloud_publish_watchdog.json`

```json
{
  "watchdog": "cloud_publish",
  "last_check": "2026-05-20T23:55:00Z",
  "last_publish": "2026-05-20T23:50:00Z",
  "last_hash": "abc123...",
  "consecutive_failures": 0,
  "status": "OK",
  "detail": "no change since last publish"
}
```

状态值：
- `OK` — 最近一次检查正常，hash 未变或 publish 成功
- `WARN` — publish 失败但未达 BLOCKER 阈值
- `BLOCKED` — 连续 3 次失败
- `STALE` — 超过 10 分钟未成功 publish

## 4. 流程

```
LOOP (every 5 min):
  │
  ├─ 1. 读取当前 dashboard hash
  │
  ├─ 2. 对比上次 publish hash
  │     ├─ 相同 → 写 OK，sleep
  │     └─ 不同 → 进入 publish 流程
  │
  ├─ 3. Build bundle (secret scan)
  │     ├─ BLOCKED → 写 WARN，记录
  │     └─ CLEAN → 继续
  │
  ├─ 4. Publish (rsync + verify + promote)
  │     ├─ SUCCESS → 更新 last_publish，reset failures
  │     └─ FAIL → failures += 1
  │           ├─ failures < 3 → retry after 30s
  │           └─ failures >= 3 → 写 BLOCKED
  │
  └─ 5. Check stale
        └─ last_publish > 10min ago → 写 STALE
```

## 5. 集成方式

Watchdog 不要求独立的 systemd/cron 进程。
可以在现有的 periodic check 脚本中加入 watchdog 逻辑：

```python
# 伪代码
def watchdog_tick():
    current_hash = sha256(dashboard_html)
    last = read_watchdog_status()

    if current_hash == last.get("last_hash"):
        update_watchdog("OK", "no change")
        return

    ok = build_and_publish()
    if ok:
        update_watchdog("OK", "published", last_hash=current_hash, failures=0)
    else:
        failures = last.get("consecutive_failures", 0) + 1
        if failures >= 3:
            update_watchdog("BLOCKED", "3 consecutive failures", failures=failures)
        else:
            update_watchdog("WARN", f"publish failed ({failures}/3)", failures=failures)
```

## 6. 监控接口

Watchdog 只报告状态，不主动推送告警。
外部监控系统可读取 `cloud_publish_watchdog.json` 判断是否需要告警。
