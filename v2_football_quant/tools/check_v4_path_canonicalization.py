#!/usr/bin/env python3
"""
V4-D.1: Path Canonicalization Checker

Verifies that all V4 artifacts are in canonical paths:
- docs/checkers in v2_football_quant (not repo root)
- system-level artifacts remain in repo root
- All V4 checker entrypoints exist
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]  # v2_football_quant/
REPO_ROOT = MODULE_ROOT.parent                     # repo root

V4_CHECKERS_REQUIRED = [
    "check_v4_active_contamination.py",
    "check_v4_boundary_contract.py",
    "check_v4_lock_timeout_contract.py",
    "check_v4_no_push_enforcement.py",
    "check_v4_output_schema.py",
    "check_v4_path_canonicalization.py",
    "check_v4_qq_guard.py",
    "check_v4_renderer_guard.py",
    "check_v4_watchdog_contract.py",
]

# These root docs are ALLOWED system-level exceptions
ROOT_DOCS_EXCEPTIONS = [
    "SYSTEM_LEGACY_INVENTORY.md",
    "V4_FORMAL_FILE_WHITELIST.md",
]


def main():
    results = {
        "check_status": "PASS",
        "repo_root": str(REPO_ROOT),
        "module_root": str(MODULE_ROOT),
        "root_v4_docs_remaining": [],
        "root_v4_tools_remaining": [],
        "module_v4_docs_count": 0,
        "module_v4_tools_count": 0,
        "system_checker_exists": False,
        "v4_checker_entrypoints": [],
        "marker_output_path": str(MODULE_ROOT / "data/runtime/status/v4_path_canonicalization_check.json"),
        "production_verified": False,
        "phase_e_allowed": False,
        "blockers": [],
        "warnings": [],
    }

    block = False

    # 1. Check root docs/ for any V4_* files (excluding system exceptions)
    root_docs_dir = REPO_ROOT / "docs"
    if root_docs_dir.is_dir():
        for f in sorted(root_docs_dir.iterdir()):
            if f.is_file() and f.name.startswith("V4_"):
                if f.name not in ROOT_DOCS_EXCEPTIONS:
                    results["root_v4_docs_remaining"].append(f.name)
                    results["blockers"].append(f"V4 doc in root docs/: {f.name}")
                    block = True

    # 2. Check root tools/ for any check_v4_* files
    root_tools_dir = REPO_ROOT / "tools"
    if root_tools_dir.is_dir():
        for f in sorted(root_tools_dir.iterdir()):
            if f.is_file() and f.name.startswith("check_v4_"):
                results["root_v4_tools_remaining"].append(f.name)
                results["blockers"].append(f"V4 checker in root tools/: {f.name}")
                block = True

    # 3. Check system checker exists
    system_checker = root_tools_dir / "check_system_legacy_purge.py"
    results["system_checker_exists"] = system_checker.is_file()
    if not system_checker.is_file():
        results["blockers"].append("System legacy purge checker missing from root tools/")
        block = True

    # 4. Count module docs
    module_docs_dir = MODULE_ROOT / "docs"
    if module_docs_dir.is_dir():
        v4_docs = [f for f in module_docs_dir.iterdir() if f.is_file() and f.name.startswith("V4_")]
        results["module_v4_docs_count"] = len(v4_docs)

    # 5. Count module tools / check V4 checker entrypoints
    module_tools_dir = MODULE_ROOT / "tools"
    missing_checkers = []
    if module_tools_dir.is_dir():
        v4_checkers = sorted(module_tools_dir.glob("check_v4_*.py"))
        results["v4_checker_entrypoints"] = [str(c.relative_to(module_tools_dir)) for c in v4_checkers]
        results["module_v4_tools_count"] = len(v4_checkers)

        for chk in V4_CHECKERS_REQUIRED:
            if not (module_tools_dir / chk).is_file():
                missing_checkers.append(chk)

    if missing_checkers:
        results["blockers"].append(f"Missing V4 checkers in module tools/: {missing_checkers}")
        block = True

    # 6. Check production guard values
    if results["production_verified"]:
        results["blockers"].append("production_verified is true")
        block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true")
        block = True

    # Determine status
    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"
    else:
        results["check_status"] = "PASS"

    # Print
    print("=" * 60)
    print("V4 PATH CANONICALIZATION CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Repo root: {results['repo_root']}")
    print(f"Module root: {results['module_root']}")
    print(f"Root V4 docs remaining: {results['root_v4_docs_remaining']}")
    print(f"Root V4 tools remaining: {results['root_v4_tools_remaining']}")
    print(f"Module V4 docs count: {results['module_v4_docs_count']}")
    print(f"Module V4 tools count: {results['module_v4_tools_count']}")
    print(f"System checker exists: {results['system_checker_exists']}")
    print(f"V4 checker entrypoints: {len(results['v4_checker_entrypoints'])}")
    print(f"Production verified: {results['production_verified']}")
    print(f"Phase E allowed: {results['phase_e_allowed']}")

    if results["blockers"]:
        print(f"\nBLOCKERS ({len(results['blockers'])}):")
        for b in results["blockers"]:
            print(f"  ! {b}")
        sys.exit(1)
    elif results["warnings"]:
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for w in results["warnings"]:
            print(f"  ? {w}")

    # Write marker to module data (NOT committed)
    marker_path = MODULE_ROOT / "data" / "runtime" / "status" / "v4_path_canonicalization_check.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0 if results["check_status"] != "BLOCKER" else 1


if __name__ == "__main__":
    sys.exit(main())
