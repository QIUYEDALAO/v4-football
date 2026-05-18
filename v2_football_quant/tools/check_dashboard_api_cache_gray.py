#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "runtime" / "dashboard"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))


def main() -> None:
    parser = argparse.ArgumentParser(description="Check API cache diagnostics gray page")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = args.date.strip().replace("-", "")

    page = OUT_DIR / "api_cache.html"
    out = STATUS_DIR / f"dashboard_api_cache_gray_check_{date_key}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not page.exists():
        result = {
            "status": "BLOCKER",
            "page_found": False,
            "content_valid": False,
            "no_secret": False,
            "no_action_button": False,
            "production_dependency": False,
            "production_verified": False,
            "warnings": warnings,
            "errors": ["api_cache_page_missing"],
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    html = page.read_text(encoding="utf-8", errors="replace")
    required = [
        "API Snapshot / Cache 诊断页",
        "production_verified",
        "production_dependency",
        "正式链路接入",
        "API调用",
        "读取key",
        "V2正式链路对账",
        "V4正式链路对账",
    ]
    for key in required:
        if key not in html:
            errors.append(f"required_missing:{key}")

    # Must keep negative production posture.
    if "production_verified</div><div class='v'><span class=\"tag bad\">失败</span>" in html:
        errors.append("production_verified_bad_tag")
    if "production_verified</div><div class='v'><span class=\"tag neutral\">是</span>" in html:
        errors.append("production_verified_true")
    if re.search(r"production_verified.*true", html, re.IGNORECASE):
        errors.append("production_verified_true_literal")
    if re.search(r"production_dependency.*true", html, re.IGNORECASE):
        errors.append("production_dependency_true_literal")

    secret_patterns = [
        r"APIFOOTBALL_KEY",
        r"OPENCLAW_APIFOOTBALL_KEY",
        r"x-apisports-key",
        r"sk-[A-Za-z0-9]{20,}",
        r"(?i)token\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}",
        r"(?i)secret\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{10,}",
    ]
    secret_findings = []
    for pat in secret_patterns:
        if re.search(pat, html):
            secret_findings.append(pat)
    no_secret = not secret_findings
    if not no_secret:
        errors.append("secret_pattern_detected")

    # No action buttons / trigger actions.
    lowered = html.lower()
    action_risks = []
    for token in ["refresh api", "trigger", "execute", "run now", "接入生产", "推送", "<button"]:
        if token in lowered:
            action_risks.append(token)
    no_action_button = len(action_risks) == 0
    if not no_action_button:
        errors.append("action_button_or_trigger_detected")

    status = "PASS"
    if errors:
        status = "FAIL"
    elif warnings:
        status = "WARN"

    result = {
        "status": status,
        "page_found": True,
        "content_valid": len([e for e in errors if e.startswith("required_missing:")]) == 0,
        "no_secret": no_secret,
        "no_action_button": no_action_button,
        "production_dependency": False,
        "production_verified": False,
        "warnings": warnings,
        "errors": errors,
        "secret_findings": secret_findings,
        "action_risks": action_risks,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

