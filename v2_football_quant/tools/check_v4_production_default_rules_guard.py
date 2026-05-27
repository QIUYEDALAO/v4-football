#!/usr/bin/env python3
"""check_v4_production_default_rules_guard.py — Verify production DEFAULT_RULES are intact."""
from __future__ import annotations
import json, sys, ast
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))

EXPECTED = {
    "grades.A.min_ht_score": 70, "grades.A.min_h2h_ht_goal_rate": 0.65,
    "grades.A.min_recent_ht": 0.70, "grades.A.min_ht_attack": 0.70, "grades.A.min_late_11_45": 0.55,
    "grades.B.min_ht_score": 60, "grades.B.min_h2h_ht_goal_rate": 0.55,
    "grades.B.min_recent_ht": 0.60, "grades.B.min_ht_attack": 0.60, "grades.B.min_late_11_45": 0.45,
    "skip.min_late_11_45": 0.45,
}


def main() -> int:
    ts = datetime.now(TZ).isoformat()
    violations = []
    checks = {}

    mi = ROOT / "engine/v4_match_intelligence.py"
    checks["file_exists"] = mi.exists()
    if not mi.exists():
        violations.append("file_not_found")
        return _output(checks, violations, ts)

    src = mi.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        violations.append("parse_failed")
        return _output(checks, violations, ts)

    # Walk AST to find DEFAULT_RULES dict
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_RULES":
                    if isinstance(node.value, ast.Dict):
                        for k, v in _dict_values(node.value, []):
                            checks[k] = v
    return _output(checks, violations, ts)


def _dict_values(d: ast.Dict, path: list[str]) -> list[tuple[str, object]]:
    results = []
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant):
            key = str(k.value)
            cur = path + [key]
            if isinstance(v, ast.Dict):
                results.extend(_dict_values(v, cur))
            elif isinstance(v, ast.Constant):
                results.append((".".join(cur), v.value))
    return results


def _output(checks: dict, violations: list, ts: str) -> int:
    for k, expected in EXPECTED.items():
        actual = checks.get(k)
        if actual is None:
            violations.append(f"field_missing:{k}")
        elif actual != expected:
            violations.append(f"field_mismatch:{k}={actual},expected={expected}")

    conclusion = "PASS" if not violations else "BLOCKER"
    result = {
        "schema_version": "v4_production_default_rules_guard.v1",
        "generated_at": ts,
        "checks": checks, "violations": violations,
        "expected": EXPECTED, "conclusion": conclusion,
        "forbidden_flags": {"cron_modified": False, "validation_recomputed": False,
                           "live_bet_raw_records_modified": False, "QQ_recommendation_pushed": False},
    }
    out = STATUS / "v4_production_default_rules_guard_20260527.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if conclusion == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
