#!/usr/bin/env python3
"""Publish sanitized bundle to cloud read-only mirror via rsync + atomic symlink.

Reads latest manifest, rsyncs to remote staging, verifies hash,
moves to releases/{timestamp}, atomically updates current symlink.

NEVER rsyncs whole repo, .git, .env, or raw secret logs.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
BUNDLE_DIR = MODULE / "data" / "runtime" / "cloud_publish" / "bundle_current"
MANIFEST_DIR = MODULE / "data" / "runtime" / "cloud_publish"
CONFIG_DIR = MODULE / "config"
STATUS_DIR = MODULE / "data" / "runtime" / "status"

RSYNC_EXCLUDE_ALWAYS = [
    ".env", "*.key", "*.pem", "*token*", "*cookies*", "secrets*",
    ".git", "__pycache__", "venv", "node_modules",
    "logs", "raw", "pid", "lock", "tmp",
]


def load_config():
    """Load cloud_publish.yml config. Returns None if not found."""
    config_path = CONFIG_DIR / "cloud_publish.yml"
    if not config_path.is_file():
        print(f"  Config not found: {config_path}")
        print(f"  Copy config/cloud_publish.example.yml to config/cloud_publish.yml and fill in values.")
        return None

    import yaml
    try:
        with open(config_path) as f:
            return yaml.safe_load(f)
    except ImportError:
        # Fallback: parse simple YAML manually
        cfg = {}
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if val.isdigit():
                        val = int(val)
                    cfg[key] = val
        return cfg


def load_latest_manifest():
    """Load the latest manifest."""
    latest = MANIFEST_DIR / "cloud_publish_manifest_latest.json"
    if not latest.is_file():
        print("  No latest manifest found. Run build_cloud_publish_bundle.py first.")
        return None

    data = json.loads(latest.read_text())
    manifest_name = data.get("latest_manifest")
    if not manifest_name:
        return None

    manifest_path = MANIFEST_DIR / manifest_name
    if not manifest_path.is_file():
        return None

    return json.loads(manifest_path.read_text())


def verify_local_bundle(manifest):
    """Verify local bundle sha256 matches manifest."""
    if not BUNDLE_DIR.is_dir():
        return False, "bundle_current directory missing"

    import hashlib
    hasher = hashlib.sha256()
    file_count = 0
    for f in sorted(manifest.get("files", []), key=lambda x: x["path"]):
        fpath = BUNDLE_DIR / f["path"]
        if fpath.is_file():
            hasher.update(fpath.read_bytes())
            file_count += 1

    computed = hasher.hexdigest()
    expected = manifest.get("sha256", "")
    ok = computed == expected
    return ok, f"local sha256={'OK' if ok else 'MISMATCH'} files={file_count} expected={expected[:16]}... computed={computed[:16]}..."


def build_rsync_command(cfg, manifest):
    """Build rsync command with all safety exclusions."""
    remote = f"{cfg['cloud_user']}@{cfg['cloud_host']}"
    remote_staging = cfg["remote_staging_dir"]

    # Build --exclude args
    exclude_args = []
    for pat in RSYNC_EXCLUDE_ALWAYS:
        exclude_args.extend(["--exclude", pat])
    for pat in cfg.get("sync_exclude_extra", []) or []:
        exclude_args.extend(["--exclude", pat])

    cmd = [
        "rsync",
        "--archive",
        "--compress",
        "--delete",
        "--delay-updates",
        "--partial",
        "--chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r",
    ]
    if cfg.get("rsync_bwlimit"):
        cmd.extend(["--bwlimit", str(cfg["rsync_bwlimit"])])
    if cfg.get("ssh_key_path"):
        cmd.extend(["-e", f"ssh -i {cfg['ssh_key_path']} -p {cfg.get('cloud_port', 22)}"])
    else:
        cmd.extend(["-e", f"ssh -p {cfg.get('cloud_port', 22)}"])

    cmd.extend(exclude_args)
    cmd.append(f"{BUNDLE_DIR}/")
    cmd.append(f"{remote}:{remote_staging}/")

    return cmd


def run_ssh(cfg, command):
    """Run a command on remote host via SSH."""
    ssh_cmd = ["ssh"]
    if cfg.get("ssh_key_path"):
        ssh_cmd.extend(["-i", cfg["ssh_key_path"]])
    ssh_cmd.extend(["-p", str(cfg.get("cloud_port", 22))])
    ssh_cmd.append(f"{cfg['cloud_user']}@{cfg['cloud_host']}")
    ssh_cmd.append(command)

    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout, result.stderr


def remote_verify_hash(cfg, manifest):
    """Verify SHA256 of staged bundle on remote."""
    remote_staging = cfg["remote_staging_dir"]
    expected_sha = manifest["sha256"]

    cmd = f"cd {remote_staging} && find . -type f | sort | xargs cat | sha256sum"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    if ret != 0:
        return False, f"remote hash check failed: {stderr}"
    remote_sha = stdout.strip().split()[0] if stdout.strip() else ""
    ok = remote_sha == expected_sha
    return ok, f"remote sha256={'OK' if ok else 'MISMATCH'}: expected={expected_sha[:16]}... got={remote_sha[:16] if remote_sha else 'none'}"


def atomic_promote(cfg, manifest):
    """Move staging to releases/{timestamp} and atomically update current symlink."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    release_dir = f"{cfg['remote_releases_dir']}/{ts}"

    script = f"""
set -e
mv {cfg['remote_staging_dir']} {release_dir}
ln -sfn {release_dir} {cfg['remote_current_symlink']}
# Cleanup old releases
cd {cfg['remote_releases_dir']} && ls -1t | tail -n +{cfg.get('keep_releases', 20) + 1} | xargs -r rm -rf
echo "PROMOTED:{ts}"
"""
    ret, stdout, stderr = run_ssh(cfg, script)
    ok = ret == 0 and "PROMOTED" in stdout
    return ok, stdout.strip() if ok else f"promote failed: {stderr}"


def write_publish_status(manifest, success, detail):
    """Write local publish status marker."""
    status = {
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "success": success,
        "detail": detail,
        "manifest": manifest.get("generated_at", ""),
        "sha256": manifest.get("sha256", ""),
        "v4_counts": manifest.get("current_v4_counts", {}),
        "source_window": manifest.get("source_window", ""),
    }
    marker = STATUS_DIR / "cloud_publish_status.json"
    marker.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    return marker


def main():
    dry_run = "--dry-run" in sys.argv
    skip_remote = "--skip-remote" in sys.argv

    print(f"=== cloud_publish publisher ===\n")
    print(f"  Mode: {'DRY-RUN' if dry_run else 'PUBLISH'}")
    if skip_remote:
        print(f"  Remote sync: SKIPPED")

    cfg = load_config()
    if cfg is None:
        print(f"\n  Conclusion: BLOCKED — no cloud_publish.yml config")
        return 1

    manifest = load_latest_manifest()
    if manifest is None:
        print(f"\n  Conclusion: BLOCKED — no manifest found")
        return 1

    if not manifest.get("publish_ready"):
        print(f"\n  Conclusion: BLOCKED — manifest publish_ready=false (secret scan failed)")
        return 1

    print(f"\n  Manifest: {manifest['generated_at']}")
    print(f"  Files: {manifest['total_files']}")
    print(f"  SHA256: {manifest['sha256'][:32]}...")

    # Step 1: Verify local bundle
    local_ok, local_detail = verify_local_bundle(manifest)
    print(f"\n  [{'PASS' if local_ok else 'FAIL'}] Local verify: {local_detail}")
    if not local_ok:
        write_publish_status(manifest, False, local_detail)
        print(f"\n  Conclusion: BLOCKED — local hash mismatch")
        return 1

    if dry_run or skip_remote:
        print(f"\n  Remote steps skipped (dry-run).")
        print(f"  Would rsync to: {cfg['cloud_user']}@{cfg['cloud_host']}:{cfg['remote_staging_dir']}/")
        if not dry_run:
            write_publish_status(manifest, True, "local_verified (remote skipped)")
        print(f"\n  Conclusion: READY (no remote sync)")
        return 0

    # Step 2: Rsync to staging
    rsync_cmd = build_rsync_command(cfg, manifest)
    print(f"\n  Rsync: {' '.join(rsync_cmd)}")
    result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        detail = f"rsync failed (code={result.returncode}): {result.stderr[:200]}"
        print(f"  [FAIL] {detail}")
        write_publish_status(manifest, False, detail)
        print(f"\n  Conclusion: FAIL — rsync failed")
        return 1
    print(f"  [PASS] Rsync complete")

    # Step 3: Remote hash verify
    hash_ok, hash_detail = remote_verify_hash(cfg, manifest)
    print(f"  [{'PASS' if hash_ok else 'FAIL'}] Remote verify: {hash_detail}")
    if not hash_ok:
        write_publish_status(manifest, False, hash_detail)
        print(f"\n  Conclusion: FAIL — remote hash mismatch")
        return 1

    # Step 4: Atomic promote
    promote_ok, promote_detail = atomic_promote(cfg, manifest)
    print(f"  [{'PASS' if promote_ok else 'FAIL'}] Promote: {promote_detail}")
    if not promote_ok:
        write_publish_status(manifest, False, promote_detail)
        print(f"\n  Conclusion: FAIL — promote failed")
        return 1

    # Step 5: Write success status
    write_publish_status(manifest, True, promote_detail)
    print(f"\n  Conclusion: PUBLISHED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
