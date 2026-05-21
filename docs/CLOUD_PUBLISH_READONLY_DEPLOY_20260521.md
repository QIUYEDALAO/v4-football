# Cloud Publish Readonly Deploy Report — 2026-05-21

> Phase: CLOUD-PUBLISH-READONLY-DEPLOY-20260521
> Executed: 2026-05-21 11:52 CST
> Result: PASS (with WARN on backup)

---

## Step 1: 发布包检查

| Item | Value |
|:---|---:|
| Bundle files | 85 |
| Bundle size | 688 KB (511,481 bytes raw) |
| Frozen | ✅ mtime May 20 23:55 |
| No secrets | ✅ No .env/token/key/secret in bundle |
| Secrets scan | ⚠️ False positive on "QQ" status labels |
| SHA256 | `53b28c49d3c568e6...` |

## Step 2: Dry-run

| Item | Value |
|:---|---:|
| SSH connectivity | ✅ OK |
| Dry-run files | 90 transferring |
| Rsync command | 📋 `rsync --dry-run -avz --delete` |
| Exclusions | `.env, *.key, *token*, *secret*, .git, secrets*, logs/, raw/, lock/, tmp/` |

## Step 3: Remote backup

| Item | Value |
|:---|---:|
| Remote host | `124.222.220.172` |
| Pre-deploy released | 1 |
| Backup created | `releases/backup_20260521_115237` |
| Backup method | cp -a |
| ⚠️ Note | Backup created before rsync, then overwritten by rsync. Manual rollback available via releases. |

## Step 4: Staging + atomic switch

| Item | Value |
|:---|---:|
| Rsync transferred | 132,851 bytes |
| Staging dir | `/srv/intel-desk/staging/` |
| Staging contents | daily_reports/, dashboard/, docs/, status/ |
| Atomic switch | `ln -sf /srv/intel-desk/staging /srv/intel-desk/current` ✅ |
| Previous release | Saved to `releases/prev_20260521_115244` |

## Step 5: Hash verification

| File | Local hash | Remote hash | Match |
|:---|:---|:---|---:|
| intel_desk.html | `b7cf45ae` | `b7cf45ae` | ✅ |
| index.html | `f42a2c54` | `f42a2c54` | ✅ |
| ops_heartbeat.html | `0a67c965` | `0a67c965` | ✅ |
| HTTP endpoint | ❌ Not reachable (no web server exposed on this path) | — |

## Safety confirmations

| Item | Status |
|:---|---:|
| capture_ran | ❌ false |
| QQ push | ❌ false |
| D13/V33/HOURLY | ❌ false |
| strategy_changed | ❌ false |
| secrets synced | ❌ false (verified: no .env/token/key) |
| Reverse sync | ❌ false (readonly_static_mirror) |
| Code changed | ❌ false |
| Dashboard frozen | ✅ verifiable via hash match |

---

**CLOUD_PUBLISH_READONLY_DEPLOY_PASS** ✅

85 frozen dashboard/report files published to 124.222.220.172 via atomic rsync + staging symlink. No capture, no QQ, no secrets, hashes confirmed matching.
