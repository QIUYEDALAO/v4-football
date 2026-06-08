#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/v3_worldcup/friendly_simulation/v3_friendly_simulation_ledger_20260608.json"
REPORT = ROOT / "data/v3_worldcup/friendly_simulation/V3_FRIENDLY_SIMULATION_LEDGER_20260608.md"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def staged_safety() -> tuple[bool, list[str], int]:
    cp = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    staged = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
    bad_paths = [
        path for path in staged
        if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\\.log$|\\.lock$|\\.pid$", path, re.I)
        or re.search(r"(^|/)(\\.env|.*\\.env|.*\\.key|.*secret.*|.*token.*)(/|$)", path, re.I)
    ]
    diff = subprocess.run(
        ["git", "diff", "--cached"],
        cwd=ROOT.parent,
        text=True,
        capture_output=True,
        check=False,
    ).stdout
    added = "\n".join(line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    secret_re = r"(?i)(api[_-]?" + "key" + r"|token|secret)\\s*[:=]\\s*['\"][A-Za-z0-9_\\-]{16,}"
    secret_hits = len(re.findall(secret_re, added))
    return (not bad_paths and secret_hits == 0), bad_paths, secret_hits


def main() -> int:
    data = load_json(LEDGER)
    records = data.get("records") or []
    included = [r for r in records if r.get("sample_included") is True]
    references = [r for r in records if r.get("sample_included") is False]
    safety = data.get("safety") or {}
    text = (REPORT.read_text(encoding="utf-8") if REPORT.exists() else "") + "\n" + json.dumps(data, ensure_ascii=False)
    staged_ok, bad_paths, secret_hits = staged_safety()

    checks = {
        "ledger_exists": LEDGER.exists(),
        "report_exists": REPORT.exists(),
        "mode_simulation_only": data.get("mode") == "SIMULATION_ONLY" and all(r.get("mode") == "SIMULATION_ONLY" for r in records),
        "record_count_5": len(records) == 5,
        "sample_count_1": data.get("sample_count") == 1 and len(included) == 1,
        "hit_rate_na": data.get("hit_rate") is None and data.get("hit_rate_label") == "N/A",
        "denmark_entry": included
        and included[0].get("match") == "Denmark vs Ukraine"
        and included[0].get("fixture_id") == 1543830
        and included[0].get("direction") == "Denmark -0.75"
        and included[0].get("confidence") == "MEDIUM-LOW"
        and included[0].get("score") == "2-1"
        and included[0].get("settlement") == "HALF_WIN",
        "other_four_not_settled": len(references) == 4
        and all(r.get("settlement") == "NO_DIRECTION_NOT_SETTLED" for r in references),
        "safety_flags": safety.get("simulation_only") is True
        and safety.get("observation_only") is True
        and safety.get("pending_written") is False
        and safety.get("qq_sent") is False
        and safety.get("affects_v4") is False
        and safety.get("runtime_output") is False,
        "no_forbidden_language": not re.search(r"推荐下注|投注建议|重仓|梭哈|必中|稳胆|official|pending_bet", text, re.I),
        "no_runtime_or_secret_staged": staged_ok,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v3_friendly_simulation_ledger_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "sample_count": data.get("sample_count"),
        "hit_rate": data.get("hit_rate_label"),
        "settled_direction_count": len(included),
        "no_direction_reference_count": len(references),
        "bad_staged_paths": bad_paths,
        "secret_literal_hit_count": secret_hits,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
