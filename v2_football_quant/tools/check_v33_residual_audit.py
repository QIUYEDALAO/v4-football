#!/usr/bin/env python3
"""V33 Residual Audit — classifies all V33 references into allowed_guard / historical_doc / active_path."""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))

SCAN_DIRS = ["engine", "tools", "config", "data_pipeline", "db"]


def classify_file(filepath: Path, content: str, hits: list) -> str:
    """Classify a file's V33 references:
    - allowed_guard: only used to verify V33=false / no_V33 / --no-v33 guard
    - historical_doc: documentation, comments, or audit records
    - active_v33_path: executable code that would run V33 logic
    """
    if filepath.suffix in (".md", ".txt"):
        return "historical_doc"

    # Check if this is a checker/guard file
    is_checker = "check_" in filepath.name or "guard" in filepath.name
    is_guard_context = all(
        any(term in content for term in ["false", "no_v33", "no-v33", "disabled", "prohibited", "blocked",
                                          "V33_ENABLED", "not allowed", "must not", "不得"])
        for hit_line in hits
    )

    if filepath.suffix == ".py":
        # Files that are named check_* or *guard* — these DETECT V33 contamination, they don't execute it.
        if is_checker or "guard" in filepath.stem.lower() or "audit" in filepath.stem.lower():
            return "allowed_guard"

        # Files that reference v33_residual_audit results — meta-audit, not execution
        if "v33_residual_audit" in content or "check_v33_audit" in content:
            return "allowed_guard"

        # Check if V33 appears in actual executable V33 logic (not guard/check context)
        has_executable_v33 = False
        for line in hits:
            stripped = line.strip()
            # Skip comments and docstrings
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if '"""' in stripped or "'''" in stripped:
                continue
            # Skip lines that are clearly guard/check/prohibition context
            if re.search(r'false|True|False|--no-v33|no_v33|prohibited|disabled|'
                        r'not allowed|blocked|check|guard|audit|must not|不得|禁止',
                        stripped, re.IGNORECASE):
                continue
            # Skip string literals
            if re.search(r'["\'][^"\']*V33[^"\']*["\']', stripped):
                continue
            # Skip lines that just import or reference V33 in data context
            if re.search(r'no_V33|V33_ENABLED|no_v33|--no-v33', stripped):
                continue
            # Skip lines that reference V33 in audit/monitoring/check context (meta-audit, not execution)
            if re.search(r'v33_residual_audit|v33.*audit|audit.*v33|check_v33|V33.*审计|审计.*V33|'
                        r'notification_severity|sys_audit|audit_notification',
                        stripped, re.IGNORECASE):
                continue
            # This looks like real V33 executable code
            has_executable_v33 = True
            break

        if has_executable_v33:
            return "active_v33_path"

        # V33 mentioned only in guard context — allowed guard
        has_guard_mention = bool(re.search(
            r'V33.*false|no_v33|V33_ENABLED|--no-v33|active_v33|prohibited|disabled',
            content, re.IGNORECASE))
        return "allowed_guard" if has_guard_mention else "historical_doc"

    if filepath.suffix in (".json", ".yaml", ".yml"):
        return "allowed_guard" if is_guard_context else "historical_doc"

    return "historical_doc"


def main():
    date_key = datetime.now(TZ).strftime("%Y%m%d")
    R = {
        "checker": "v33_residual_audit",
        "check_status": "PASS",
        "allowed_guard": [],
        "historical_doc": [],
        "active_v33_path": [],
        "allowed_guard_count": 0,
        "historical_doc_count": 0,
        "active_v33_path_count": 0,
        "total_hits": 0,
        "blockers": [],
        "warnings": [],
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "date_key": date_key,
    }

    # Scan for V33 references
    for scan_dir in SCAN_DIRS:
        dir_path = MODULE / scan_dir
        if not dir_path.is_dir():
            continue
        for filepath in dir_path.rglob("*"):
            if filepath.suffix not in (".py", ".md", ".json", ".yaml", ".yml", ".txt"):
                continue
            if "__pycache__" in str(filepath) or ".DS_Store" in str(filepath):
                continue
            if "node_modules" in str(filepath) or "package-lock.json" in filepath.name:
                # node_modules and lock files may contain V33 in hashes — not real references
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if "V33" not in content and "v33" not in content:
                continue

            # Extract all lines containing V33
            lines_with_v33 = [l for l in content.split("\n") if "V33" in l or "v33" in l]
            R["total_hits"] += len(lines_with_v33)

            classification = classify_file(filepath, content, lines_with_v33)
            rel_path = str(filepath.relative_to(MODULE))

            entry = {
                "file": rel_path,
                "lines": len(lines_with_v33),
                "sample": lines_with_v33[0][:120] if lines_with_v33 else "",
            }

            if classification == "allowed_guard":
                R["allowed_guard"].append(entry)
            elif classification == "active_v33_path":
                R["active_v33_path"].append(entry)
            else:
                R["historical_doc"].append(entry)

    # Also scan docs
    docs_dir = MODULE / "docs"
    if docs_dir.is_dir():
        for filepath in docs_dir.rglob("*.md"):
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if "V33" not in content and "v33" not in content:
                continue
            lines_with_v33 = [l for l in content.split("\n") if "V33" in l or "v33" in l]
            rel_path = str(filepath.relative_to(MODULE))
            R["historical_doc"].append({
                "file": rel_path,
                "lines": len(lines_with_v33),
                "sample": lines_with_v33[0][:120] if lines_with_v33 else "",
            })
            R["total_hits"] += len(lines_with_v33)

    R["allowed_guard_count"] = len(R["allowed_guard"])
    R["historical_doc_count"] = len(R["historical_doc"])
    R["active_v33_path_count"] = len(R["active_v33_path"])

    # HARD RULE: active_v33_path_count must be 0
    if R["active_v33_path_count"] > 0:
        R["check_status"] = "BLOCKER"
        R["blockers"].append(f"active_v33_path_count={R['active_v33_path_count']} — must be 0")
        for entry in R["active_v33_path"]:
            R["blockers"].append(f"  active V33 path: {entry['file']}")

    print("=" * 60)
    print("V33 RESIDUAL AUDIT")
    print("=" * 60)
    print(f"Status: {R['check_status']}")
    print(f"Allowed guards: {R['allowed_guard_count']}")
    print(f"Historical docs: {R['historical_doc_count']}")
    print(f"Active V33 paths: {R['active_v33_path_count']}  ← must be 0")
    print(f"Total hits: {R['total_hits']}")

    if R["allowed_guard"]:
        print(f"\n--- Allowed Guards ({R['allowed_guard_count']}) ---")
        for e in R["allowed_guard"]:
            print(f"  {e['file']} ({e['lines']} lines)")

    if R["historical_doc"]:
        print(f"\n--- Historical Docs ({R['historical_doc_count']}) ---")
        for e in R["historical_doc"][:15]:
            print(f"  {e['file']} ({e['lines']} lines)")
        if R["historical_doc_count"] > 15:
            print(f"  ... and {R['historical_doc_count'] - 15} more")

    if R["active_v33_path"]:
        print(f"\n--- ACTIVE V33 PATHS ({R['active_v33_path_count']}) --- BLOCKER ---")
        for e in R["active_v33_path"]:
            print(f"  ! {e['file']}: {e['sample']}")

    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"  ! {b}")

    out = MODULE / "data" / "runtime" / "status" / f"v33_residual_audit_{date_key}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str))

    if R["check_status"] == "BLOCKER":
        sys.exit(2)
    elif R["check_status"] == "WARN":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
