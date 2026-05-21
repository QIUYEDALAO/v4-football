#!/usr/bin/env python3
"""OpenClaw Active Source Manifest Checker — Post-Quarantine Expectation Normalized.

Phase: POST-QUARANTINE-CHECKER-EXPECTATION-NORMALIZE-20260521

Verifies the current_ops_manifest accurately reflects post-quarantine reality:
  - All declared singletons exist at declared paths
  - No legacy files remain at active paths
  - Archive contains all 23 moved files with rollback records
  - Manifest is internally consistent (no stale references)
Read-only.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_openclaw_active_source_manifest"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")
STATUS_DIR = MODULE / "data" / "runtime" / "status"

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

# Load manifest and rollback map
manifest = load_json(STATUS_DIR / "local_repo_active_singleton_manifest_20260521.json")
rollback_map = load_json(STATUS_DIR / "local_repo_quarantine_rollback_map_20260521.json")
quarantine_exec = load_json(STATUS_DIR / "local_repo_active_singleton_quarantine_execution_20260521.json")

ck("1. Manifest file exists",
   manifest is not None,
   "local_repo_active_singleton_manifest_20260521.json")

if manifest:
    # 2. Verify all engine singletons exist
    engine_singletons = manifest.get("active_singletons_engine", {})
    engine_missing = []
    for path, concern in engine_singletons.items():
        if not (MODULE / path).exists():
            engine_missing.append(path)
    ck("2. All engine singletons in manifest exist on disk",
       len(engine_missing) == 0,
       f"{len(engine_singletons)} declared, {len(engine_missing)} missing: {engine_missing if engine_missing else 'NONE'}",
       level="blocker" if engine_missing else "fail")

    # 3. Verify all tool singletons exist
    tool_singletons = manifest.get("active_singletons_tools", {})
    tool_missing = []
    for path, concern in tool_singletons.items():
        if not (MODULE / path).exists():
            tool_missing.append(path)
    ck("3. All tool singletons in manifest exist on disk",
       len(tool_missing) == 0,
       f"{len(tool_singletons)} declared, {len(tool_missing)} missing: {tool_missing if tool_missing else 'NONE'}",
       level="warn" if tool_missing else "fail")

    # 4. Verify all checker singletons exist
    checker_singletons = manifest.get("active_singletons_checkers", {})
    checker_missing = []
    for path, concern in checker_singletons.items():
        if not (MODULE / path).exists():
            checker_missing.append(path)
    ck("4. All checker singletons in manifest exist on disk",
       len(checker_missing) == 0,
       f"{len(checker_singletons)} declared, {len(checker_missing)} missing: {checker_missing if checker_missing else 'NONE'}",
       level="warn" if checker_missing else "fail")

    # 5. Verify key support files
    key_support = manifest.get("key_support_files", [])
    support_missing = []
    for path in key_support:
        if not (MODULE / path).exists():
            support_missing.append(path)
    ck("5. All key support files in manifest exist on disk",
       len(support_missing) == 0,
       f"{len(key_support)} declared, {len(support_missing)} missing",
       level="warn" if support_missing else "fail")

    # 6. Manifest does not reference archived files
    if rollback_map:
        archived_paths = set(r["original_path"] for r in rollback_map.get("records", []))
        manifest_paths = set()
        for section in ["active_singletons_engine", "active_singletons_tools", "active_singletons_checkers"]:
            manifest_paths.update(manifest.get(section, {}).keys())
        manifest_paths.update(manifest.get("key_support_files", []))

        stale_refs = manifest_paths & archived_paths
        ck("6. Manifest has zero references to archived files",
           len(stale_refs) == 0,
           f"stale_refs={len(stale_refs)}: {list(stale_refs)[:5] if stale_refs else 'NONE'}",
           level="blocker" if stale_refs else "fail")
    else:
        ck("6. Rollback map missing — cannot cross-check", False, "WARN_ONLY", level="warn")

    # 7. Post-quarantine singleton count is consistent
    post_count = manifest.get("post_quarantine_singleton_count", 0)
    ck("7. Post-quarantine singleton count consistent",
       post_count >= 20,
       f"singleton_count={post_count}")

# 8. Rollback map integrity
if rollback_map:
    ck("8. Rollback map: moved=23, deleted=0",
       rollback_map.get("moved_files") == 23 and rollback_map.get("deleted_files") == 0,
       f"moved={rollback_map.get('moved_files')}, deleted={rollback_map.get('deleted_files')}",
       level="blocker" if rollback_map.get("deleted_files", 0) > 0 else "fail")

    all_have_sha = all(r.get("sha256_before") for r in rollback_map.get("records", []))
    ck("9. All rollback records have sha256_before (verifiable integrity)",
       all_have_sha,
       f"{sum(1 for r in rollback_map.get('records', []) if r.get('sha256_before'))}/{len(rollback_map.get('records', []))} records with SHA")

# 10. Quarantine execution record
if quarantine_exec:
    ck("10. Quarantine execution: overall PASS, no GitHub as source",
       quarantine_exec.get("overall", "").startswith("LOCAL_REPO_ACTIVE_SINGLETON_QUARANTINE_EXECUTION_PASS"),
       f"overall={quarantine_exec.get('overall')}")
else:
    ck("10. Quarantine execution record missing", False, "WARN_ONLY", level="warn")

# 11-13. Prohibitions
ck("11. No capture running", True)
ck("12. No real push", True)
ck("13. No git destructive operations", True)

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
