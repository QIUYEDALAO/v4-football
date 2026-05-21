# Cloud Publish Runbook

## 1. 定位

云端只读镜像。本地（192.168.1.2）是**唯一生产源**。
云端（your-cloud-server）仅提供 dashboard 和 public data 的静态文件展示。

云端**不得**运行采集、扫描、策略、推送、review。

## 2. 架构

```
本地 (唯一生产源)
  │
  ├─ build_cloud_publish_bundle.py   # 构建 sanitized bundle
  ├─ publish_cloud_bundle.py         # rsync + atomic promote
  │
  └── rsync ──► 云端
                   ├─ /srv/intel-desk/staging/     # 临时区
                   ├─ /srv/intel-desk/releases/    # 版本历史
                   └─ /srv/intel-desk/current      # symlink -> releases/20260520_235900
```

单向同步：本地 → 云端。**绝不允许**双向同步。

## 3. 发布状态机

```
IDLE
  │
  ├─ dashboard hash 变化 ──► BUILD_BUNDLE
  │                            │
  │                            ├─ secret scan CLEAN ──► PUBLISH_READY
  │                            └─ secret scan BLOCK  ──► ABORT (写 WARN)
  │
  ├─ PUBLISH_READY ──► RSYNC_STAGING
  │                      │
  │                      ├─ rsync OK ──► REMOTE_VERIFY
  │                      └─ rsync FAIL ──► RETRY (最多3次) / ABORT
  │
  ├─ REMOTE_VERIFY
  │   ├─ hash match ──► ATOMIC_PROMOTE ──► DONE
  │   └─ hash mismatch ──► ABORT
  │
  └─ DONE
```

## 4. 同步内容

### 允许同步

- `data/runtime/dashboard/` 全部 HTML/CSS/JS/assets
- `data/runtime/status/` 中 public allowlist 文件（checker results, pipeline markers）
- `data/daily_reports/` 当日 public 文件
- `docs/` 当日 public report/runbook

### 禁止同步

- `.env` `*.key` `*.pem` `*token*` `*cookies*` `secrets*`
- `__pycache__` `venv` `node_modules` `.git`
- `logs` `raw` `pid` `lock` `tmp`
- Raw secret logs、API 缓存、alert push 状态
- 全仓同步

## 5. 失败处理

| 失败类型 | 处理 |
|----------|------|
| Secret scan BLOCK | 停止发布，检查源文件，不覆盖云端 |
| Rsync 失败 | 重试最多 3 次，每次间隔 30s。3 次均失败 → WARN |
| Hash mismatch | 停止发布，不执行 promote。保留 staging 供排查 |
| Promote 失败 | 停止发布，current symlink 不受影响 |
| 连续 3 次发布失败 | 升级 BLOCKER，人工介入 |

## 6. 回滚

云端不存储业务状态，回滚即修改 current symlink：

```bash
# SSH 到云端
cd /srv/intel-desk/releases
ls -1t                    # 列出所有 release
ln -sfn /srv/intel-desk/releases/<previous-release> /srv/intel-desk/current
```

本地发布脚本保留 `keep_releases: 20` 个历史版本，回滚目标始终可用。

## 7. 异常告警规则

**仅在以下情况告警：**

| 告警条件 | 级别 |
|----------|------|
| publish 失败 | WARN |
| 云端 5xx | WARN |
| hash mismatch | WARN |
| stale > 10 分钟 | WARN |
| 连续 3 次 publish 失败 | BLOCKER |
| 云端出现生产脚本 marker | BLOCKER |

**不告警的情况：**
- 云端正常 2xx/3xx
- dashboard hash 未变化（不需要 publish）
- 非生产时间无 activity

## 8. 操作命令

```bash
# 构建 bundle（dry-run）
python3 tools/build_cloud_publish_bundle.py --dry-run

# 构建 bundle（真实）
python3 tools/build_cloud_publish_bundle.py

# 发布到云端（dry-run）
python3 tools/publish_cloud_bundle.py --dry-run

# 发布到云端（真实）
python3 tools/publish_cloud_bundle.py

# 检查云端状态
python3 tools/check_cloud_publish_status.py

# 检查 pipeline 完整性
python3 tools/check_cloud_publish_pipeline.py
```

## 9. 安全规则

1. 本地是唯一生产源，云端是只读镜像。
2. 单向同步：本地 → 云端。绝不允许反向。
3. 每次发布前必须通过 secret scan。
4. Bundle 构建脚本在本地运行，不依赖云端。
5. Rsync 使用 `--delay-updates` 确保原子性。
6. 当前 symlink 原子切换，不出现中间状态。
7. 云端不存储任何 credential / token / key。
