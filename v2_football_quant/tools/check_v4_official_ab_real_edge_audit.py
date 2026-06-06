#!/usr/bin/env python3
"""Check the V4 official A/B real-edge audit freeze.

Read-only checker. It validates the corrected official record, break-even odds,
ROI sensitivity, drawdown caveat, and safety boundaries.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/V4_OFFICIAL_AB_REAL_EDGE_AUDIT_20260606.md"

OFFICIAL = {
    "A": {"hit": 30, "settled": 49, "pending": 0, "break_even": 1.6333},
    "B": {"hit": 54, "settled": 95, "pending": 1, "break_even": 1.7593},
    "AB": {"hit": 84, "settled": 144, "pending": 1, "break_even": 1.7143},
}


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def main() -> int:
    text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    required = [
        "30 | 49",
        "54 | 95",
        "84 | 144",
        "61.22%",
        "56.84%",
        "58.33%",
        "1.6333",
        "1.7593",
        "1.7143",
        "-21.02%",
        "-26.67%",
        "-24.75%",
        "Corrected event-level sequence is not available",
        "Pause real-time reminders",
        "Daily report only",
        "Keep blocked / observation-only",
        "Do not weaken that checker to pass",
        "price-aware replay ledger",
    ]
    forbidden = [
        "90.9%",
        "93.5%",
        "84.6%",
        "increase recommendation volume",
        "must bet",
        "sure win",
        "guaranteed profit",
        "稳赚",
        "稳赢",
        "必下",
    ]
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = [
        p for p in staged
        if p.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/"))
        or re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", p)
    ]

    computed = {
        key: round(v["settled"] / v["hit"], 4)
        for key, v in OFFICIAL.items()
    }
    checks = {
        "doc_exists": DOC.exists(),
        "required_numbers_present": all(x in text for x in required),
        "misleading_90pct_not_used": all(x not in text for x in forbidden[:3]),
        "no_profit_certainty_claim": not any(x in text for x in forbidden[3:]),
        "break_even_math_ok": all(abs(computed[k] - OFFICIAL[k]["break_even"]) <= 0.0001 for k in OFFICIAL),
        "risk_decision_present": all(x in text for x in ["A:", "B:", "A+B:", "Shadow/C/SKIP:"]),
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_official_ab_real_edge_audit_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "official_record": OFFICIAL,
        "computed_break_even": computed,
        "forbidden_staged": forbidden_staged,
        "live_api_called": False,
        "scan_executed": False,
        "official_grade_changed": False,
        "pending_written": False,
        "qq_sent": False,
        "cron_or_launchd_modified": False,
        "rf_shadow_promotion_released": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
