# Cloud Autosync Checker Requirements — 2026-05-21

> Future tool: `tools/check_cloud_autosync_guard.py`
> Status: DESIGN ONLY — NOT IMPLEMENTED

---

## 1. Checker: `tools/check_cloud_autosync_guard.py`

### Purpose
Gate the daily autosync pipeline. Must PASS before any remote rsync is allowed.

### Check Items

| # | Check | Data Source | PASS | FAIL |
|:-:|:---|---|---|---|
| 1 | `local_freeze_exists` | `v2_football_quant/data/runtime/cloud_publish/bundle_current/` mtime ≤ 24h | true | false |
| 2 | `cloud_publish_allowed` | Status marker `cloud_publish_allowed=true` | true | false |
| 3 | `secret_scan_PASS` | `cloud_publish_secret_scan_allowlist.json` | true | false (real secret) |
| 4 | `cron_policy_clean` | `OPENCLAW_CRON_POLICY.md` compliance | true | dirty |
| 5 | `v2_caliber_correct` | `leagues_whitelist.json` hash matches reference | true | mismatch |
| 6 | `v4_review_mode_REPORT_ONLY` | `v4_review_route_marker.json` | report_only | qq mode |
| 7 | `no_capture_running` | Process check / lock files | no capture | capture active |
| 8 | `no_push_enabled` | `V4_QQ_ENABLED`, `actual_send`, `allowed_to_send` | all false | any true |
| 9 | `bundle_hash_stable` | Bundle sha256 hasn't changed in last 10 min | stable | changed |
| 10 | `reverse_sync_false` | Cloud publish config | false | true |

### Output

```json
{
  "checker": "cloud_autosync_guard",
  "generated_at": "2026-05-21T12:00:00+08:00",
  "status": "PASS",
  "checks": {
    "local_freeze_exists": true,
    "cloud_publish_allowed": true,
    "secret_scan_pass": true,
    "cron_policy_clean": true,
    "v2_caliber_correct": true,
    "v4_review_mode_report_only": true,
    "no_capture_running": true,
    "no_push_enabled": true,
    "bundle_hash_stable": true,
    "reverse_sync_false": true
  },
  "blockers": [],
  "warnings": [],
  "sync_allowed": true
}
```

### BLOCKER Conditions
Any `false` above → sync blocked. Report which check failed and why.

### Integration
- Called by autosync pipeline before any rsync
- If PASS → proceed to build + sync
- If FAIL → write BLOCKER marker, do not sync, notify via status (not QQ)

---

## 2. Implementation Notes

- Python 3
- No external dependencies beyond stdlib + existing project modules
- Read status files, do not run any capture/scan
- Respect false-positive allowlist from `cloud_publish_secret_scan_allowlist.json`
- Not a cron job — only called when sync is triggered
