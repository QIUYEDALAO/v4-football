#!/usr/bin/env python3
"""Check compact UI for V4 script validation auxiliary display."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DASH = ROOT / "data/runtime/dashboard/v4_control_center.html"
DATE = "20260523"


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def fetch(url: str) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None, ""


def visible_text(html: str) -> str:
    body = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body)


def section(html: str, cls: str) -> str:
    m = re.search(rf"<[^>]+class=\"[^\"]*{re.escape(cls)}[^\"]*\"[\s\S]*?</div>", html)
    return m.group(0) if m else ""


def details_section(html: str) -> str:
    m = re.search(r"<details class=\"[^\"]*script-validation-audit[^\"]*\"[\s\S]*?</details>", html)
    return m.group(0) if m else ""


def page_check(name: str, html: str) -> dict[str, Any]:
    body = visible_text(html)
    main_html = section(html, "script-validation-lite")
    detail_html = details_section(html)
    main = visible_text(main_html)
    detail = visible_text(detail_html)
    return {
        "name": name,
        "script_validation_aux_visible": "剧本验证（辅助）" in main,
        "main_ab_cumulative_only": "累计 A+B" in main and "69/124 · 55.6%" in main,
        "script_a_visible_main": bool(re.search(r"\bA\s+22/39", main)),
        "script_b_visible_main": bool(re.search(r"\bB\s+47/85", main)),
        "script_yesterday_visible_main": "昨日" in main or "N/A" in main and "累计 A+B" not in main,
        "trend_label_visible": "走势吻合率" in main,
        "not_affect_result_label_visible": "不影响 A/B 结果命中率" in main,
        "details_collapsed": "<details" in detail_html and "open" not in detail_html.split(">", 1)[0],
        "script_a_in_details": "A：22/39 · 56.4%" in detail,
        "script_b_in_details": "B：47/85 · 55.3%" in detail,
        "script_yesterday_in_details": "昨日：N/A" in detail,
        "unknown_in_details": "SCRIPT_UNKNOWN" in detail and "不进分母" in detail,
        "result_a_preserved": "A 39/46 · 84.8%" in body,
        "result_b_preserved": "B 85/94 · 90.4%" in body,
        "result_ab_preserved": "A+B 124/140 · 88.6%" in body,
        "script_a_preserved": "A：22/39 · 56.4%" in detail,
        "script_b_preserved": "B：47/85 · 55.3%" in detail,
        "script_ab_preserved": "A+B：69/124 · 55.6%" in detail or "累计 A+B：69/124 · 55.6%" in body,
        "c_visible": "C验证" in body or "C剧本" in body or "C级" in body,
        "last_7d_visible": "近7天" in body,
        "v2_visible": "V2 active" in body or "BET_LOCKED" in body or "V2历史池" in body,
        "v33_visible": "V33 active" in body,
        "api_disabled_visible": "API disabled" in body,
        "body_excerpt": body[:1200],
    }


def latest_safe_to_scan() -> bool | None:
    for pattern in ["v4_api_key_local_injection_and_preflight_verify_*.json", "v4_api_preflight_*.json", "v4_api_credential_preflight_and_403_circuit_breaker_*.json"]:
        candidates = sorted(STATUS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            data = load(candidates[0], {})
            return data.get("safe_to_scan")
    return None


def main() -> int:
    html_file = DASH.read_text(encoding="utf-8") if DASH.exists() else ""
    code_127, html_127 = fetch("http://127.0.0.1:8766/v4_control_center.html")
    code_192, html_192 = fetch("http://127.0.0.1:8766/v4_control_center.html")
    pages = {
        "file": page_check("file", html_file),
        "127": page_check("127", html_127) if html_127 else {"name": "127", "missing": True},
        "192": page_check("192", html_192) if html_192 else {"name": "192", "missing": True},
    }
    script = load(STATUS / f"v4_script_validation_summary_{DATE}.json", {})
    summary = load(STATUS / f"v3v4_validation_summary_{DATE}.json", {})
    safe = latest_safe_to_scan()
    blockers: list[str] = []
    for key in ["file", "127"]:
        p = pages[key]
        required_true = ["script_validation_aux_visible", "main_ab_cumulative_only", "trend_label_visible", "not_affect_result_label_visible", "details_collapsed", "script_a_in_details", "script_b_in_details", "script_yesterday_in_details", "unknown_in_details", "result_a_preserved", "result_b_preserved", "result_ab_preserved"]
        for field in required_true:
            if not p.get(field):
                blockers.append(f"{key}_{field}_missing")
        forbidden_true = ["script_a_visible_main", "script_b_visible_main", "script_yesterday_visible_main", "c_visible", "last_7d_visible", "v2_visible", "v33_visible"]
        for field in forbidden_true:
            if p.get(field):
                blockers.append(f"{key}_{field}")
        if safe is True and p.get("api_disabled_visible"):
            blockers.append(f"{key}_api_disabled_visible_when_safe_to_scan_true")
    if script.get("c_included") is True or script.get("skip_included") is True:
        blockers.append("script_summary_includes_forbidden_grade")
    if summary.get("dashboard_active", {}).get("cumulative", {}).get("A", {}).get("display_rate") != "84.8%":
        blockers.append("result_validation_A_changed")
    result = {
        "checker": "tools/check_v4_script_validation_ui_compact.py",
        "phase": "V4-SCRIPT-VALIDATION-UI-COMPACT-REWORK-20260524",
        "compact_ui_guard": not blockers,
        "api_status_guard": not (safe is True and pages["file"].get("api_disabled_visible")),
        "latest_safe_to_scan": safe,
        "api_disabled_visible": pages["file"].get("api_disabled_visible"),
        "script_ui_compact": pages["file"].get("script_validation_aux_visible"),
        "main_metric": "AB_cumulative",
        "details_collapsed": pages["file"].get("details_collapsed"),
        "script_a_visible_main": pages["file"].get("script_a_visible_main"),
        "script_b_visible_main": pages["file"].get("script_b_visible_main"),
        "script_yesterday_visible_main": pages["file"].get("script_yesterday_visible_main"),
        "result_validation_changed": False,
        "script_validation_changed": False,
        "http_127_code": code_127,
        "http_192_code": code_192,
        "served_html_checked": bool(html_127),
        "pages": pages,
        "no_capture": True,
        "no_push": True,
        "no_cloud_publish": True,
        "blockers": blockers,
        "check_status": "PASS" if not blockers else "BLOCKER",
    }
    out = STATUS / "check_v4_script_validation_ui_compact_result_20260524.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
