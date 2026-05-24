#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DASH = ROOT / "data/runtime/dashboard"
TZ = timezone(timedelta(hours=8))
DATE = datetime.now(TZ).strftime("%Y%m%d")


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def count_english_match_lines(html: str) -> int:
    count = 0
    for m in re.finditer(r'<div class="(?:team|match-line)">([^<]+?)\s+vs\s+([^<]+?)</div>', html):
        a = m.group(1).strip()
        b = m.group(2).strip()
        if a.startswith("中文名缺失：") or b.startswith("中文名缺失："):
            continue
        if re.fullmatch(r"[A-Za-z0-9 .\-'/&]+", a) and re.fullmatch(r"[A-Za-z0-9 .\-'/&]+", b):
            count += 1
    return count


def main() -> int:
    blockers = []
    warnings = []

    main_html_path = DASH / "intel_ops_console.html"
    out_html_path = DASH / "outside_57_observation.html"
    main_html = main_html_path.read_text(encoding="utf-8", errors="replace") if main_html_path.exists() else ""
    out_html = out_html_path.read_text(encoding="utf-8", errors="replace") if out_html_path.exists() else ""

    main_eng = count_english_match_lines(main_html)
    out_eng = count_english_match_lines(out_html)
    if main_eng > 0:
        blockers.append(f"main_dashboard_english_lines:{main_eng}")
    if out_eng > 0:
        blockers.append(f"outside_57_english_lines:{out_eng}")

    cv = load(STATUS / "v3v4_dashboard_candidate_view_20260524.json")
    missing_cv = 0
    total_cv = 0
    for bucket in ("A_candidates", "B_candidates", "C_candidates", "SKIP_candidates"):
        rows = cv.get(bucket, []) if isinstance(cv, dict) else []
        if not isinstance(rows, list):
            continue
        for row in rows:
            total_cv += 1
            if not row.get("home_team_cn") or not row.get("away_team_cn"):
                if not row.get("team_cn_missing"):
                    blockers.append(f"candidate_missing_cn_without_flag:{row.get('fixture_id')}")
                missing_cv += 1

    op = load(STATUS / "v4_outside_57_observation_pool_20260525.json")
    fixtures = op.get("fixtures", []) if isinstance(op, dict) else []
    missing_out = 0
    for row in fixtures if isinstance(fixtures, list) else []:
        if not row.get("home_team_cn") or not row.get("away_team_cn"):
            if not row.get("team_cn_missing"):
                blockers.append(f"outside_missing_cn_without_flag:{row.get('fixture_id')}")
            missing_out += 1

    missing_list = load(STATUS / "missing_team_cn_20260525.json")
    if not isinstance(missing_list, dict) or "missing_rows" not in missing_list:
        blockers.append("missing_team_cn_list_missing")

    # Governance
    if "V2" in main_html or "V33" in main_html:
        blockers.append("v2_v33_visible_in_main")
    if "V2" in out_html or "V33" in out_html:
        blockers.append("v2_v33_visible_in_outside")

    result = {
        "checker": "tools/check_v3v4_team_cn_display_full.py",
        "phase": "V3V4-INTEL-CENTER-TEAM-CN-DISPLAY-FULL-FIX-20260525",
        "date": DATE,
        "english_main_card_guard": main_eng == 0 and out_eng == 0,
        "main_dashboard_english_visible_count": main_eng,
        "outside_57_english_visible_count": out_eng,
        "candidate_total": total_cv,
        "candidate_missing_cn_count": missing_cv,
        "outside_total": len(fixtures) if isinstance(fixtures, list) else 0,
        "outside_missing_cn_count": missing_out,
        "missing_team_cn_list_exists": isinstance(missing_list, dict) and "missing_rows" in missing_list,
        "blockers": blockers,
        "warnings": warnings,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    out = STATUS / f"check_v3v4_team_cn_display_full_result_{DATE}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
