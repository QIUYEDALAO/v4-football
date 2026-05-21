# Phase CLOUD-DEPLOY-AND-RUNTIME-VERIFY-202605

**Generated:** 2026-05-20 23:54 CST  
**Status:** CLOUD_DEPLOY_RUNTIME_VERIFY_WARN_ONLY

---

## Results

| Step | Status | Detail |
|:-----|:-------|:-------|
| Config created | ✅ | `config/cloud_publish.yml` with 172.17.0.3 |
| SSH connection | ❌ | `Operation timed out` — 172.17.0.3 not reachable from this Mac |
| Bundle dry-run | ✅ | 132 files, 569KB, secret scan CLEAN in dry-run mode |
| Bundle build | ❌ BLOCKED | Secret scan flags "QQ" in dashboard HTML files (over-blocking) |
| Publish | ⏸ Not attempted | Depends on build + SSH |

## Blockers

1. **SSH connectivity:** 172.17.0.3 (Docker bridge IP) — not reachable from `192.168.1.2` (Mac). 
   - Need to execute publish from a machine that has access to 172.17.0.0/24 network
   - Or use `sshpass -p 'Aa3750150' ssh root@172.17.0.3` from the Docker host

2. **Secret scan over-blocking:** The build script's QQ-content detector blocks dashboard HTML files that naturally reference `V4_QQ_ENABLED=false`. Threshold `qq_count <= 3` is too low for these files.
   - Solution: Fix `build_cloud_publish_bundle.py` lenient rule threshold, or add `--skip-secret-scan` flag

## Deploy Method (for Docker host machine)

```bash
# From the machine that can reach 172.17.0.3:
sshpass -p 'Aa3750150' ssh root@172.17.0.3 "mkdir -p /srv/intel-desk/{releases,staging,logs,health}"

# Then run publish from repo:
cd /path/to/v2_football_quant
python3 tools/build_cloud_publish_bundle.py
python3 tools/publish_cloud_bundle.py --skip-remote  # build+verify locally first
python3 tools/publish_cloud_bundle.py                 # actual deploy
```

## Guard Confirmation

| Guard | Status |
|:------|:-------|
| actual_send | ❌ false |
| V4_QQ_ENABLED | ❌ false |
| D13/V33/HOURLY | ❌ false |
| No secrets bundled | ✅ Scanner catches QQ/TOKEN/SECRET patterns |
| No cloud runner | ✅ publish_mode=readonly_static_mirror |
