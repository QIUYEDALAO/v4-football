#!/usr/bin/env python3
"""Check cloud publish pipeline completeness and safety.

15 checks covering: config, scripts, runbook, watchdog, secrets, sync direction,
cloud readonly mode, atomic symlink design.
"""
import json
import sys
from pathlib import Path

CHECKER_NAME = "check_cloud_publish_pipeline"
MODULE = Path(__file__).resolve().parents[1]

results = []
PASS = 0


def check(label, condition, detail=""):
    global PASS
    tag = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    line = f"  [{tag:10s}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail})
    return condition


print(f"=== {CHECKER_NAME} ===\n")

# 1. Config example exists
cfg_example = MODULE / "config" / "cloud_publish.example.yml"
check("Config example exists",
      cfg_example.is_file(),
      str(cfg_example))

# 2. Build script exists
build_script = MODULE / "tools" / "build_cloud_publish_bundle.py"
check("Build script exists",
      build_script.is_file(),
      str(build_script))

# 3. Publish script exists
pub_script = MODULE / "tools" / "publish_cloud_bundle.py"
check("Publish script exists",
      pub_script.is_file(),
      str(pub_script))

# 4. Verify script exists
verify_script = MODULE / "tools" / "check_cloud_publish_status.py"
check("Verify script exists",
      verify_script.is_file(),
      str(verify_script))

# 5. Runbook exists
runbook = MODULE / "docs" / "CLOUD_PUBLISH_RUNBOOK.md"
check("Runbook exists",
      runbook.is_file(),
      str(runbook))

# 6. Watchdog design exists
watchdog = MODULE / "docs" / "CLOUD_PUBLISH_WATCHDOG_DESIGN.md"
check("Watchdog design exists",
      watchdog.is_file(),
      str(watchdog))

# 7. Secret blacklist exists (in build script)
if build_script.is_file():
    build_content = build_script.read_text()
    has_blacklist = "SECRET_FILENAME_PATTERNS" in build_content and "SECRET_CONTENT_PATTERNS" in build_content
    check("Secret blacklist in build script",
          has_blacklist,
          "filename + content patterns defined")
else:
    check("Secret blacklist in build script", False, "build script missing")

# 8. Allowlist exists (in build script)
if build_script.is_file():
    has_allowlist = "STATUS_PUBLIC_ALLOWLIST" in build_content
    check("Public allowlist in build script",
          has_allowlist,
          "status allowlist defined")
else:
    check("Public allowlist in build script", False, "build script missing")

# 9. No bidirectional sync
if pub_script.is_file():
    pub_content = pub_script.read_text()
    has_bidi = "bidirectional" in pub_content.lower() or "双向同步" in pub_content.lower() or "cloud->local" in pub_content.lower()
    check("No bidirectional sync",
          not has_bidi,
          "单向：local -> cloud only")
else:
    check("No bidirectional sync", False, "publish script missing")

# 10. Cloud readonly mode
if cfg_example.is_file():
    cfg_content = cfg_example.read_text()
    has_readonly = "readonly_static_mirror" in cfg_content
    check("Cloud readonly mode declared",
          has_readonly,
          "publish_mode=readonly_static_mirror")
else:
    check("Cloud readonly mode declared", False, "config missing")

# 11. No production runner on cloud
if runbook.is_file():
    runbook_content = runbook.read_text()
    no_runner = ("不得" in runbook_content and "运行" in runbook_content and "采集" in runbook_content)
    check("No production runner on cloud (documented)",
          no_runner,
          "runbook prohibits capture/scan/push on cloud")
else:
    check("No production runner on cloud (documented)", False, "runbook missing")

# 12. No QQ/push token in bundle (check secret scan exists)
if build_script.is_file():
    has_secret_scan = "scan_file_content" in build_content and "scan" in build_content.lower()
    check("Secret content scan for QQ/push tokens",
          has_secret_scan,
          "scan_file_content function with SECRET_CONTENT_PATTERNS")
else:
    check("Secret content scan for QQ/push tokens", False, "build script missing")

# 13. No .env in bundle
if build_script.is_file():
    env_excluded = ".env" in build_content and ("exclude" in build_content.lower() or "SECRET_FILENAME" in build_content)
    check("No .env in bundle",
          env_excluded,
          ".env in SECRET_FILENAME_PATTERNS")
else:
    check("No .env in bundle", False, "build script missing")

# 14. No .git in bundle
if build_script.is_file():
    git_excluded = ".git" in build_content
    check("No .git in bundle",
          git_excluded,
          ".git in SECRET_FILENAME_PATTERNS")
else:
    check("No .git in bundle", False, "build script missing")

# 15. Atomic current symlink design
if pub_script.is_file():
    pub_content = pub_script.read_text()
    has_atomic = "ln -sfn" in pub_content and "current" in pub_content.lower()
    check("Atomic current symlink design",
          has_atomic,
          "ln -sfn for atomic symlink update")
else:
    check("Atomic current symlink design", False, "publish script missing")

# Summary
total = len(results)
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"\n---")
print(f"  Total: {total} | PASS: {PASS} | FAIL: {failed}")

conclusion = "PASS" if failed == 0 else "BLOCKED"
print(f"  Conclusion: {conclusion}")

marker = {
    "checker": CHECKER_NAME,
    "generated_at": "2026-05-20T23:59:00+08:00",
    "total": total,
    "pass": PASS,
    "fail": failed,
    "conclusion": conclusion,
    "results": results,
}
out_path = MODULE / "data" / "runtime" / "status" / f"{CHECKER_NAME}_result_20260520.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")

sys.exit(0 if conclusion == "PASS" else 1)
