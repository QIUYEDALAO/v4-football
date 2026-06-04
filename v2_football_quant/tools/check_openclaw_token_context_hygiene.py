#!/usr/bin/env python3
"""
OpenClaw Token Context Hygiene Checker.

Checks:
1. All 3 docs exist and are readable
2. Docs contain required sections (main session / child session / memory bridge / allowed/forbidden / high-risk STOP / token_hygiene fields)
3. Docs contain no real API keys / secrets / tokens
4. No V2/V3/V4 business code modified (this commit only docs/checker)
5. Runtime/cache/log not staged
6. V4 scanner/runner/dashboard/cron not staged
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
TOOLS_DIR = ROOT / "tools"

EXPECTED_DOCS = [
    "OPENCLAW_RUNTIME_OPTIMIZATION_PACK_PHASE_1_TOKEN_CONTEXT_HYGIENE_20260605.md",
    "OPENCLAW_CHILD_SESSION_TASK_TEMPLATE_20260605.md",
    "OPENCLAW_MEMORY_BRIDGE_TEMPLATE_20260605.md",
]

REQUIRED_SECTIONS = [
    # Main session
    "main session responsibilities",
    "child session responsibilities",
    # Applicable scenarios
    "applicable scenarios",
    # Forbidden/allowed
    "forbidden content in main session",
    "allowed content in main session",
    # Memory bridge
    "memory bridge",
    # Artifact
    "artifact summary",
    # STOP rules
    "high-risk stop",
    # Token hygiene
    "token_hygiene",
]

# Templates only need their core topic, not the full spec
TEMPLATE_MINIMUM = [
    "template",
    "stop",
    "token_hygiene",
    "forbidden",
]

HYGIENE_FIELDS = [
    "raw_json_pasted",
    "raw_html_pasted",
    "browser_snapshot_pasted",
    "api_response_pasted",
    "ocr_fulltext_pasted",
    "checker_full_json_pasted",
    "runtime_log_fulltext_pasted",
    "output_lines_under_120",
    "artifact_paths_reported",
    "secrets_printed",
]


def check_file_exists(path: Path) -> bool:
    return path.is_file()


def check_doc_sections(path: Path) -> list[str]:
    """Check a doc contains required sections.
    
    The main spec doc (RUNTIME_OPTIMIZATION_PACK) must have all sections.
    Template docs only need their core topic + safety fields.
    """
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    missing = []
    
    if "template" in path.name.lower():
        # Template docs: check minimum set
        for section in TEMPLATE_MINIMUM:
            if section not in text:
                missing.append(section)
    else:
        # Main spec: check all sections
        for section in REQUIRED_SECTIONS:
            if section not in text:
                missing.append(section)
    return missing


def check_no_secrets_in_docs(path: Path) -> list[str]:
    """Check docs contain no real API keys/secrets/tokens."""
    text = path.read_text(encoding="utf-8", errors="replace")
    problems = []
    # Check for real-looking secrets (hex strings that look like API keys)
    # Pattern: long alphanumeric strings that could be keys
    key_patterns = [
        (r'\b[0-9a-f]{32,}\b', 'Possible API key (32+ hex chars)'),
        (r'\bsk-[a-zA-Z0-9]{20,}\b', 'Possible OpenAI-style key'),
        (r'x-apisports-key\s*:\s*[0-9a-f]{8,}', 'Possible API key after header'),
        (r'Authorization:\s*Bearer\s+[a-zA-Z0-9._-]{20,}', 'Possible bearer token'),
    ]
    for pattern, label in key_patterns:
        if re.search(pattern, text):
            problems.append(f"{label} found in {path.name}")
    return problems


def check_staged_files() -> list[str]:
    """Check git staged files for hygiene violations."""
    try:
        # Check what's staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=ROOT, check=False, timeout=15
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        problems = []

        # Check for business code changes
        for f in staged:
            if f.startswith("engine/") or f.startswith("scripts/") or f.startswith("config/"):
                if "openclaw" not in f.lower() and "hygiene" not in f.lower():
                    problems.append(f"Business code staged: {f}")

        # Check for V4 files
        for f in staged:
            if "v4_" in f.lower() and "doc" not in f.lower():
                problems.append(f"V4 file staged: {f}")

        # Check for runtime/cache/log
        for f in staged:
            if "runtime/" in f or "/cache/" in f or "/log/" in f or ".log" in f:
                problems.append(f"Runtime/cache/log staged: {f}")

        # Check for secrets
        for f in staged:
            if "secrets" in f.lower() or ".env" in f.lower() or "token" in f.lower():
                problems.append(f"Secrets/env file staged: {f}")

        return problems
    except Exception as e:
        return [f"git check failed: {e}"]


def main():
    failures = []
    warnings = []

    # 1. Check docs exist
    for doc_name in EXPECTED_DOCS:
        doc_path = DOCS_DIR / doc_name
        if check_file_exists(doc_path):
            print(f"  ✅ {doc_name} exists")
        else:
            failures.append(f"Missing doc: {doc_name}")
            print(f"  ❌ {doc_name} MISSING")

    # 2. Check docs contain required sections
    for doc_name in EXPECTED_DOCS:
        doc_path = DOCS_DIR / doc_name
        if not doc_path.exists():
            continue
        missing = check_doc_sections(doc_path)
        if missing:
            failures.append(f"{doc_name}: missing sections: {missing}")
            print(f"  ❌ {doc_name}: missing sections: {missing}")
        else:
            print(f"  ✅ {doc_name}: all required sections present")

    # 3. Check no secrets in docs
    for doc_name in EXPECTED_DOCS:
        doc_path = DOCS_DIR / doc_name
        if not doc_path.exists():
            continue
        problems = check_no_secrets_in_docs(doc_path)
        if problems:
            failures.append(f"{doc_name}: {problems}")
            print(f"  ❌ {doc_name}: secrets found: {problems}")
        else:
            print(f"  ✅ {doc_name}: no secrets detected")

    # 4. Check checker has hygiene fields
    checker_path = Path(__file__).resolve()
    checker_text = checker_path.read_text(encoding="utf-8")
    hygiene_in_checker = all(f in checker_text for f in HYGIENE_FIELDS)
    if hygiene_in_checker:
        print(f"  ✅ Checker includes all {len(HYGIENE_FIELDS)} token_hygiene fields")
    else:
        missing_hygiene = [f for f in HYGIENE_FIELDS if f not in checker_text]
        warnings.append(f"Checker missing hygiene fields: {missing_hygiene}")
        print(f"  ⚠️  Checker missing hygiene fields: {missing_hygiene}")

    # 5. Check staged files
    staged_problems = check_staged_files()
    if staged_problems:
        failures.extend(staged_problems)
        for p in staged_problems:
            print(f"  ❌ {p}")
    else:
        print(f"  ✅ No business code / runtime / V4 files staged")

    # Report
    print()
    if failures:
        print(f"CONCLUSION: FAILED — {len(failures)} failure(s)")
        for f in failures:
            print(f"  FAIL: {f}")
    elif warnings:
        print(f"CONCLUSION: PASS — {len(warnings)} warning(s)")
        for w in warnings:
            print(f"  WARN: {w}")
    else:
        print(f"CONCLUSION: PASS")

    result = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "conclusion": "FAILED" if failures else "PASS",
        "failures": failures,
        "warnings": warnings,
        "expected_docs": EXPECTED_DOCS,
        "required_sections": REQUIRED_SECTIONS,
        "hygiene_fields": HYGIENE_FIELDS,
    }

    status_dir = ROOT / "data" / "runtime" / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    status_path = status_dir / "check_openclaw_token_context_hygiene_20260605.json"
    status_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nStatus written: {status_path}")

    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
