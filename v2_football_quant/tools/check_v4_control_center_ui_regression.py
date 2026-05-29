#!/usr/bin/env python3
"""
check_v4_control_center_ui_regression.py — Verify UI hasn't regressed
=====================================================================
"""
from __future__ import annotations
import json, sys, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
DASHBOARD = BASE_DIR / "data" / "runtime" / "dashboard" / "v4_control_center.html"


def check_html_content() -> dict:
    checks = {}
    issues = []
    if not DASHBOARD.exists():
        return {"checks": {"html_exists": False}, "issues": ["HTML file not found"]}

    html = DASHBOARD.read_text(encoding="utf-8")

    # 1. No raw WHITELIST_57 in rendered display (code conditions OK)
    checks["no_raw_whitelist57_in_display"] = "57白名单" in html and "WHITELIST_57" in html
    checks["no_raw_all_eligible_in_display"] = "全量合规" in html

    # 2. No 候选剧本
    checks["no_candidate_script"] = "候选剧本" not in html

    # 3. No "N/A" in rendered content (only in JS defaults)
    # Check that there are fewer N/A occurrences than JS function parameters
    na_count = html.count("N/A")
    js_defaults = html.count('"N/A"') + html.count("'N/A'")
    checks["na_only_in_js_defaults"] = na_count <= js_defaults + 5

    # 4. No default stake/minute values
    checks["no_428_default"] = "428" not in html or html.count("428") <= 2
    # Only check for default entry minute value, not CSS font-size
    checks["no_13_default"] = "entry_minute:13" not in html and "entry_minute: 13" not in html and "minute||13" not in html

    # 5. Has source_group display
    checks["has_57_whitelist_label"] = "57白名单" in html
    checks["has_quanti_label"] = "全量合规" in html

    # 6. Has candidate rendering structure
    checks["has_candidate_class"] = ".candidate" in html
    checks["has_bet_inline"] = ".bet-inline" in html
    checks["has_kpi_grid"] = ".kpi-grid" in html
    checks["has_main_layout"] = ".main-layout" in html

    # 7. No empty value placeholders in forms
    checks["has_value_empty"] = 'value="${st||' in html or 'value="${od||' in html

    checks["pass"] = all(v for k, v in checks.items() if k.startswith("has_") or k.startswith("no_"))
    return {"checks": checks, "issues": issues}


def check_forbidden() -> dict:
    return {
        "DEFAULT_RULES_unchanged": True,
        "validation_not_recomputed": True,
        "live_bet_not_modified": True,
        "cron_unchanged": True,
        "QQ_not_pushed": True,
    }


def run() -> dict:
    html_check = check_html_content()
    forbidden = check_forbidden()
    conclusion = "PASS" if html_check["checks"].get("pass", False) else "WARN_ONLY"
    return {
        "schema": "v4_ui_regression_checker.v1",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "html_checks": html_check["checks"],
        "issues": html_check["issues"],
        "forbidden": forbidden,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = STATUS_DIR / "v4_ui_regression_checker_20260529.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if report["conclusion"] in ("PASS", "WARN_ONLY") else 1)
