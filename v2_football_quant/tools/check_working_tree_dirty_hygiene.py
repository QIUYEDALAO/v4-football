#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "v2_football_quant/data/runtime/status/check_working_tree_dirty_hygiene_20260604.json"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
RUNTIME_RE = re.compile(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", re.I)
SECRET_PATH_RE = re.compile(r"(^|/)(\.env|.*\.env|.*\.key|.*secret.*|.*token.*)(/|$)", re.I)
V4_PATH_RE = re.compile(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", re.I)


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = run_git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def staged_diff() -> str:
    return run_git(["diff", "--cached"]).stdout


def main() -> int:
    staged = staged_files()
    runtime_staged = [path for path in staged if RUNTIME_RE.search(path)]
    secret_path_staged = [path for path in staged if SECRET_PATH_RE.search(path)]
    v4_staged = [path for path in staged if V4_PATH_RE.search(path)]
    diff_text = staged_diff()
    secret_literal_hits = []
    for pattern in SECRET_PATTERNS:
        secret_literal_hits.extend(match.group(0)[:48] for match in pattern.finditer(diff_text))
    blockers = []
    if runtime_staged:
        blockers.append("runtime_cache_log_status_staged")
    if secret_path_staged or secret_literal_hits:
        blockers.append("secret_env_key_token_staged")
    if v4_staged:
        blockers.append("v4_file_staged")
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "staged_files": staged,
        "runtime_staged": runtime_staged,
        "secret_path_staged": secret_path_staged,
        "secret_literal_hit_count": len(secret_literal_hits),
        "v4_staged": v4_staged,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
