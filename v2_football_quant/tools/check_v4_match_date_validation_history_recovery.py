#!/usr/bin/env python3
"""Check V4 match-date validation history recovery and dashboard display."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
HTML_PATH = ROOT / "data/runtime/dashboard/intel_ops_console.html"
DATE = "20260523"


def load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fetch(url: str) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, str(exc)


def validation_text(html: str) -> str:
    m = re.search(r'<section class="panel validation-panel.*?</section>', html, re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0))).strip()


def check_body(html: str, summary: dict[str, Any]) -> dict[str, Any]:
    text = validation_text(html)
    trusted = int(summary.get("trusted_records", 0) or 0)
    active = summary.get("dashboard_active", {}) if isinstance(summary.get("dashboard_active"), dict) else {}
    cumulative = active.get("cumulative", {}) if isinstance(active.get("cumulative"), dict) else {}
    cum_metrics = [cumulative.get("A", {}), cumulative.get("B", {}), cumulative.get("A_plus_B", {})]
    cum_all_na = all(str(m.get("display_rate", "N/A")) == "N/A" or int(m.get("settled", 0) or 0) <= 0 for m in cum_metrics if isinstance(m, dict))
    reason_tokens = ["累计验证已从本地 match_date attribution 历史恢复", "API disabled", "no_trusted_history", "暂无可信"]
    return {
        "validation_card_visible": bool(text),
        "yesterday_visible": "昨日验证" in text,
        "cumulative_visible": "累计验证" in text,
        "row_A_visible": bool(re.search(r"\bA\s+(?:N/A|\d+/\d+\s*·\s*\d+\.\d+%)", text)),
        "row_B_visible": bool(re.search(r"\bB\s+(?:N/A|\d+/\d+\s*·\s*\d+\.\d+%)", text)),
        "row_AB_visible": bool(re.search(r"A\+B\s+(?:N/A|\d+/\d+\s*·\s*\d+\.\d+%)", text)),
        "na_reason_visible": any(t in text for t in reason_tokens),
        "cumulative_all_na": cum_all_na,
        "trusted_records_gt_zero_dashboard_has_cumulative_data": (trusted <= 0 or not cum_all_na),
        "c_validation_visible": "C观察" in text or "C级观察" in text,
        "last_7d_visible": "近7天" in text,
        "fake_zero_percent": "0.0%" in text,
        "v2_visible": "V2 active" in html or "BET_LOCKED" in html,
        "v33_visible": "V33 active" in html,
        "brief_used_for_hit_rate_text_true": "brief_used_for_hit_rate=true" in text,
        "text": text[:1200],
    }


def main() -> int:
    summary = load(STATUS / f"v3v4_validation_summary_{DATE}.json")
    dry = load(STATUS / "v4_match_date_validation_history_recovery_dry_run_20260523.json")
    apply = load(STATUS / "v4_match_date_validation_history_recovery_apply_20260523.json")
    stale = load(STATUS / "v4_validation_pre_repair_marked_stale_20260523.json")
    local_html = HTML_PATH.read_text(encoding="utf-8") if HTML_PATH.exists() else ""
    code127, html127 = fetch("http://127.0.0.1:8765/intel_ops_console.html")
    code192, html192 = fetch("http://192.168.1.2:8765/intel_ops_console.html")
    bodies = {
        "file": check_body(local_html, summary),
        "127": check_body(html127, summary) if code127 == 200 else {"validation_card_visible": False, "error": html127},
        "192": check_body(html192, summary) if code192 == 200 else {"validation_card_visible": False, "error": html192},
    }
    trusted = int(summary.get("trusted_records", 0) or 0)
    blockers: list[str] = []
    if not stale.get("old_summary_marked_stale"):
        blockers.append("old_summary_not_marked_stale")
    if summary.get("active_summary_uses_stale_polluted_source") is True:
        blockers.append("active_summary_uses_stale_polluted_source")
    if summary.get("date_filter_field") != "match_date":
        blockers.append("active_summary_not_match_date")
    if not summary.get("source_files"):
        blockers.append("missing_source_files")
    if summary.get("brief_used_for_hit_rate") is not False:
        blockers.append("brief_used_for_hit_rate_not_false")
    if summary.get("c_observation_active") is not False:
        blockers.append("c_observation_active")
    if summary.get("last_7d_active") is not False:
        blockers.append("last_7d_active")
    if trusted > 0 and bodies["file"].get("cumulative_all_na"):
        blockers.append("trusted_records_gt_zero_but_dashboard_cumulative_all_na")
    if trusted <= 0 and not bodies["file"].get("na_reason_visible"):
        blockers.append("no_trusted_history_without_reason")
    for label, body in bodies.items():
        for key in ["validation_card_visible", "yesterday_visible", "cumulative_visible", "row_A_visible", "row_B_visible", "row_AB_visible"]:
            if not body.get(key):
                blockers.append(f"{label}_{key}_false")
        if body.get("c_validation_visible"):
            blockers.append(f"{label}_c_validation_visible")
        if body.get("last_7d_visible"):
            blockers.append(f"{label}_last_7d_visible")
        if body.get("fake_zero_percent"):
            blockers.append(f"{label}_fake_zero_percent")
        if body.get("v2_visible"):
            blockers.append(f"{label}_v2_visible")
        if body.get("v33_visible"):
            blockers.append(f"{label}_v33_visible")
        if body.get("brief_used_for_hit_rate_text_true"):
            blockers.append(f"{label}_brief_used_for_hit_rate_true")
    out = {
        "checker": "tools/check_v4_match_date_validation_history_recovery.py",
        "phase": "V4-MATCH-DATE-VALIDATION-HISTORY-RECOVERY-20260523",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "summary_exists": bool(summary),
        "old_summary_marked_stale": bool(stale.get("old_summary_marked_stale")),
        "active_summary_uses_stale_polluted_source": bool(summary.get("active_summary_uses_stale_polluted_source")),
        "active_summary_uses_match_date": summary.get("date_filter_field") == "match_date",
        "source_files_present": bool(summary.get("source_files")),
        "trusted_records": trusted,
        "unresolved_records": int(summary.get("unresolved_records", 0) or 0),
        "brief_used_for_hit_rate": bool(summary.get("brief_used_for_hit_rate")),
        "c_observation_active": bool(summary.get("c_observation_active")),
        "last_7d_active": bool(summary.get("last_7d_active")),
        "validation_card_visible": bodies["file"].get("validation_card_visible"),
        "cumulative_all_na": bodies["file"].get("cumulative_all_na"),
        "na_reason_visible": bodies["file"].get("na_reason_visible"),
        "http_127_code": code127,
        "http_192_code": code192,
        "served_html_checked": code127 == 200 and code192 == 200,
        "capture_ran": bool(dry.get("capture_ran") or apply.get("capture_ran")),
        "QQ_push": bool(dry.get("QQ_push") or apply.get("QQ_push")),
        "cloud_publish": bool(dry.get("cloud_publish") or apply.get("cloud_publish")),
        "blockers": sorted(set(blockers)),
        "body_results": bodies,
    }
    (STATUS / "check_v4_match_date_validation_history_recovery_result_20260523.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
