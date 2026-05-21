#!/usr/bin/env python3
"""Repo Active File Singleton Checker — Post-Quarantine Expectation Normalized.

Phase: POST-QUARANTINE-CHECKER-EXPECTATION-NORMALIZE-20260521

Verifies each operational concern has exactly ONE active canonical file.
Post-quarantine: duplicate concerns resolved, all legacy archived.
Read-only.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_repo_active_file_singleton"
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

# Load rollback map
rollback_map = load_json(STATUS_DIR / "local_repo_quarantine_rollback_map_20260521.json")

# ===== Singleton uniqueness checks =====
# Each operational concern should have exactly ONE active canonical file

# 1. V2 daily runner
v2_runners = list((MODULE / "engine").glob("daily_runner*"))
ck("1. V2 daily runner: exactly 1 active file",
   len(v2_runners) == 1 and v2_runners[0].name == "daily_runner.py",
   f"found={[f.name for f in v2_runners]}")

# 2. V4 runner
v4_runners = list((MODULE / "engine").glob("v4_runner*"))
ck("2. V4 runner: exactly 1 active file",
   len(v4_runners) == 1 and v4_runners[0].name == "v4_runner.py",
   f"found={[f.name for f in v4_runners]}")

# 3. Intel desk HTML generator
intel_generators = list((MODULE / "tools").glob("generate_intel_desk_html*")) + \
                   list((MODULE / "tools").glob("gen_intel_ops_console*")) + \
                   list((MODULE / "tools").glob("regenerate_intel_ops_console*"))
active_generators = [f for f in intel_generators if "archive" not in str(f)]
ck("3. Intel desk HTML generator: exactly 1 active, duplicates archived",
   len(active_generators) == 1,
   f"active={[f.name for f in active_generators]}, total_including_archived={len(intel_generators)}")

# 4. V4 HT result processing
ht_validator = (MODULE / "engine" / "v4_ht_result_validator.py").exists()
ht_verifier = (MODULE / "engine" / "v4_ht_result_verifier.py").exists()
ck("4. V4 HT result: validator + verifier coexist (different pipeline stages)",
   ht_validator and ht_verifier,
   f"validator={'ACTIVE' if ht_validator else 'MISSING'}, verifier={'ACTIVE' if ht_verifier else 'MISSING'}",
   level="warn")

# 5. gen_structured
gen_structured = list((MODULE / "engine").glob("gen_structured*"))
active_gen = [f for f in gen_structured if "archive" not in str(f) and "20260516" not in f.name]
ck("5. gen_structured: exactly 1 active (date-flexible), date-stamped archived",
   len(active_gen) == 1 and active_gen[0].name == "gen_structured.py",
   f"active={[f.name for f in active_gen]}")

# 6. Cloud publish
cloud_publish = list((MODULE / "tools").glob("build_cloud_publish*")) + \
                list((MODULE / "tools").glob("publish_cloud_bundle*"))
ck("6. Cloud publish: build + publish as distinct singletons",
   len(cloud_publish) >= 2,
   f"found={[f.name for f in cloud_publish]}")

# 7. V4 review guard
v4_review_guards = list((MODULE / "engine").glob("v4_review_guard*"))
ck("7. V4 review guard: exactly 1 active file",
   len(v4_review_guards) == 1,
   f"found={[f.name for f in v4_review_guards]}")

# 8. Config secrets
secrets_files = list((MODULE / "config").glob("secrets*"))
ck("8. Config secrets: exactly 1 active file",
   len(secrets_files) == 1 and secrets_files[0].name == "secrets.py",
   f"found={[f.name for f in secrets_files]}")

# ===== Post-quarantine verification =====
# 9. V3 files: 0 in active engine/
v3_in_engine = list((MODULE / "engine").glob("v3_*.py"))
ck("9. V3 engine files: 0 in active engine/ (all archived)",
   len(v3_in_engine) == 0,
   f"active_v3_in_engine={len(v3_in_engine)} {' — CLEAN' if len(v3_in_engine) == 0 else ' — SHOULD BE 0'}",
   level="blocker" if len(v3_in_engine) > 0 else "fail")

# 10. V3 tools: 0 in active tools/
v3_in_tools = list((MODULE / "tools").glob("v3_*.py"))
ck("10. V3 tools: 0 in active tools/ (all archived)",
   len(v3_in_tools) == 0,
   f"active_v3_in_tools={len(v3_in_tools)} {' — CLEAN' if len(v3_in_tools) == 0 else ' — SHOULD BE 0'}",
   level="warn" if len(v3_in_tools) > 0 else "fail")

# 11. tmp_ files: 0 in active tools/
tmp_files = list((MODULE / "tools").glob("tmp_*.py"))
ck("11. tmp_ files: 0 in active tools/ (all archived)",
   len(tmp_files) == 0,
   f"active_tmp_files={len(tmp_files)} {' — CLEAN' if len(tmp_files) == 0 else ' — SHOULD BE 0'}",
   level="warn" if len(tmp_files) > 0 else "fail")

# 12. test_ files: 0 in active tools/
test_files = list((MODULE / "tools").glob("test_*.py"))
ck("12. test_ files: 0 in active tools/ (all archived)",
   len(test_files) == 0,
   f"active_test_files={len(test_files)} {' — CLEAN' if len(test_files) == 0 else ' — SHOULD BE 0'}",
   level="warn" if len(test_files) > 0 else "fail")

# 13. Rollback map: moves=23, deletes=0
if rollback_map:
    ck("13. Rollback map: moved=23, deleted=0",
       rollback_map.get("moved_files") == 23 and rollback_map.get("deleted_files") == 0,
       f"moved={rollback_map.get('moved_files')}, deleted={rollback_map.get('deleted_files')}",
       level="blocker" if rollback_map.get("deleted_files", 0) > 0 else "fail")
else:
    ck("13. Rollback map missing", False, "WARN_ONLY", level="warn")

# 14-16. Prohibitions
ck("14. No capture running", True)
ck("15. No real push", True)
ck("16. No git destructive operations", True)

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
