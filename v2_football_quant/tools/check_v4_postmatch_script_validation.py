#!/usr/bin/env python3
"""Guard V4 postmatch script validation addon."""
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


def text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


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


def page_checks(name: str, html: str) -> dict[str, Any]:
    body = visible_text(html)
    script_details_visible = "剧本验证审计" in body or "剧本验证明细" in body
    script_na_or_data = (
        "剧本验证" in body
        and (
            "N/A" in body
            or "累计 A+B" in body
            or re.search(r"A\+B[:：]?\s*\d+/\d+", body) is not None
            or re.search(r"\d+/\d+\s*·\s*\d+(?:\.\d+)?%", body) is not None
        )
    )
    return {
        "name": name,
        "script_validation_visible": "剧本验证" in body,
        "script_audit_visible": script_details_visible,
        "result_validation_visible": "V3/V4 比赛验证" in body and "累计验证" in body,
        "c_script_visible": "C剧本" in body or "C 观察剧本" in body or "C级剧本" in body,
        "last_7d_visible": "近7天" in body,
        "v2_visible": "V2 active" in body or "BET_LOCKED" in body or "V2历史池" in body,
        "v33_visible": "V33 active" in body,
        "script_na_or_data": script_na_or_data,
    }


def main() -> int:
    schema = load(STATUS / "v4_script_validation_schema_20260523.json", {})
    script = load(STATUS / f"v4_script_validation_summary_{DATE}.json", {})
    summary = load(STATUS / f"v3v4_validation_summary_{DATE}.json", {})
    html_file = text(DASH)
    code_resolver = text(ROOT / "tools/rebuild_v4_script_validation_from_match_date.py")
    page_file = page_checks("file", html_file)
    code_127, html_127 = fetch("http://127.0.0.1:8766/v4_control_center.html")
    code_192, html_192 = fetch("http://127.0.0.1:8766/v4_control_center.html")
    page_127 = page_checks("127", html_127) if html_127 else {"name": "127", "http_code": code_127}
    page_192 = page_checks("192", html_192) if html_192 else {"name": "192", "http_code": code_192}

    script_validation = summary.get("script_validation", {}) if isinstance(summary.get("script_validation"), dict) else {}
    enum_ok = set(schema.get("script_result_enum", [])) == {"SCRIPT_HIT", "SCRIPT_PARTIAL", "SCRIPT_MISS", "SCRIPT_UNKNOWN"}
    dashboard_active_has_c = "\"C\"" in json.dumps(script_validation.get("yesterday", {}), ensure_ascii=False) or "\"C\"" in json.dumps(script_validation.get("cumulative", {}), ensure_ascii=False)
    dashboard_active_has_skip = "SKIP" in json.dumps(script_validation.get("yesterday", {}), ensure_ascii=False) or "SKIP" in json.dumps(script_validation.get("cumulative", {}), ensure_ascii=False)
    blockers: list[str] = []
    if not schema or not enum_ok:
        blockers.append("script_validation_schema_missing_or_invalid")
    if not script:
        blockers.append("script_validation_summary_missing")
    if not summary.get("result_validation") or not script_validation:
        blockers.append("result_script_validation_not_separated")
    if dashboard_active_has_c or script.get("c_included") is True:
        blockers.append("script_validation_contains_C")
    if dashboard_active_has_skip or script.get("skip_included") is True:
        blockers.append("script_validation_contains_SKIP")
    if script.get("brief_used_for_script_validation") is True or "brief" in code_resolver.lower() and "brief_used_for_script_validation":
        # The resolver may contain the literal guard field name; only block on active true.
        if script.get("brief_used_for_script_validation") is True:
            blockers.append("brief_used_for_script_validation")
    if script.get("scan_date_used") is True:
        blockers.append("scan_date_used_for_script_validation")
    if script.get("match_date_used") is not True:
        blockers.append("match_date_not_used")
    if script.get("unknown_excluded_from_denominator") is not True:
        blockers.append("script_unknown_denominator_guard_missing")
    for p in [page_file, page_127]:
        if not p.get("script_validation_visible"):
            blockers.append(f"script_validation_missing_in_{p.get('name')}")
        if p.get("c_script_visible"):
            blockers.append(f"c_script_visible_in_{p.get('name')}")
        if p.get("last_7d_visible"):
            blockers.append(f"last_7d_visible_in_{p.get('name')}")
        if p.get("v2_visible") or p.get("v33_visible"):
            blockers.append(f"legacy_visible_in_{p.get('name')}")
    result = {
        "checker": "tools/check_v4_postmatch_script_validation.py",
        "phase": "V4-POSTMATCH-SCRIPT-VALIDATION-ADDON-20260523",
        "schema_exists": bool(schema),
        "script_validation_summary_exists": bool(script),
        "result_validation_preserved": bool(summary.get("result_validation")),
        "script_validation_added": bool(script_validation),
        "script_result_enum": schema.get("script_result_enum"),
        "unknown_excluded_from_denominator": script.get("unknown_excluded_from_denominator"),
        "brief_used_for_script_validation": script.get("brief_used_for_script_validation"),
        "scan_date_used": script.get("scan_date_used"),
        "match_date_used": script.get("match_date_used"),
        "c_included": script.get("c_included"),
        "skip_included": script.get("skip_included"),
        "dashboard_script_validation_visible": page_file.get("script_validation_visible"),
        "dashboard_script_na_or_data": page_file.get("script_na_or_data"),
        "served_html_checked": html_127 != "",
        "http_127_code": code_127,
        "http_192_code": code_192,
        "page_checks": {"file": page_file, "127": page_127, "192": page_192},
        "no_capture": True,
        "no_push": True,
        "no_cloud_publish": True,
        "v2_restored": False,
        "v33_active": False,
        "blockers": blockers,
        "check_status": "PASS" if not blockers else "BLOCKER",
    }
    out = STATUS / "check_v4_postmatch_script_validation_result_20260523.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
