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


def english_main_lines(html: str) -> int:
    c = 0
    for m in re.finditer(r'<div class="(?:match-line|team)">([^<]+?)\s+vs\s+([^<]+?)</div>', html):
        a, b = m.group(1).strip(), m.group(2).strip()
        if a.startswith("中文名缺失：") or b.startswith("中文名缺失："):
            continue
        if re.fullmatch(r"[A-Za-z0-9 .'/&-]+", a) and re.fullmatch(r"[A-Za-z0-9 .'/&-]+", b):
            c += 1
    return c


def main() -> int:
    blockers = []
    warnings = []

    alias = ROOT / "data/config/team_cn_aliases.json"
    resolver = ROOT / "tools/team_cn_resolver.py"
    if not alias.exists():
        blockers.append("alias_file_missing")
    if not resolver.exists():
        blockers.append("resolver_missing")

    cv = load(STATUS / "v3v4_dashboard_candidate_view_20260524.json")
    cv_ok = True
    for k in ("A_candidates", "B_candidates", "C_candidates", "SKIP_candidates"):
        rows = cv.get(k, []) if isinstance(cv, dict) else []
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not (r.get("home_team_cn") and r.get("away_team_cn")) and not r.get("team_cn_missing"):
                cv_ok = False
                blockers.append(f"candidate_no_cn_no_missing:{r.get('fixture_id')}")
                break
    op = load(STATUS / "v4_outside_57_observation_pool_20260525.json")
    rows = op.get("fixtures", []) if isinstance(op, dict) else []
    out_ok = True
    if isinstance(rows, list):
        for r in rows:
            if not (r.get("home_team_cn") and r.get("away_team_cn")) and not r.get("team_cn_missing"):
                out_ok = False
                blockers.append(f"outside57_no_cn_no_missing:{r.get('fixture_id')}")
                break

    main_html = (DASH / "intel_ops_console.html").read_text(encoding="utf-8", errors="replace") if (DASH / "intel_ops_console.html").exists() else ""
    out_html = (DASH / "outside_57_observation.html").read_text(encoding="utf-8", errors="replace") if (DASH / "outside_57_observation.html").exists() else ""
    main_eng = english_main_lines(main_html)
    out_eng = english_main_lines(out_html)
    if main_eng > 0:
        blockers.append(f"main_english_fallback:{main_eng}")
    if out_eng > 0:
        blockers.append(f"outside_english_fallback:{out_eng}")

    missing_path = STATUS / "missing_team_cn_20260525.json"
    if not missing_path.exists():
        blockers.append("missing_team_cn_file_missing")

    runner_text = (ROOT / "tools/run_v3v4_dashboard_daily_update.py").read_text(encoding="utf-8", errors="replace")
    if "enrich_team_cn(" not in runner_text:
        blockers.append("runner_not_call_team_cn_enrich")

    if "EN:" not in out_html:
        warnings.append("outside57_no_en_audit_line")

    result = {
        "checker": "tools/check_v3v4_team_cn_pipeline_persistent.py",
        "phase": "V3V4-TEAM-CN-PERSISTENT-PIPELINE-FIX-20260525",
        "date": DATE,
        "alias_file_exists": alias.exists(),
        "resolver_exists": resolver.exists(),
        "candidate_cn_fields_ok": cv_ok,
        "outside57_cn_fields_ok": out_ok,
        "main_english_fallback_count": main_eng,
        "outside_english_fallback_count": out_eng,
        "missing_team_cn_file_exists": missing_path.exists(),
        "runner_calls_team_cn_enrich": "enrich_team_cn(" in runner_text,
        "blockers": blockers,
        "warnings": warnings,
        "conclusion": "BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS"),
    }
    out = STATUS / f"check_v3v4_team_cn_pipeline_persistent_result_{DATE}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
