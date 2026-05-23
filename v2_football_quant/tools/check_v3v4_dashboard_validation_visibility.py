#!/usr/bin/env python3
"""Check that V3/V4 dashboard validation card is visible even when data is N/A."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DASH = ROOT / "data/runtime/dashboard/intel_ops_console.html"
DATE = "20260523"
TZ = timezone(timedelta(hours=8))


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def curl(url: str) -> tuple[int, str]:
    out = Path("/tmp/v3v4_validation_visibility.html")
    try:
        r = subprocess.run(["curl", "-sS", "-L", "--max-time", "3", "-w", "\n%{http_code}", "-o", str(out), url], cwd=str(ROOT), text=True, capture_output=True, timeout=6)
        code = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "000"
        return int(code) if code.isdigit() else 0, out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""
    except Exception:
        return 0, ""


def validation_card(html: str) -> str:
    m = re.search(r'<section class="panel validation-panel[^>]*>(.*?)</section>', html, flags=re.S)
    return m.group(1) if m else ""


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def check_html(label: str, html: str, blockers: list[str]) -> dict[str, Any]:
    card = validation_card(html)
    text = strip_tags(card)
    exists = bool(card)
    validation_grid = 'class="validation-grid"' in card
    y_visible = "昨日验证" in card
    c_visible = "累计验证" in card
    row_a = bool(re.search(r"<span>A</span>\s*<b>(?:N/A|\d+/\d+ · [^<]+)</b>", card))
    row_b = bool(re.search(r"<span>B</span>\s*<b>(?:N/A|\d+/\d+ · [^<]+)</b>", card))
    row_ab = bool(re.search(r"<span>A\+B</span>\s*<b>(?:N/A|\d+/\d+ · [^<]+)</b>", card))
    na_visible = "N/A" in card
    reason_visible = any(token in card for token in ["赛果数据未就绪", "样本不足", "等待赛果", "match_date attribution 历史恢复", "暂无可信已结算样本"])
    audit = 'class="validation-audit"' in card and "source_files=" in card
    forbidden = []
    for token in ["C观察", "C级观察", "近7天验证", "V2 active", "BET_LOCKED", "V33 active"]:
        if token in card or token in html:
            forbidden.append(token)
    fake_zero = bool(re.search(r"(?<!\d)0\.0%", card))
    if not exists:
        blockers.append(f"{label}_validation_card_missing")
    if not validation_grid:
        blockers.append(f"{label}_validation_grid_missing")
    if not y_visible:
        blockers.append(f"{label}_yesterday_missing")
    if not c_visible:
        blockers.append(f"{label}_cumulative_missing")
    if not row_a:
        blockers.append(f"{label}_row_A_missing")
    if not row_b:
        blockers.append(f"{label}_row_B_missing")
    if not row_ab:
        blockers.append(f"{label}_row_AB_missing")
    if not na_visible:
        blockers.append(f"{label}_na_missing")
    if not reason_visible:
        blockers.append(f"{label}_reason_missing")
    if not audit:
        blockers.append(f"{label}_audit_missing")
    if forbidden:
        blockers.append(f"{label}_forbidden_visible:{','.join(forbidden)}")
    if fake_zero:
        blockers.append(f"{label}_fake_zero_percent")
    return {
        "validation_card_visible": exists,
        "validation_grid": validation_grid,
        "yesterday_visible": y_visible,
        "cumulative_visible": c_visible,
        "row_A_visible": row_a,
        "row_B_visible": row_b,
        "row_AB_visible": row_ab,
        "na_visible": na_visible,
        "reason_visible": reason_visible,
        "audit_visible": audit,
        "fake_zero_percent": fake_zero,
        "text": text[:500],
    }


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    html = DASH.read_text(encoding="utf-8", errors="replace") if DASH.exists() else ""
    code127, body127 = curl("http://127.0.0.1:8765/intel_ops_console.html")
    code192, body192 = curl("http://192.168.1.2:8765/intel_ops_console.html")
    bodies = [("file", html)]
    if code127 == 200:
        bodies.append(("127", body127))
    else:
        blockers.append(f"http_127_not_200:{code127}")
    if code192 == 200:
        bodies.append(("192", body192))
    else:
        warnings.append(f"http_192_not_200:{code192}")
    body_results = {label: check_html(label, text, blockers) for label, text in bodies}
    summary = load(STATUS / f"v3v4_validation_summary_{DATE}.json")
    active = summary.get("dashboard_active", {}) if isinstance(summary.get("dashboard_active"), dict) else {}
    if not isinstance(active.get("yesterday"), dict):
        blockers.append("summary_yesterday_missing")
    if not isinstance(active.get("cumulative"), dict):
        blockers.append("summary_cumulative_missing")
    if summary.get("brief_used_for_hit_rate") is not False:
        blockers.append("brief_used_for_hit_rate_not_false")
    if summary.get("c_observation_active") is not False:
        blockers.append("c_observation_active_not_false")
    if summary.get("last_7d_active") is not False:
        blockers.append("last_7d_active_not_false")
    source_files = summary.get("source_files") if isinstance(summary.get("source_files"), list) else []
    if not source_files:
        blockers.append("summary_source_files_missing")
    status = "BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS")
    first = body_results.get("file", {})
    out = {
        "checker": "tools/check_v3v4_dashboard_validation_visibility.py",
        "phase": "V3V4-DASHBOARD-VALIDATION-VISIBILITY-RECOVERY-20260523",
        "generated_at": datetime.now(TZ).isoformat(),
        "conclusion": status,
        "http_127_code": code127,
        "http_192_code": code192,
        "validation_card_visible": first.get("validation_card_visible"),
        "yesterday_visible": first.get("yesterday_visible"),
        "cumulative_visible": first.get("cumulative_visible"),
        "validation_layout": "two_column" if first.get("validation_grid") else "missing",
        "validation_display_mode": "na" if first.get("na_visible") else "data",
        "reason_visible": first.get("reason_visible"),
        "api_disabled": bool(summary.get("old_summary_marked_stale")) or "API" in str(summary.get("validation_source_status") or ""),
        "brief_used_for_hit_rate": summary.get("brief_used_for_hit_rate"),
        "c_validation_visible": False,
        "last_7d_visible": False,
        "served_html_checked": code127 == 200 or code192 == 200,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "blockers": blockers,
        "warnings": warnings,
        "body_results": body_results,
    }
    (STATUS / f"check_v3v4_dashboard_validation_visibility_result_{DATE}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
