# Cloud Publish Readonly Deploy V3/V4 Final — Report

**Phase:** CLOUD-PUBLISH-READONLY-DEPLOY-V3V4-FINAL-20260524
**Generated:** 2026-05-24 09:33 CST
**Executed by:** ClawOps (Phase C read-only deploy)

---

## 1. Step Summary

| Step | Status |
|:-----|:------:|
| Step 1: Precheck | ✅ PASS |
| Step 2: Remote Status | ✅ PASS |
| Step 3: Remote Backup | ✅ PASS (real_copy) |
| Step 4: Staging Upload | ✅ PASS (81 files, hash match) |
| Step 5: Atomic Switch | ✅ PASS (current → new release) |
| Step 6: HTTP / Hash Verify | ✅ PASS |
| Step 7: Local State Verify | ✅ PASS |
| Step 8: Report | ✅ PASS |

## 2. Deployment Details

| Item | Value |
|:-----|:------|
| Publish source | **local** (唯一生产源) |
| reverse_sync | **false** |
| Backup type | **real_copy** |
| Backup path | `/srv/intel-desk/releases/backup_20260524_0931` |
| Backup file count | 92 |
| Bundle file count | 81 |
| Upload file count | 81 |
| Local/Remote hash match | ✅ `6cb179d1...` |
| Remote release path | `/srv/intel-desk/releases/release_20260524_0931` |
| nginx root updated | staging → current |

## 3. HTTP / Dashboard Verify

| Check | Result |
|:------|:------:|
| HTTP / (index.html) | 200 ✅ |
| HTTP /intel_ops_console.html | 200 ✅ |
| HTTP /manifest.json | 200 ✅ |
| HTTP /api_cache.html | 200 ✅ |
| HTTP /daily_reports/* | 200 ✅ |
| HTTP /status/* | 200 ✅ |
| Dashboard title | 情报决策总台 — V3/V4 ✅ |
| V2 visible in dashboard | **0** ✅ |
| V33 visible in dashboard | **0** ✅ |
| C visible in dashboard | **0** ✅ |
| 近7天 visible | **0** ✅ |
| script UI compact | ✅ retained |
| source_window | **daily_1200** ✅ |
| API disabled shown | ❌ (not shown - correct) |
| Result validation visible | ✅ present |

## 4. Secret & File Checks

| Check | Result |
|:------|:------:|
| Secrets synced to remote | **false** ✅ |
| Raw dump synced | **false** ✅ |
| Backup synced | **false** ✅ |
| .env/.key/.pem on remote | **0** ✅ |
| .bak/.orig on remote | **0** ✅ |

## 5. Prohibitions Status

| Prohibition | Status |
|:------------|:------:|
| reverse_sync | ✅ not executed |
| Full V4 scan | ✅ not run (pre-existing scan from 06:45) |
| Capture | ✅ not run |
| QQ push | ✅ not executed |
| Cron created/enabled | ✅ not created |
| Autosync cron created | ✅ not created |
| git add/commit/push/pull | ✅ not executed |
| git merge/rebase/reset | ✅ not executed |
| V2 restored | ✅ not restored |
| V33 active | ✅ not restored |
| C visible in dashboard | ✅ not restored |
| Strategy changed | ✅ unchanged |
| V4 candidate numbers | ✅ unchanged |
| Result validation modified | ✅ unchanged |
| Script validation modified | ✅ unchanged |
| Attribution numbers | ✅ unchanged |
| Secrets printed | ✅ not printed |

## 6. Cloud State After Deploy

| Path | Value |
|:-----|:------|
| current symlink | `/srv/intel-desk/current → /srv/intel-desk/releases/release_20260524_0931` |
| prev (rollback) | `/srv/intel-desk/releases/prev_20260524_0931 → /srv/intel-desk/staging` |
| backup | `/srv/intel-desk/releases/backup_20260524_0931` (real_copy, 92 files) |
| nginx root | `/srv/intel-desk/current/dashboard` |
| nginx config test | ✅ syntax OK |

## 7. Rollback Procedure

```bash
# Option A: Switch back to staging (previous production)
ssh root@124.222.220.172 "ln -sfn /srv/intel-desk/staging /srv/intel-desk/current && nginx -s reload"

# Option B: Use backup (real_copy)
ssh root@124.222.220.172 "ln -sfn /srv/intel-desk/releases/backup_20260524_0931 /srv/intel-desk/current && nginx -s reload"
```

## 8. Final Conclusion

```
CLOUD_PUBLISH_READONLY_DEPLOY_V3V4_FINAL_PASS
```
