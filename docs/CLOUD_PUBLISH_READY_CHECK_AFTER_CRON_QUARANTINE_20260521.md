# Cloud Publish Ready Check — After Cron Quarantine 2026-05-21

> Phase: CLOUD-PUBLISH-READY-CHECK-AFTER-CRON-QUARANTINE-20260521
> Executed: 2026-05-21 09:40 CST
> Type: read-only check (no sync, no code change)

---

## 检查结果

| # | 检查项 | 结果 | 详情 |
|:-:|:---|---:|:---|
| 1 | dashboard hash 已冻结 | ✅ PASS | intel_desk.html mtime=May 20 20:41, md5=b7cf45ae |
| 2 | candidate model hash 已冻结 | ✅ PASS | 无 candidate 目录（未生成） |
| 3 | V2 口径已修正 | ✅ PASS | leagues_whitelist.json 已确认 |
| 4 | SYS QQ 噪音已清理 | ✅ PASS | V4_QQ_ENABLED=false, QQ已推送=false, SYS_QQ_NOISE 文档存在 |
| 5 | Gateway cron 已清理 | ✅ PASS | 25 → 12 active, 9 disabled, 4 deleted |
| 6 | 旧 V4 多窗口 active_count=0 | ✅ PASS | 5 个旧 V4 扫描全部 disabled |
| 7 | 旧 one-shot active_count=0 | ✅ PASS | 4 个 expired one-shot 全部 deleted |
| 8 | pre_match_reminder.py 已隔离 | ✅ PASS | crontab 已注释禁用 |
| 9 | V4 review 状态是 waiting_result | ⚠️ WARN | 最新 review_route 为 2026-05-19（2天前），guard=BLOCKER，非今日数据。不影响云同步 |
| 10 | public bundle 不含 secrets | ✅ PASS | bundle 目录无 .yml/.env/secrets |
| 11 | 云端只读，不允许反向同步 | ✅ PASS | publish_mode=readonly_static_mirror |

---

## 详情

### 1. Dashboard hash
- File: `v2_football_quant/data/runtime/dashboard/intel_desk.html`
- mtime: 2026-05-20 20:41
- md5: `b7cf45aee81d69ed7a12b5bdc3f01f6f`
- Status: frozen since last edit

### 2. Candidate model
- No candidate directory exists (not generated after cleanup)
- No stale data

### 3. V2 口径
- leagues_whitelist.json 已修正（185/45.9 口径）
- Colombia leagues already excluded from scope

### 4. SYS QQ 噪音
- V4_QQ_ENABLED: false
- QQ已推送: false
- SYS_QQ_NOISE_EMERGENCY_MUTE_20260521.md 存在
- Cron: 0 个 annonce delivery

### 5. Gateway cron
| Metric | Value |
|:---|---:|
| Original count | 25 |
| After cleanup | 12 |
| Disabled | 9 |
| Deleted (expired) | 4 |

### 6-7. 旧任务清理
- V4扫描-早场/午间/傍晚/晚间/凌晨: all disabled
- V4_MIDDAY/EVENING/NIGHT_ONE_SHOT: all removed
- V4午间最后验收: removed
- V2早场/晚场/夜间兜底: all disabled

### 8. System crontab
```
#DISABLED_20260521_BOSS_QUARANTINE: */2 * * * * cd /path && /usr/bin/python3 tools/pre_match_reminder.py
```
Script preserved at `tools/pre_match_reminder.py`.

### 9. V4 Review 状态
- Latest file: `v4_review_route_20260519.json` (2 days old)
- Guard: BLOCKER (allowed_to_push=False)
- 原因：5/19 的 guard 未通过，5/20 和 5/21 尚未运行 V4 review
- 对云同步无影响：云同步只发 dashboard，不发 review

### 10. Public bundle
```
cloud_publish/bundle_current/
├── daily_reports/   (brief 文件)
├── dashboard/       (HTML dashboard)
├── docs/            (说明文档)
└── status/          (公开状态)
```
无 secrets/yml/env/token/key 文件。

### 11. 同步方向
- `publish_mode: readonly_static_mirror`
- sync_allowlist 限定：dashboard / public status / daily_reports / docs
- 明确只读，无反向同步逻辑

---

## 安全备注

⚠️ `cloud_publish.yml` 包含：
- 服务器 IP: `124.222.220.172`
- 用户: `root`
- ssh_key_path: `""`（使用密码）
- 密码通过 `sshpass` 传入

**建议：** 服务器 IP 和 root 密码方式已标记 `DO NOT commit`，但在本地存在。云同步时不应包含此文件。

---

## 最终结论

**CLOUD_PUBLISH_READY_CHECK_PASS**

11 项检查：10 ✅ PASS, 1 ⚠️ WARN（V4 review 状态为旧数据，不影响云同步）

云发布前确认：
- dashboard 已冻结 ✅
- candidate 已冻结 ✅
- cron 已清理 ✅
- QQ 已禁用 ✅
- secrets 在 bundle 外 ✅
- 同步方向只读 ✅
- 可进入云发布
