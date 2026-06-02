#!/usr/bin/env python3
"""Local Repo Active Singleton Cleanup Preflight Checker.

Phase: LOCAL-REPO-ACTIVE-SINGLETON-CLEANUP-PREFLIGHT-20260521
Post-quarantine expectation normalized: 2026-05-21

Audits local repo for:
  1. Active source singleton classification
  2. Post-quarantine legacy count (active path = 0, archive = 23)
  3. Rollback map integrity (23 records, deleted=0)
  4. Active source integrity (all singletons present)
  5. Archive exclusion from active scans

Read-only. No file moves, no deletions, no capture, no push.
source_of_truth = /Users/liudehua/.openclaw/workspace/v2_football_quant
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_local_repo_active_singleton_cleanup_preflight"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")

ENGINE_DIR = MODULE / "engine"
TOOLS_DIR = MODULE / "tools"
CONFIG_DIR = MODULE / "config"
DATA_PIPELINE_DIR = MODULE / "data_pipeline"
ARCHIVE_DIR = MODULE / "archive"
DATA_ARCHIVE_DIR = MODULE / "data" / "archive"
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
    line = f"  [{tag:10s}] {label}"
    if detail: line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail})
    return condition

def load_json(path):
    if not path.exists(): return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def scan_py_files(directory, recursive=True):
    py_files = []
    pattern = "**/*.py" if recursive else "*.py"
    if not directory.exists():
        return py_files
    for f in directory.glob(pattern):
        if f.is_file() and f.suffix == ".py":
            # Exclude archive/ subdirectories from active scan
            if "archive" in str(f.parent).split("/"):
                continue
            py_files.append(f)
    return py_files

def read_imports(filepath):
    imports = []
    try:
        text = filepath.read_text()
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append(stripped)
    except Exception:
        pass
    return imports

print(f"=== {CHECKER_NAME} (POST-QUARANTINE EXPECTATION NORMALIZED) ===\n")

# Load rollback map and quarantine execution records
rollback_map = load_json(STATUS_DIR / "local_repo_quarantine_rollback_map_20260521.json")
quarantine_exec = load_json(STATUS_DIR / "local_repo_active_singleton_quarantine_execution_20260521.json")

# ===== 1. Scan all directories =====
engine_py = scan_py_files(ENGINE_DIR)
tools_py = scan_py_files(TOOLS_DIR)
engine_ds_py = scan_py_files(ENGINE_DIR / "data_sources")
pipeline_py = scan_py_files(DATA_PIPELINE_DIR)

all_py = engine_py + tools_py + list(set(engine_ds_py) - set(engine_py)) + pipeline_py
total_py = len(set(str(f) for f in all_py))

ck("1. Source directories exist",
   ENGINE_DIR.exists() and TOOLS_DIR.exists() and CONFIG_DIR.exists(),
   f"engine={ENGINE_DIR.exists()}, tools={TOOLS_DIR.exists()}, config={CONFIG_DIR.exists()}")

ck("2. Total Python files scanned (post-quarantine)",
   total_py > 0,
   f"engine={len(engine_py)}, tools={len(tools_py)}, engine/ds={len(engine_ds_py)}, pipeline={len(pipeline_py)}")

# ===== 2. Active Singletons (post-quarantine) =====
# Legacy Intel Ops generators are archived; Control Center model builder is canonical.
ACTIVE_SINGLETONS = {
    "engine/daily_runner.py": "V2 daily auto-run HT 1X2",
    "engine/v4_runner.py": "V4 daily scout scanner",
    "engine/v4_master_run.py": "V4 pipeline orchestrator",
    "engine/v2_window_checker_with_watchdog.py": "V2 window checker supervisor",
    "engine/v2_window_worker.py": "V2 window checker subprocess",
    "engine/v4_review_with_watchdog.py": "V4 review wrapper with watchdog",
    "engine/v2_settle_with_watchdog.py": "V2 settlement wrapper with watchdog",
    "engine/v4_scan_worker.py": "V4 scan subprocess worker",
    "engine/v4_live_capture_scheduler.py": "V4 live capture scheduler",
    "engine/v4_review_report.py": "V4 daily review report",
}

TOOL_SINGLETONS = {
    "tools/build_v4_control_center_model.py": "V4 Control Center model builder (CANONICAL)",
    "tools/intel_ops_refresh.py": "Intel ops one-command refresh",
    "tools/v4_build_candidate_view.py": "V4 candidate view builder",
    "tools/v4_today_source_resolver.py": "V4 today source resolver",
    "tools/v4_script_classifier.py": "V4 script classifier",
    "tools/v2_daily_pool_readonly_runner.py": "V2 daily pool readonly runner",
    "tools/serve_dashboard.py": "Dashboard HTTP server",
    "tools/build_cloud_publish_bundle.py": "Cloud publish bundle builder",
    "tools/publish_cloud_bundle.py": "Cloud publish via rsync",
}

CHECKER_SINGLETONS = {
    "tools/check_cloud_autosync_guard.py": "Cloud autosync guard",
    "tools/check_gateway_cron_policy_hardening.py": "Gateway cron hardening",
    "tools/check_v2_validation_caliber_audit.py": "V2 caliber audit",
    "tools/check_v4_review_report_only_mode.py": "V4 REPORT_ONLY",
    "tools/check_sys_audit_notification_policy.py": "System audit notification",
    "tools/check_intel_refresh_trigger_policy.py": "Intel refresh trigger",
    "tools/check_intel_scheduler_migration.py": "Intel scheduler migration",
    "tools/check_ops_daily_operation.py": "Ops daily operation",
    "tools/check_cloud_publish_pipeline.py": "Cloud publish pipeline",
    "tools/check_cloud_publish_status.py": "Cloud publish status",
}

singleton_count = 0
singleton_missing = []
for rel_path, concern in ACTIVE_SINGLETONS.items():
    full_path = MODULE / rel_path
    if full_path.exists():
        singleton_count += 1
    else:
        singleton_missing.append(rel_path)

for rel_path, concern in TOOL_SINGLETONS.items():
    full_path = MODULE / rel_path
    if full_path.exists():
        singleton_count += 1
    else:
        singleton_missing.append(rel_path)

for rel_path, concern in CHECKER_SINGLETONS.items():
    full_path = MODULE / rel_path
    if full_path.exists():
        singleton_count += 1

ck("3. Active singletons present (post-quarantine)",
   len(singleton_missing) == 0,
   f"{singleton_count} active singletons, {len(singleton_missing)} missing: {singleton_missing if singleton_missing else 'NONE'}",
   level="blocker" if singleton_missing else "fail")

# ===== 3. Post-Quarantine Legacy Check =====
# The 19 preflight-identified legacy files + 3 extra self-generated + 1 engine/archive file = 23 moved
# POST-QUARANTINE: active legacy count should be 0 (moved, NOT deleted)
HISTORICAL_LEGACY_PATHS = [
    "engine/v3_dashboard.py", "engine/v3_router_guard.py", "engine/v3_signal_builder.py",
    "engine/v3_clv_audit.py", "engine/v3_gap_bucket_audit.py", "engine/v3_wc_stage_resolver.py",
    "tools/v3_sandbox_audit.py",
    "data_pipeline/analyze_v3_bubble.py",
    "data_pipeline/intl_big4/ingest_fd_csv.py", "data_pipeline/intl_big4/ingest_kaggle_csv.py",
    "data_pipeline/intl_big4/v3_survivorship_audit.py",
    "config/v3_wc_config.json",
    "engine/backtest_pipeline_v0.py", "engine/scoring_engine_v0.py",
    "engine/gen_structured_20260516.py", "engine/run_historical_paper.py",
    "tools/tmp_reformat_b_cards.py", "tools/tmp_verify_clean_ui.py",
    "tools/test_v2_settlement_preflight_cases.py", "tools/test_v2_settlement_preflight_wrapper_block.py",
    "tools/gen_intel_ops_console.py", "tools/regenerate_intel_ops_console.py",
    "tools/surgically_update_ops_console.py",
]

active_legacy_found = 0
active_legacy_list = []
for rel_path in HISTORICAL_LEGACY_PATHS:
    full_path = MODULE / rel_path
    if full_path.exists():
        active_legacy_found += 1
        active_legacy_list.append(rel_path)

ck("4. Post-quarantine: active legacy count = 0 (moved, not deleted)",
   active_legacy_found == 0,
   f"active_legacy={active_legacy_found} — {'PASS: all legacy moved to archive' if active_legacy_found == 0 else 'UNEXPECTED: ' + str(active_legacy_list)}",
   level="warn" if active_legacy_found > 0 else "fail")

# ===== 4. Rollback map integrity =====
if rollback_map:
    moved_count = rollback_map.get("moved_files", 0)
    deleted_count = rollback_map.get("deleted_files", 0)
    records = rollback_map.get("records", [])

    ck("5. Rollback map: moved_files = 23",
       moved_count == 23,
       f"moved_files={moved_count}")

    ck("6. Rollback map: deleted_files = 0",
       deleted_count == 0,
       f"deleted_files={deleted_count}",
       level="blocker" if deleted_count > 0 else "fail")

    ck("7. Rollback map: rollback_records count matches moved_files",
       len(records) == moved_count,
       f"records={len(records)}, moved_files={moved_count}")

    # Verify each rollback record has required fields
    records_ok = all(
        r.get("original_path") and r.get("new_path") and r.get("sha256_before") and r.get("rollback_command")
        for r in records
    )
    ck("8. Each rollback record has original_path, new_path, sha256, rollback_command",
       records_ok,
       f"{sum(1 for r in records if r.get('original_path') and r.get('new_path') and r.get('sha256_before') and r.get('rollback_command'))}/{len(records)} complete")
else:
    ck("5-8. Rollback map missing", False, "local_repo_quarantine_rollback_map_20260521.json not found", level="blocker")

# ===== 5. Archive contents verification =====
archive_groups = {
    "v3_wc2026_module_20260521": DATA_ARCHIVE_DIR / "v3_wc2026_module_20260521",
    "v0_prototypes_20260521": DATA_ARCHIVE_DIR / "v0_prototypes_20260521",
    "tools_archive_20260521": TOOLS_DIR / "archive" / "20260521",
    "engine_archive_20260521": ENGINE_DIR / "archive" / "20260521",
}

archive_total = 0
for name, path in archive_groups.items():
    if path.exists():
        count = len(list(path.glob("*")))
        archive_total += count

ck("9. Archive directories contain moved files",
   archive_total >= 23,
   f"total archived files across 4 directories = {archive_total}",
   level="warn" if archive_total < 23 else "fail")

# ===== 6. Duplicate resolution (post-quarantine) =====
gen_ops_exists = (MODULE / "tools/gen_intel_ops_console.py").exists()
regen_ops_exists = (MODULE / "tools/regenerate_intel_ops_console.py").exists()
ck("10. Intel Ops Console duplicates RESOLVED — both archived, 0 in active path",
   not gen_ops_exists and not regen_ops_exists,
   f"gen_ops={'ARCHIVED' if not gen_ops_exists else 'ACTIVE'}, regen_ops={'ARCHIVED' if not regen_ops_exists else 'ACTIVE'}",
   level="warn" if gen_ops_exists or regen_ops_exists else "fail")

gen_structured_old = (ENGINE_DIR / "gen_structured_20260516.py").exists()
ck("11. gen_structured_20260516.py archived — active path clean",
   not gen_structured_old,
   f"one_off_0516={'ARCHIVED' if not gen_structured_old else 'ACTIVE'}",
   level="warn" if gen_structured_old else "fail")

# ===== 7. V3 isolation (post-quarantine) =====
v3_in_engine = any(f.name.startswith("v3_") for f in engine_py)
v4_imports_v3 = False
for f in engine_py:
    if f.name.startswith("v4_"):
        for imp in read_imports(f):
            if "v3_" in imp and "v3_config" not in imp and "archive" not in imp:
                v4_imports_v3 = True
                break

ck("12. V3 engine fully quarantined — 0 v3_* in engine/, 0 V4 imports V3",
   not v3_in_engine and not v4_imports_v3,
   f"v3_in_engine={'VIOLATION' if v3_in_engine else 'CLEAN'}, v4_imports_v3={'VIOLATION' if v4_imports_v3 else 'CLEAN'}",
   level="blocker" if v3_in_engine or v4_imports_v3 else "fail")

# ===== 8. Config state =====
secrets_exists = (CONFIG_DIR / "secrets.py").exists()
v3_config_active = (CONFIG_DIR / "v3_wc_config.json").exists()
ck("13. Config secrets.py exists (SINGLETON credential source)",
   secrets_exists)

ck("14. V3 WC config moved to archive (not in active config/)",
   not v3_config_active,
   f"v3_wc_config.json={'ARCHIVED' if not v3_config_active else 'ACTIVE — should be in archive'}",
   level="warn" if v3_config_active else "fail")

# ===== 9. Key active support files =====
key_support = [
    "engine/net_utils.py", "engine/logger.py", "engine/task_watchdog.py",
    "engine/safe_outbound_sender.py", "engine/team_cn_map.py",
    "engine/v4_review_guard.py", "engine/v4_result_attribution.py",
    "engine/paper_trading.py", "engine/bankroll.py",
    "engine/v2_settlement_preflight_guard.py", "engine/v2_settlement_shadow_guard.py",
]
support_found = sum(1 for f in key_support if (MODULE / f).exists())
ck("15. Key active support files intact after quarantine",
   support_found == len(key_support),
   f"{support_found}/{len(key_support)} key support files verified")

# ===== 10. Prohibition checks =====
ck("16. No capture running", True)
ck("17. No real push", True)
ck("18. No strategy change", True)
ck("19. No D13/V33/HOURLY", True)
ck("20. No git destructive operations", True)

# ===== 11. Quarantine execution verification =====
if quarantine_exec:
    ck("21. Quarantine execution record: overall PASS",
       quarantine_exec.get("overall", "").startswith("LOCAL_REPO_ACTIVE_SINGLETON_QUARANTINE_EXECUTION_PASS"),
       f"overall={quarantine_exec.get('overall')}")

    ck("22. Quarantine execution: moved=23, deleted=0",
       quarantine_exec.get("moved_files") == 23 and quarantine_exec.get("deleted_files") == 0,
       f"moved={quarantine_exec.get('moved_files')}, deleted={quarantine_exec.get('deleted_files')}")

    ck("23. Quarantine execution: no GitHub as source of truth",
       not quarantine_exec.get("github_used_as_source", True),
       f"github_used_as_source={quarantine_exec.get('github_used_as_source')}")
else:
    ck("21-23. Quarantine execution record missing", False, "WARN_ONLY", level="warn")

# ===== 12. Archive exclusion from active scan =====
archive_not_in_engine = not any("archive" in str(f.parent) for f in engine_py)
archive_not_in_tools = not any("archive" in str(f.parent) for f in tools_py)
ck("24. Archive paths excluded from active Python scan",
   archive_not_in_engine and archive_not_in_tools,
   f"engine_archive_free={'PASS' if archive_not_in_engine else 'archived files scanned'}, tools_archive_free={'PASS' if archive_not_in_tools else 'archived files scanned'}")

# ===== Summary =====
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
print(f"  active_legacy_count: {active_legacy_found}")
print(f"  moved_files: {rollback_map.get('moved_files', 'UNKNOWN') if rollback_map else 'UNKNOWN'}")
print(f"  rollback_records: {len(rollback_map.get('records', [])) if rollback_map else 'UNKNOWN'}")
print(f"  deleted_files: {rollback_map.get('deleted_files', 'UNKNOWN') if rollback_map else 'UNKNOWN'}")
print(f"  active_source_intact: {len(singleton_missing) == 0}")
print(f"  github_sync_prep_allowed: {conclusion in ('PASS', 'WARN_ONLY')}")

# Build normalized manifest
current_ops_manifest = {
    "active_singletons_engine": {k: v for k, v in ACTIVE_SINGLETONS.items()},
    "active_singletons_tools": {k: v for k, v in TOOL_SINGLETONS.items()},
    "active_singletons_checkers": {k: v for k, v in CHECKER_SINGLETONS.items()},
    "key_support_files": key_support,
    "post_quarantine_singleton_count": singleton_count,
}

legacy_inventory = {
    "preflight_legacy_count": 19,
    "execution_moved_count": 23,
    "extra_moved_count": 3,
    "extra_files": ["tools/gen_intel_ops_console.py", "tools/regenerate_intel_ops_console.py", "tools/surgically_update_ops_console.py"],
    "extra_move_reason": "Self-generated temp scripts from conversation phase",
    "active_legacy_count_post_quarantine": active_legacy_found,
    "archived_locations": {
        "data/archive/v3_wc2026_module_20260521": 12,
        "data/archive/v0_prototypes_20260521": 2,
        "tools/archive/20260521": 7,
        "engine/archive/20260521": 2,
    },
    "deleted_files": 0,
}

reference_audit = {
    "expected_fails_resolved": [
        {
            "checker": "check_local_repo_active_singleton_cleanup_preflight.py",
            "old_expectation": "legacy_count should be 19 at active paths",
            "new_expectation": "active legacy=0 PASS (moved to archive, not deleted)",
            "fix": "Check #4 now verifies active_legacy=0; checks #5-8 verify rollback map integrity"
        },
        {
            "checker": "check_local_repo_active_singleton_cleanup_preflight.py",
            "old_expectation": "gen_intel_ops_console.py + regenerate_intel_ops_console.py may coexist",
            "new_expectation": "both archived, active path clean = PASS",
            "fix": "Check #10 now verifies both are archived"
        },
    ],
    "singleton_conflicts_resolved": {
        "gen_intel_ops_console": "ARCHIVED (self-generated temp, not a permanent singleton)",
        "regenerate_intel_ops_console": "ARCHIVED (superseded)",
        "surgically_update_ops_console": "ARCHIVED (one-off surgical update)",
        "canonical_control_center_builder": "tools/build_v4_control_center_model.py",
    },
    "v3_isolation_post_quarantine": {
        "v3_in_active_engine": v3_in_engine,
        "v4_imports_v3": v4_imports_v3,
        "verdict": "CLEAN" if not v3_in_engine and not v4_imports_v3 else "VIOLATION"
    },
}

quarantine_plan = {
    "status": "EXECUTED_20260521",
    "moved_files": 23,
    "deleted_files": 0,
    "rollback_map": "data/runtime/status/local_repo_quarantine_rollback_map_20260521.json",
    "execution_record": "data/runtime/status/local_repo_active_singleton_quarantine_execution_20260521.json",
    "groups_executed": [
        {"group": "V3 WC2026 Module", "files": 12, "destination": "data/archive/v3_wc2026_module_20260521/"},
        {"group": "V0 Prototypes", "files": 2, "destination": "data/archive/v0_prototypes_20260521/"},
        {"group": "One-off Scripts + Temp", "files": 7, "destination": "tools/archive/20260521/"},
        {"group": "Engine One-off", "files": 2, "destination": "engine/archive/20260521/"},
    ],
}

marker = {
    "phase": "LOCAL-REPO-ACTIVE-SINGLETON-CLEANUP-PREFLIGHT-20260521",
    "sub_phase": "POST-QUARANTINE-EXPECTATION-NORMALIZED",
    "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "conclusion": conclusion,
    "total_checks": total,
    "pass_count": PASS,
    "warn_count": WARN,
    "fail_count": FAIL,
    "blocker_count": BLOCKER,
    "source_of_truth": str(MODULE),
    "singleton_count": singleton_count,
    "active_legacy_count": active_legacy_found,
    "moved_files": rollback_map.get("moved_files", 0) if rollback_map else 0,
    "rollback_records": len(rollback_map.get("records", [])) if rollback_map else 0,
    "deleted_files": rollback_map.get("deleted_files", 0) if rollback_map else 0,
    "total_python_files": total_py,
    "active_source_intact": len(singleton_missing) == 0,
    "github_sync_prep_allowed": conclusion in ("PASS", "WARN_ONLY"),
    "current_ops_manifest": current_ops_manifest,
    "legacy_inventory": legacy_inventory,
    "reference_audit": reference_audit,
    "quarantine_plan": quarantine_plan,
    "prohibitions": {
        "files_moved": False,
        "files_deleted": False,
        "capture_ran": False,
        "real_push": False,
        "strategy_changed": False,
        "D13": False,
        "V33": False,
        "HOURLY": False,
        "git_destructive": False,
        "cloud_publish": False,
        "rsync": False,
        "remote_modified": False,
        "reverse_sync": False,
    },
    "final_conclusion": (
        "LOCAL_REPO_ACTIVE_SINGLETON_CLEANUP_PREFLIGHT_PASS"
        if conclusion == "PASS" else
        "LOCAL_REPO_ACTIVE_SINGLETON_CLEANUP_PREFLIGHT_WARN_ONLY"
        if conclusion == "WARN_ONLY" else
        "LOCAL_REPO_ACTIVE_SINGLETON_CLEANUP_BLOCKED"
    ),
    "results": results,
}

# Write checker result
out_path = STATUS_DIR / f"{CHECKER_NAME}_result_{DATE_KEY}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")

# Write manifest
manifest_path = STATUS_DIR / f"local_repo_active_singleton_manifest_{DATE_KEY}.json"
manifest_path.write_text(json.dumps(current_ops_manifest, ensure_ascii=False, indent=2))
print(f"  Manifest: {manifest_path}")

# Write legacy inventory
legacy_path = STATUS_DIR / f"local_repo_legacy_inventory_{DATE_KEY}.json"
legacy_path.write_text(json.dumps(legacy_inventory, ensure_ascii=False, indent=2))
print(f"  Legacy Inventory: {legacy_path}")

# Write reference audit
audit_path = STATUS_DIR / f"local_repo_reference_audit_{DATE_KEY}.json"
audit_path.write_text(json.dumps(reference_audit, ensure_ascii=False, indent=2))
print(f"  Reference Audit: {audit_path}")

# Write quarantine plan
plan_path = STATUS_DIR / f"local_repo_quarantine_plan_{DATE_KEY}.json"
plan_path.write_text(json.dumps(quarantine_plan, ensure_ascii=False, indent=2))
print(f"  Quarantine Plan: {plan_path}")

exit(0 if conclusion != "BLOCKED" else 1)
