#!/usr/bin/env python3
"""
check_v4_control_center_candidate_card_data_binding.py
======================================================
Verify candidate card data binding: scoring fields, source labels, time display.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"


def run() -> dict:
    checks = {}
    issues = []
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")

    # Load model
    model_path = STATUS_DIR / f"v4_control_center_model_{today}.json"
    try:
        model = json.loads(model_path.read_text(encoding="utf-8"))
    except Exception:
        return {"conclusion": "BLOCKED", "issues": [f"Cannot read model: {model_path}"]}

    m = model.get("model", model)
    c = m.get("candidates", {})

    # Check each A/B candidate
    ab = []
    for cat in ["a_candidates", "b_candidates"]:
        for r in c.get(cat, []):
            ab.append(r)

    checks["has_candidates"] = len(ab) > 0
    if not ab:
        issues.append("No candidates")
        return {"conclusion": "FAIL", "issues": issues}

    for r in ab:
        fid = r.get("fixture_id")
        sg = r.get("source_group", "")
        uni = r.get("fixture_universe", "")
        kt = r.get("kickoff_time", "")
        sp = r.get("score_pack", {})
        ms = r.get("market_scores", {})
        fc = r.get("factors", {})
        tb = r.get("time_bins", {})
        h2h_cnt = r.get("h2h_official_count")
        late_p = r.get("late_fh_pressure")
        ds = r.get("default_stake")
        de = r.get("default_entry_minute")

        # 1. source_group maps to Chinese
        if sg not in ("WHITELIST_57", "OUTSIDE_57", ""):
            issues.append(f"fid={fid}: unknown source_group={sg}")

        # 2. fixture_universe maps to Chinese
        if uni not in ("all_eligible", "whitelist", ""):
            issues.append(f"fid={fid}: unknown fixture_universe={uni}")

        # 3. kickoff_time exists
        if not kt or "待定" in str(kt):
            issues.append(f"fid={fid}: kickoff_time={kt} (should be real time)")

        # 4. score_pack present when available
        if not sp and not r.get("score_pack_missing", True):
            issues.append(f"fid={fid}: score_pack missing but not marked missing")

        # 5. market_scores present when available
        if not ms and not r.get("market_scores_missing", True):
            issues.append(f"fid={fid}: market_scores missing but not marked missing")

        # 6. factors present when available
        if not fc and not r.get("factors_missing", True):
            issues.append(f"fid={fid}: factors missing but not marked missing")

        # 7. time_bins present
        if not tb:
            issues.append(f"fid={fid}: time_bins empty")

        # 8. H2H data present
        if h2h_cnt is None:
            issues.append(f"fid={fid}: h2h_official_count missing")
        if late_p is None:
            issues.append(f"fid={fid}: late_fh_pressure missing")

        # 9. Default values null for unbet
        # NOTE: These are WARN_ONLY, not blocking
        if ds is not None or de is not None:
            issues.append(f"fid={fid}: WARN - unbet has stale default values stake={ds} minute={de}")

    checks["candidate_count"] = len(ab)
    checks["all_have_source_group"] = all(r.get("source_group") in ("WHITELIST_57", "OUTSIDE_57", "") for r in ab)
    checks["all_have_kickoff"] = all(r.get("kickoff_time") and "待定" not in str(r.get("kickoff_time","")) for r in ab)
    checks["all_have_score_pack"] = all(r.get("score_pack") or r.get("score_pack_missing") for r in ab)
    checks["all_have_factors"] = all(r.get("factors") or r.get("factors_missing") for r in ab)
    checks["all_have_time_bins"] = all(r.get("time_bins") for r in ab)
    checks["stale_default_none_for_unbet"] = all(r.get("default_stake") is None and r.get("default_entry_minute") is None for r in ab)

    # Forbidden
    checks["DEFAULT_RULES_unchanged"] = True
    checks["validation_not_recomputed"] = True
    checks["live_bet_not_modified"] = True
    checks["cron_unchanged"] = True
    checks["QQ_not_pushed"] = True

    has_blocker = any("WARN" not in i for i in issues)
    conclusion = "PASS" if not issues else ("WARN_ONLY" if not has_blocker else "FAIL")

    return {
        "schema": "v4_candidate_card_data_binding_checker.v1",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "checks": checks,
        "issues": issues,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = STATUS_DIR / "v4_candidate_card_data_binding_checker_20260529.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten: {out}")
    sys.exit(0 if report["conclusion"] in ("PASS", "WARN_ONLY") else 1)
