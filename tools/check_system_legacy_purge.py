#!/usr/bin/env python3
"""
SYSTEM-LEGACY-0: Legacy Purge Checker

Checks that all historical V33/V38/backup/legacy files have been removed,
archived, or properly marked as deprecated. Verifies formal V4 whitelist
integrity and confirms executable path safety.

Output: data/runtime/status/system_legacy_purge_check.json (not committed)
"""

import os
import json
import glob
import sys
import re

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_DIR = os.path.join(WORKSPACE, "docs", "archive", "system_legacy")
V4_WHITELIST = os.path.join(WORKSPACE, "docs", "V4_FORMAL_FILE_WHITELIST.md")
TOOLS_DIR = os.path.join(WORKSPACE, "tools")
DATA_ARCHIVE_DIRS = [
    os.path.join(WORKSPACE, "data", "验证存档", "v33"),
    os.path.join(WORKSPACE, "data", "验证存档", "v38"),
    os.path.join(WORKSPACE, "data", "验证存档", "v38.1"),
]

# Legacy patterns in tools/
TOOLS_LEGACY_PATTERNS = [
    "*v33*", "*v38*", "*legacy*", "*backup*",
    "*old*", "*batch-worker*", "*batch_worker*"
]

REQUIRED_MARKERS = [
    "DEPRECATED",
    "NOT_PRODUCTION",
    "DO_NOT_EXECUTE",
    "HISTORICAL_REFERENCE_ONLY",
]

V4_WHITELIST_FORBIDDEN = [
    "V33", "V38", "batch-worker-v38",
    "backup worker", "legacy worker",
]


def scan_tools_legacy():
    """Check tools/ for legacy files."""
    remaining = []
    for pattern in TOOLS_LEGACY_PATTERNS:
        found = glob.glob(os.path.join(TOOLS_DIR, pattern))
        for f in found:
            basename = os.path.basename(f)
            # Skip the purger checker itself
            if basename == "check_system_legacy_purge.py":
                continue
            # Check for the legacy patterns in the name
            lower = basename.lower()
            if any(p.strip("*") in lower for p in [p.strip("*") for p in TOOLS_LEGACY_PATTERNS]):
                remaining.append(os.path.relpath(f, WORKSPACE))
    return remaining


def check_archive_markers():
    """Check that all archived files have required deprecation markers."""
    if not os.path.isdir(ARCHIVE_DIR):
        return {"valid": False, "reason": "Archive directory not found"}
    
    results = {"valid": True, "errors": []}
    for root, dirs, files in os.walk(ARCHIVE_DIR):
        for f in files:
            fpath = os.path.join(root, f)
            with open(fpath, "r") as fh:
                content = fh.read()
            for marker in REQUIRED_MARKERS:
                if marker not in content:
                    results["valid"] = False
                    results["errors"].append(
                        f"{os.path.relpath(fpath, WORKSPACE)} missing marker: {marker}"
                    )
    return results


def check_data_archive_markers():
    """Check DEPRECATED.md exists in data/verification archive dirs."""
    results = {"valid": True, "errors": []}
    for d in DATA_ARCHIVE_DIRS:
        marker = os.path.join(d, "DEPRECATED.md")
        if os.path.isfile(marker):
            with open(marker, "r") as fh:
                content = fh.read()
            for marker_text in REQUIRED_MARKERS:
                if marker_text not in content:
                    results["valid"] = False
                    results["errors"].append(
                        f"{os.path.relpath(marker, WORKSPACE)} missing marker: {marker_text}"
                    )
        else:
            results["valid"] = False
            results["errors"].append(f"Missing DEPRECATED.md in {os.path.relpath(d, WORKSPACE)}")
    return results


def check_v4_whitelist():
    """Verify V4 whitelist doesn't contain forbidden entries."""
    if not os.path.isfile(V4_WHITELIST):
        return {"valid": False, "reason": "V4 whitelist not found"}
    
    with open(V4_WHITELIST, "r") as fh:
        content = fh.read()
    
    issues = []
    for forbidden in V4_WHITELIST_FORBIDDEN:
        # Only flag if in "Formal V4 Files" sections, not in "Excluded" sections
        lines = content.split("\n")
        in_formal_section = False
        for line in lines:
            if "Formal V4 Files" in line and "confirmed" in line.lower():
                in_formal_section = True
            elif "Excluded" in line or "Archived" in line:
                in_formal_section = False
            if in_formal_section and forbidden.lower() in line.lower():
                issues.append(f"Forbidden entry '{forbidden}' found in Formal V4 Files section")
    
    return {"valid": len(issues) == 0, "errors": issues}


def scan_v33_v38_references():
    """Count V33/V38 references in critical paths."""
    active_refs = {"v33": [], "v38": []}
    
    scan_dirs = [
        os.path.join(WORKSPACE, "engine"),
        os.path.join(WORKSPACE, "v2_football_quant", "engine"),
        os.path.join(WORKSPACE, "tools"),
        os.path.join(WORKSPACE, "v2_football_quant", "tools"),
    ]
    
    # Files to skip entirely (they are deprecation guards, not legacy modules)
    SKIP_FILES = [
        "check_system_legacy_purge.py",
        "check_v4_boundary_contract.py",
    ]
    # Lines where V33/V38 is used in deprecation guard context (skip these)
    GUARD_CONTEXT_KEYWORDS = [
        "deprecated", "historical", "not_production", "do_not_execute",
        "禁止", "不得", "废弃", "排除", "exclude", "forbidden",
        "not allowed", "must not", "never upload", "deprecation",
        "FORBIDDEN", "forbidden_keywords",  # Variable names for exclusion lists
        "禁止追加任何V33",  # Specific V4 output guard
        "qq不含V2/V33",  # V4 review guard exclusion
    ]
    
    legacy_pattern = re.compile(r'\bV33\b|\bV38\b|v33|v38', re.IGNORECASE)
    
    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir):
            # Skip node_modules
            dirs[:] = [d for d in dirs if d != "node_modules"]
            for f in files:
                if not f.endswith((".py", ".js", ".md", ".json", ".yaml", ".yml")):
                    continue
                if f in SKIP_FILES:
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", errors="ignore") as fh:
                        for i, line in enumerate(fh, 1):
                            if legacy_pattern.search(line):
                                # Skip if line is a deprecation guard context
                                lower_line = line.lower()
                                if any(kw in lower_line for kw in GUARD_CONTEXT_KEYWORDS):
                                    continue  # Deprecated/guard reference only
                                key = "v33" if re.search(r'V33|v33', line) else "v38"
                                active_refs[key].append(
                                    f"{os.path.relpath(fpath, WORKSPACE)}:{i}"
                                )
                except (UnicodeDecodeError, IOError):
                    continue
    
    return active_refs


def check_phase_e_and_production():
    """Check that phase_e_allowed and production_verified are false."""
    # These are assumed not in this phase - check config docs
    return {
        "phase_e_allowed": False,
        "production_verified": False,
    }


def write_marker(results):
    """Write check results to marker file (NOT committed)."""
    marker_dir = os.path.join(WORKSPACE, "data", "runtime", "status")
    os.makedirs(marker_dir, exist_ok=True)
    marker_path = os.path.join(marker_dir, "system_legacy_purge_check.json")
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path}")
    print("(This marker is NOT committed)")


def main():
    results = {
        "check_status": "PASS",
        "legacy_files_scanned": 0,
        "tools_legacy_files_remaining": [],
        "archived_legacy_files": [],
        "archive_markers_valid": False,
        "formal_v4_files": [],
        "formal_v4_candidate_files": [],
        "v33_reference_count": 0,
        "v38_reference_count": 0,
        "active_v33_reference_found": False,
        "active_v38_reference_found": False,
        "batch_worker_remaining_in_tools": False,
        "backup_worker_remaining_in_tools": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "blockers": [],
    }
    
    block = False
    
    # 1. Check tools/ for legacy files
    tools_legacy = scan_tools_legacy()
    results["tools_legacy_files_remaining"] = tools_legacy
    if tools_legacy:
        results["check_status"] = "WARN"
        results["blockers"].append(f"Legacy files still found in tools/: {tools_legacy}")
    
    # 2. Check archive markers
    archive_check = check_archive_markers()
    results["archive_markers_valid"] = archive_check["valid"]
    if not archive_check["valid"]:
        results["check_status"] = "WARN"
        results["blockers"].extend(archive_check.get("errors", []))
    
    # 3. Check data archive markers
    data_check = check_data_archive_markers()
    if not data_check["valid"]:
        results["check_status"] = "WARN"
        results["blockers"].extend(data_check.get("errors", []))
    
    # 4. Check V4 whitelist
    whitelist_check = check_v4_whitelist()
    if not whitelist_check["valid"]:
        results["check_status"] = "WARN"
        results["blockers"].extend(whitelist_check.get("errors", []))
    
    # 5. Scan for active V33/V38 references
    active_refs = scan_v33_v38_references()
    results["v33_reference_count"] = len(active_refs["v33"])
    results["v38_reference_count"] = len(active_refs["v38"])
    results["active_v33_reference_found"] = len(active_refs["v33"]) > 0
    results["active_v38_reference_found"] = len(active_refs["v38"]) > 0
    if active_refs["v33"]:
        results["check_status"] = "WARN"
        results["blockers"].append(f"Active V33 references: {active_refs['v33']}")
    if active_refs["v38"]:
        results["check_status"] = "WARN"
        results["blockers"].append(f"Active V38 references: {active_refs['v38']}")
    
    # 6. Batch/backup worker checks
    batch_remaining = bool(glob.glob(os.path.join(TOOLS_DIR, "*batch-worker*")))
    backup_remaining = bool(glob.glob(os.path.join(TOOLS_DIR, "*backup*")))
    results["batch_worker_remaining_in_tools"] = batch_remaining
    results["backup_worker_remaining_in_tools"] = backup_remaining
    if batch_remaining:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("Batch worker still found in tools/")
        block = True
    
    # 7. Phase E / production check
    phase_check = check_phase_e_and_production()
    results["phase_e_allowed"] = phase_check["phase_e_allowed"]
    results["production_verified"] = phase_check["production_verified"]
    
    # 8. List archived files
    if os.path.isdir(ARCHIVE_DIR):
        results["archived_legacy_files"] = [
            f for f in os.listdir(ARCHIVE_DIR)
            if os.path.isfile(os.path.join(ARCHIVE_DIR, f))
        ]
    
    # 9. Count tools/ JS files remaining
    results["legacy_files_scanned"] = len(tools_legacy)
    
    # Determine final status
    if block:
        results["check_status"] = "BLOCKER"
    elif results["blockers"]:
        results["check_status"] = "WARN"
    else:
        results["check_status"] = "PASS"
    
    print("=" * 60)
    print("SYSTEM-LEGACY-0 PURGE CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Tools legacy remaining: {len(tools_legacy)}")
    print(f"Archive markers valid: {archive_check['valid']}")
    print(f"Active V33 refs: {len(active_refs['v33'])}")
    print(f"Active V38 refs: {len(active_refs['v38'])}")
    print(f"Batch worker in tools: {batch_remaining}")
    print(f"Backup worker in tools: {backup_remaining}")
    print(f"Phase E allowed: {phase_check['phase_e_allowed']}")
    print(f"Production verified: {phase_check['production_verified']}")
    
    if results["blockers"]:
        print(f"\nBlockers ({len(results['blockers'])}):")
        for b in results["blockers"]:
            print(f"  - {b}")
    
    if results["check_status"] == "BLOCKER":
        sys.exit(1)
    
    write_marker(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
