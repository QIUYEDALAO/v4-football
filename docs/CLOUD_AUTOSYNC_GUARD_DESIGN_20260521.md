# Cloud Autosync Guard Design — 2026-05-21

> Phase: CLOUD-PUBLISH-POST-DEPLOY-CLOSEOUT-AND-AUTOSYNC-GUARD-20260521
> Status: **DESIGN ONLY — NOT ENABLED**

---

## 1. Purpose

Design a daily autosync guard that ensures only frozen, secret-free, validated bundles are published to the cloud read-only mirror.

## 2. Trigger Conditions

All must be true:

| # | Condition | Source |
|:-:|:---|---|
| 1 | `intel_ops_console.html` hash changed | md5 check |
| 2 | `candidate_model` hash changed | md5 check |
| 3 | `daily_report` date changed | file list diff |
| 4 | `cloud_publish_allowed` marker = true | status file |

## 3. Blocking Conditions

Any true → block sync:

| # | Condition | Reason |
|:-:|:---|---|
| 1 | `review_status=waiting_result` AND `structured` incomplete | Don't sync unfinished review |
| 2 | Checker FAIL/BLOCKER | Don't sync unverified state |
| 3 | Secret scan FAIL (real secrets) | Never sync credentials |
| 4 | Cron policy dirty | Don't sync when cron not clean |
| 5 | Candidate numbers inconsistent | Data integrity risk |

## 4. Sync Flow

```
1. Local freeze check
2. Bundle build
3. Secret scan (with known FP allowlist)
4. Dry-run rsync
5. Remote snapshot (real copy)
6. Staging rsync upload
7. Atomic symlink switch (staging → current)
8. HTTP/hash verify
9. Publish marker write
```

## 5. Sync Scope

### Allowed
- `data/runtime/dashboard/`
- `data/runtime/status/public/`
- `data/daily_reports/` (frozen only)
- `docs/` (public docs only)

### Forbidden
- `.env`, `*.key`, `*token*`, `secrets*`
- `config/` (all config files)
- `archive/`
- `sshpass`, `.clawvard_token`
- `logs/`, `raw/`, `lock/`, `tmp/`
- `.git/` and git metadata
- Unfrozen temp files

## 6. Sync Mode

| Property | Value |
|:---|:---|
| `source_of_truth` | **local** |
| `cloud_mode` | **readonly_mirror** |
| `reverse_sync` | **false** |
| `rsync_direction` | local → remote only |

## 7. Security

- Credentials stored only in `config/secrets.py` and env vars
- Cloud bundle explicitly excludes all credential files
- Remote SSH uses sshpass (no key file committed)
- Remote has no write-back capability
- Manifest includes sha256 of all bundled files

## 8. Design Decision: Cron Not Enabled

Per BOSS directive: this phase designs the guard but does NOT enable the cron.

Future enablement requires:
1. `tools/check_cloud_autosync_guard.py` implemented
2. BOSS explicit approval to enable cron
3. Gateway cron entry with `--dry-run` first week
4. Full week dry-run data
5. Second BOSS approval to switch to live sync
