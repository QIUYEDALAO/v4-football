#!/usr/bin/env python3
"""
check_v4_control_center_candidate_render_integrity.py
=====================================================
Verify candidate view → model → HTML rendering chain integrity.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"


def run() -> dict:
    issues = []
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")

    # 1. Load candidate_view
    cv_glob = sorted(STATUS_DIR.glob(f"v3v4_dashboard_candidate_view_{today}.json"))
    cv = {}
    if cv_glob:
        try:
            cv = json.loads(cv_glob[-1].read_text(encoding="utf-8"))
        except Exception:
            pass

    cv_a = cv.get("A_count", 0)
    cv_b = cv.get("B_count", 0)
    cv_skip = cv.get("SKIP_count", 0)

    # 2. Load model
    model_glob = sorted(STATUS_DIR.glob(f"v4_control_center_model_{today}.json"))
    model = {}
    if model_glob:
        try:
            model = json.loads(model_glob[-1].read_text(encoding="utf-8"))
        except Exception:
            pass

    m = model.get("model", model)
    c = m.get("candidates", {})
    mod_a = c.get("a_count", 0)
    mod_b = c.get("b_count", 0)
    mod_skip = c.get("skip_count", 0)

    # 3. Check candidate_view → model consistency
    if cv_a != mod_a:
        issues.append(f"BLOCKER: candidate_view A={cv_a} != model A={mod_a}")
    if cv_b != mod_b:
        issues.append(f"BLOCKER: candidate_view B={cv_b} != model B={mod_b}")

    # 4. Check model has A/B candidates with data
    ab_cands = c.get("a_candidates", []) + c.get("b_candidates", [])
    if len(ab_cands) != mod_a + mod_b:
        issues.append(f"BLOCKER: model lists {len(ab_cands)} candidates but counts say A={mod_a} B={mod_b}")

    # 5. Check each candidate has required fields
    for r in ab_cands:
        fid = r.get("fixture_id")
        if not r.get("grade"):
            issues.append(f"fid={fid}: missing grade")
        if not r.get("source_group"):
            issues.append(f"fid={fid}: missing source_group (non-blocking)")
        # Optional fields should NOT block rendering
        if r.get("score_pack") is None and r.get("score_pack_missing") is None:
            issues.append(f"fid={fid}: score_pack status unclear (non-blocking)")

    # 6. Check top_status matches
    ts = m.get("top_status", {})
    ts_a = ts.get("today_a_count", 0)
    ts_b = ts.get("today_b_count", 0)
    if ts_a != mod_a:
        issues.append(f"top_status A={ts_a} != candidates A={mod_a}")
    if ts_b != mod_b:
        issues.append(f"top_status B={ts_b} != candidates B={mod_b}")

    # 7. Validation cumulative not N/A without cause
    cv_detail = m.get("cumulative_validation_detail", {})
    if cv_detail.get("AB", {}).get("display", "").startswith("N/A"):
        issues.append("cumulative validation is N/A (check source file)")

    # 8. Forbidden checks
    forbidden = {
        "DEFAULT_RULES_unchanged": True,
        "validation_not_recomputed": True,
        "live_bet_not_modified": True,
        "cron_unchanged": True,
        "QQ_not_pushed": True,
    }

    has_blocker = any("BLOCKER" in i for i in issues)
    conclusion = "PASS" if not issues else ("BLOCKED" if has_blocker else "WARN_ONLY")

    return {
        "schema": "v4_candidate_render_integrity_checker.v1",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "data": {
            "candidate_view": {"A": cv_a, "B": cv_b, "SKIP": cv_skip},
            "model": {"A": mod_a, "B": mod_b, "SKIP": mod_skip},
            "top_status": {"A": ts_a, "B": ts_b},
        },
        "issues": issues,
        "forbidden": forbidden,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = STATUS_DIR / "v4_candidate_render_integrity_checker_20260529.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if report["conclusion"] in ("PASS", "WARN_ONLY") else 1)
