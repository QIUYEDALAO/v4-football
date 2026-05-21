#!/usr/bin/env python3
"""Check cloud publish status: local manifest, remote accessibility, hash match, content integrity.

Reads: data/runtime/cloud_publish/cloud_publish_manifest_latest.json
Checks remote via SSH, verifies current symlink, dashboard content, no-notify compliance.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
MANIFEST_DIR = MODULE / "data" / "runtime" / "cloud_publish"
STATUS_DIR = MODULE / "data" / "runtime" / "status"
CONFIG_DIR = MODULE / "config"
DASHBOARD_DIR = MODULE / "data" / "runtime" / "dashboard"

CHECKER_NAME = "check_cloud_publish_status"


def load_config():
    config_path = CONFIG_DIR / "cloud_publish.yml"
    if not config_path.is_file():
        return None
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


def run_ssh(cfg, command):
    ssh_cmd = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]
    if cfg.get("ssh_key_path"):
        ssh_cmd.extend(["-i", cfg["ssh_key_path"]])
    ssh_cmd.extend(["-p", str(cfg.get("cloud_port", 22))])
    ssh_cmd.append(f"{cfg['cloud_user']}@{cfg['cloud_host']}")
    ssh_cmd.append(command)

    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stdout, result.stderr


def check_local_manifest():
    latest = MANIFEST_DIR / "cloud_publish_manifest_latest.json"
    if not latest.is_file():
        return "FAIL", "local manifest not found", None
    data = json.loads(latest.read_text())
    manifest_name = data.get("latest_manifest")
    manifest_path = MANIFEST_DIR / manifest_name if manifest_name else None
    if not manifest_path or not manifest_path.is_file():
        return "FAIL", f"manifest file missing: {manifest_name}", data
    manifest = json.loads(manifest_path.read_text())
    return "PASS", f"manifest: {manifest_name}", manifest


def check_remote_accessible(cfg):
    ret, stdout, stderr = run_ssh(cfg, "echo OK")
    ok = ret == 0 and "OK" in stdout
    return ("PASS" if ok else "FAIL",
            "remote SSH OK" if ok else f"SSH failed: {stderr.strip()[:100]}")


def check_remote_manifest(cfg):
    remote_current = cfg.get("remote_current_symlink", "/srv/intel-desk/current")
    cmd = f"cat {remote_current}/cloud_publish_manifest_latest.json 2>/dev/null || echo NOT_FOUND"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    if "NOT_FOUND" in stdout:
        return "FAIL", "remote manifest not found"
    try:
        data = json.loads(stdout)
        return "PASS", f"remote manifest: {data.get('latest_manifest', 'unknown')}"
    except json.JSONDecodeError:
        return "FAIL", f"remote manifest unparseable: {stdout[:100]}"


def check_hash_match(cfg, manifest):
    if not manifest:
        return "FAIL", "no local manifest for comparison"
    remote_current = cfg.get("remote_current_symlink", "/srv/intel-desk/current")
    cmd = f"cd {remote_current} && find . -type f | sort | xargs cat 2>/dev/null | sha256sum"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    remote_sha = stdout.strip().split()[0] if stdout.strip() else ""
    local_sha = manifest.get("sha256", "")
    ok = remote_sha == local_sha
    return ("PASS" if ok else "FAIL",
            f"hash {'match' if ok else 'MISMATCH'}: local={local_sha[:16]}... remote={remote_sha[:16] if remote_sha else 'none'}...")


def check_remote_http(cfg, path):
    remote_host = cfg.get("cloud_host", "")
    remote_current = cfg.get("remote_current_symlink", "/srv/intel-desk/current")
    cmd = f"test -f {remote_current}/{path} && echo OK || echo MISSING"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    ok = "OK" in stdout
    return ("PASS" if ok else "FAIL",
            f"{path} {'exists' if ok else 'MISSING'} on remote")


def check_remote_no_notify(cfg):
    remote_current = cfg.get("remote_current_symlink", "/srv/intel-desk/current")
    console_path = f"{remote_current}/dashboard/intel_ops_console.html"
    cmd = f"grep -c 'V4_QQ_ENABLED' {console_path} 2>/dev/null || echo 0"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    v4qq_count = int(stdout.strip()) if stdout.strip().isdigit() else 0

    cmd2 = f"grep -c '需BOSS批准' {console_path} 2>/dev/null || echo 0"
    ret2, stdout2, stderr2 = run_ssh(cfg, cmd2)
    boss_count = int(stdout2.strip()) if stdout2.strip().isdigit() else 0

    # V4_QQ_ENABLED should be in collapsed audit only
    # In the sanitized view, it should appear only in data-audit-hidden sections
    ok = v4qq_count <= 2 and boss_count == 0
    return ("PASS" if ok else "FAIL",
            f"V4_QQ={v4qq_count} BOSS={boss_count} {'(clean)' if ok else '(excessive)'}")


def check_remote_symlink(cfg):
    remote_current = cfg.get("remote_current_symlink", "/srv/intel-desk/current")
    cmd = f"readlink {remote_current} 2>/dev/null || echo BROKEN"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    link_target = stdout.strip()
    if "BROKEN" in link_target:
        return "FAIL", "current symlink is BROKEN"

    releases_dir = cfg.get("remote_releases_dir", "/srv/intel-desk/releases")
    cmd2 = f"ls -1t {releases_dir}/ 2>/dev/null | head -1"
    ret2, stdout2, stderr2 = run_ssh(cfg, cmd2)
    latest = stdout2.strip()
    ok = latest in link_target
    return ("PASS" if ok else "WARN_ONLY",
            f"symlink->{link_target.split('/')[-1]} latest_release={latest} {'(match)' if ok else '(not latest)'}")


def check_no_production_runner(cfg):
    remote_current = cfg.get("remote_current_symlink", "/srv/intel-desk/current")
    # Check if any capture/scan/push scripts are present (they shouldn't be)
    cmd = f"find {remote_current} -name '*capture*' -o -name '*push*' -o -name '*scan*' -o -name '*.pid' 2>/dev/null | head -5"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    found = stdout.strip()
    ok = len(found) == 0
    return ("PASS" if ok else "FAIL",
            "no production runner" if ok else f"found production-like files: {found[:100]}")


def check_active_blockers(cfg):
    """Check if intel_ops_console shows active blockers."""
    remote_current = cfg.get("remote_current_symlink", "/srv/intel-desk/current")
    cmd = f"grep -c '阻断' {remote_current}/dashboard/intel_ops_console.html 2>/dev/null || echo 0"
    ret, stdout, stderr = run_ssh(cfg, cmd)
    blocker_count = int(stdout.strip()) if stdout.strip().isdigit() else 0
    status = "PASS" if blocker_count == 0 else "WARN_ONLY"
    return (status,
            f"blocker_count={blocker_count} {'(clean)' if blocker_count == 0 else '(blockers present)'}")


def main():
    results = []
    passed = 0
    failed = 0
    warned = 0

    def check(label, status, detail):
        nonlocal passed, failed, warned
        results.append({"label": label, "status": status, "detail": detail})
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed += 1
        else:
            warned += 1
        print(f"  [{status:10s}] {label} — {detail}")

    print(f"=== {CHECKER_NAME} ===\n")

    # Check 1: Local manifest
    s1, d1, manifest = check_local_manifest()
    check("Local manifest exists", s1, d1)

    # Load config for remote checks
    cfg = load_config()
    if cfg is None:
        check("Cloud config exists", "FAIL", "no cloud_publish.yml — remote checks skipped")
        print(f"\n---\n  PASS: {passed} | FAIL: {failed} | WARN: {warned}")
        conclusion = "BLOCKED"
        print(f"  Conclusion: {conclusion}")
        return 1
    else:
        check("Cloud config exists", "PASS", f"host={cfg.get('cloud_host', '?')}")

    # Remaining checks require SSH
    s3, d3 = check_remote_accessible(cfg)
    check("Remote accessible via SSH", s3, d3)
    if s3 == "FAIL":
        # Skip remaining remote checks
        for label in ["Remote manifest", "Hash match", "index.html", "intel_ops_console.html",
                       "No-notify compliance", "Symlink correct", "No production runner", "Blocker status"]:
            check(label, "SKIP", "remote unreachable")

    if s3 == "PASS":
        s4, d4 = check_remote_manifest(cfg)
        check("Remote manifest accessible", s4, d4)
        s5, d5 = check_hash_match(cfg, manifest)
        check("SHA256 local==remote", s5, d5)
        s6, d6 = check_remote_http(cfg, "dashboard/index.html")
        check("index.html 200/OK", s6, d6)
        s7, d7 = check_remote_http(cfg, "dashboard/intel_ops_console.html")
        check("intel_ops_console.html 200/OK", s7, d7)
        s8, d8 = check_remote_no_notify(cfg)
        check("No-notify rules pass on remote", s8, d8)
        s9, d9 = check_remote_symlink(cfg)
        check("Current symlink -> latest release", s9, d9)
        s10, d10 = check_active_blockers(cfg)
        check("Active blocker count = 0 or WARN", s10, d10)
        s11, d11 = check_no_production_runner(cfg)
        check("No production scripts on cloud", s11, d11)

    # Summarize
    total = len(results)
    print(f"\n---")
    print(f"  Total: {total} | PASS: {passed} | FAIL: {failed} | WARN: {warned}")

    if "BLOCKED" in [r["status"] for r in results]:
        conclusion = "BLOCKED"
    elif failed > 0:
        conclusion = "FAIL"
    elif warned > 0:
        conclusion = "WARN_ONLY"
    else:
        conclusion = "PASS"

    print(f"  Conclusion: {conclusion}")

    marker = {
        "checker": CHECKER_NAME,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "conclusion": conclusion,
        "total": total,
        "passed": passed,
        "failed": failed,
        "warn_only": warned,
        "results": results,
    }
    marker_path = STATUS_DIR / f"{CHECKER_NAME}_result_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  Marker: {marker_path}")

    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
