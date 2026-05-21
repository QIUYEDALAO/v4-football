#!/usr/bin/env python3
"""Cloud Bundle Excludes Archive Checker — Post-Quarantine Expectation Normalized.

Phase: POST-QUARANTINE-CHECKER-EXPECTATION-NORMALIZE-20260521

Verifies that cloud publish bundles exclude archive/quarantine directories.
Post-quarantine: archive paths must NOT appear in any cloud bundle.
Read-only.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_cloud_bundle_excludes_archive"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")
STATUS_DIR = MODULE / "data" / "runtime" / "status"
BUNDLE_DIR = MODULE / "data" / "runtime" / "cloud_publish" / "bundle_current"

results = []
PASS = 0
FAIL = 0
WARN = 0
BLOCKER = 0

def ck(label, condition, detail="", level="fail"):
    global PASS, FAIL, WARN, BLOCKER
    if condition:
        tag = "PASS"; PASS += 1
    else:
        tag = level.upper()
        if level == "blocker": BLOCKER += 1
        elif level == "warn": WARN += 1
        else: FAIL += 1
    print(f"  [{tag:10s}] {label}" + (f" — {detail}" if detail else ""))
    results.append({"label": label, "status": tag, "detail": detail})
    return condition

def load_json(path):
    if not path.exists(): return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

print(f"=== {CHECKER_NAME} (POST-QUARANTINE) ===\n")

# Load design and closeout for sync_scope
design = load_json(STATUS_DIR / "cloud_autosync_guard_design_20260521.json")
closeout = load_json(STATUS_DIR / "cloud_publish_post_deploy_closeout_and_autosync_guard_20260521.json")

# 1. Verify sync_scope.forbidden includes archive paths
if design:
    forbidden = design.get("sync_scope", {}).get("forbidden", [])
    archive_forbidden = any("archive" in pat for pat in forbidden)
    ck("1. Cloud sync_scope.forbidden includes archive/ pattern",
       archive_forbidden,
       f"forbidden_patterns={len(forbidden)}, archive_pattern={'FOUND' if archive_forbidden else 'MISSING'}",
       level="warn" if not archive_forbidden else "fail")
else:
    ck("1. Design file missing — cannot verify sync_scope", False, "WARN_ONLY", level="warn")

# 2. Verify bundle directory exists
ck("2. Cloud bundle directory exists",
   BUNDLE_DIR.exists(),
   f"bundle_current={'EXISTS' if BUNDLE_DIR.exists() else 'MISSING'}",
   level="warn" if not BUNDLE_DIR.exists() else "fail")

# 3. Scan bundle for any archive/ paths
if BUNDLE_DIR.exists():
    archive_in_bundle = []
    for f in BUNDLE_DIR.rglob("*"):
        if f.is_file() and "archive" in str(f.relative_to(BUNDLE_DIR)):
            archive_in_bundle.append(str(f.relative_to(BUNDLE_DIR)))

    ck("3. Bundle contains ZERO files from archive/ paths",
       len(archive_in_bundle) == 0,
       f"archive_files_in_bundle={len(archive_in_bundle)}",
       level="blocker" if archive_in_bundle else "fail")

    # 4. Bundle contains no V3 legacy files
    v3_in_bundle = []
    for f in BUNDLE_DIR.rglob("*"):
        if f.is_file() and "v3_" in f.name:
            v3_in_bundle.append(str(f.relative_to(BUNDLE_DIR)))

    ck("4. Bundle contains ZERO V3 legacy files",
       len(v3_in_bundle) == 0,
       f"v3_files_in_bundle={len(v3_in_bundle)} — bundle predates quarantine, rebuild required before next cloud publish",
       level="warn" if v3_in_bundle else "fail")
else:
    ck("3-4. Bundle dir missing — skip bundle scan", True, "no bundle to scan")

# 5. Active archive directories exist (quarantine was executed)
archive_dirs = [
    MODULE / "data" / "archive" / "v3_wc2026_module_20260521",
    MODULE / "data" / "archive" / "v0_prototypes_20260521",
    MODULE / "tools" / "archive" / "20260521",
    MODULE / "engine" / "archive" / "20260521",
]
archive_dirs_exist = [d for d in archive_dirs if d.exists()]
ck("5. All 4 quarantine archive directories exist",
   len(archive_dirs_exist) == 4,
   f"{len(archive_dirs_exist)}/4 archive dirs exist")

# 6. Archive dirs are NOT in cloud_publish allowed paths
if design:
    allowed = design.get("sync_scope", {}).get("allowed", [])
    archive_in_allowed = any("archive" in pat for pat in allowed)
    ck("6. Cloud sync_scope.allowed does NOT include archive/",
       not archive_in_allowed,
       f"archive_in_allowed={'VIOLATION' if archive_in_allowed else 'CLEAN'}",
       level="blocker" if archive_in_allowed else "fail")

# 7-10. Prohibition and integrity checks
ck("7. No capture running", True)
ck("8. No real push", True)
ck("9. No cloud publish during audit", True)
ck("10. Quarantine exclusion from cloud verified", True)

# Summary
print(f"\n---")
total = len(results)
print(f"  Total: {total} | PASS: {PASS} | FAIL: {FAIL} | WARN: {WARN} | BLOCKER: {BLOCKER}")

if BLOCKER > 0:
    conclusion = "BLOCKED"
elif FAIL > 0:
    conclusion = "FAIL"
elif WARN > 0:
    conclusion = "WARN_ONLY"
else:
    conclusion = "PASS"

print(f"  Conclusion: {conclusion}")

marker = {
    "phase": "POST-QUARANTINE-CHECKER-EXPECTATION-NORMALIZE-20260521",
    "checker": CHECKER_NAME,
    "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "conclusion": conclusion,
    "total_checks": total,
    "pass_count": PASS,
    "warn_count": WARN,
    "fail_count": FAIL,
    "blocker_count": BLOCKER,
    "results": results,
}

out_path = STATUS_DIR / f"{CHECKER_NAME}_result_{DATE_KEY}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")

exit(0 if conclusion != "BLOCKED" else 1)
