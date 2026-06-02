#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_no_betting_words_20260602.json"

SCOPES = [
    ROOT / "data/v3_worldcup",
    ROOT / "data/runtime/dashboard",
    ROOT / "docs",
    ROOT / "tools",
]

BANNED_REGEX = [
    r"\bbetting recommendation\b",
    r"\bstake\b",
    r"\bwager\b",
    r"\bauto bet\b",
    r"\blocked pick\b",
    r"\bbuy\b",
    r"\bsell\b",
    r"推荐下注",
    r"投注建议",
    r"重仓",
    r"梭哈",
    r"必中",
    r"稳胆",
]

ALLOW_PHRASES = [
    "no betting recommendations",
    "no betting recommendation",
    "not a betting recommendation",
    "not betting recommendation",
    "禁止投注推荐",
    "不输出投注建议",
    "不是投注建议",
    "observation-only, not trading signal",
    "任何 watchlist 都不是推荐下注",
    "不构成投注建议",
    "无投注建议",
    "dry-run 不等于 official final squad",
    "candidate review only",
]


def in_scope(path: Path) -> bool:
    s = str(path)
    if s.endswith(".md"):
        return "V3_WORLDCUP" in path.name
    if path.suffix == ".html":
        return path.name.startswith("v3_worldcup")
    if path.suffix == ".py":
        return (
            path.name.startswith("build_v3_worldcup")
            or path.name.startswith("check_v3_worldcup")
            or path.name.startswith("v3_worldcup")
        )
    if "data/v3_worldcup/" in s:
        return path.suffix in {".json", ".md", ".txt"}
    if "data/runtime/v3_worldcup/" in s:
        return path.suffix in {".json", ".txt"}
    return False


def main() -> int:
    files: list[Path] = []
    for base in SCOPES:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and in_scope(p):
                files.append(p)

    violations = []
    for p in files:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        low = txt.lower()
        for allowed in ALLOW_PHRASES:
            low = low.replace(allowed.lower(), "")
        if p.name.startswith("check_v3_worldcup"):
            continue
        for bad in BANNED_REGEX:
            if re.search(bad, low):
                violations.append({"file": str(p), "word": bad})

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not violations else "BLOCKER",
        "violations": violations[:100],
        "scanned_files": len(files),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "violations": len(violations), "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not violations else 2


if __name__ == "__main__":
    raise SystemExit(main())
