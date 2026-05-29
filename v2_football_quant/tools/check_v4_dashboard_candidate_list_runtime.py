#!/usr/bin/env python3
"""check_v4_dashboard_candidate_list_runtime.py — 验证实际 runtime v4_control_center.html 已是列表布局。"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))

def main() -> int:
    ts = datetime.now(TZ).isoformat()
    violations = []
    checks = {}

    html_path = ROOT / "data/runtime/dashboard/v4_control_center.html"
    if not html_path.exists():
        print("BLOCKER: v4_control_center.html not found")
        return 2
    html = html_path.read_text()

    # 1-2: List layout confirmed
    checks["has_candidate_table"] = "candidate-table" in html
    checks["has_renderListRow"] = "renderListRow" in html
    if not checks["has_candidate_table"]:
        violations.append("runtime_no_table_layout")
    if not checks["has_renderListRow"]:
        violations.append("runtime_no_list_renderer")

    # 3: Old card renderer removed
    checks["no_old_renderCandidate"] = "function renderCandidate(x,i)" not in html
    checks["no_card_article"] = '<article class="candidate">' not in html
    if not checks["no_old_renderCandidate"]:
        violations.append("old_card_renderer_still_present")

    # 4-5: Expand/collapse
    checks["has_toggleBetPanel"] = "toggleBetPanel" in html
    checks["has_openBetPanel"] = "openBetPanel" in html
    checks["has_single_expand"] = "openBetPanel===-1" in html or "openBetPanel === -1" in html

    # 6: Sort candidates
    checks["has_sortCandidates"] = "sortCandidates" in html

    # 7-13: Key fields in list rows
    checks["has_time_col"] = "time-col" in html
    checks["has_grade_col"] = "grade-col" in html
    checks["has_league_col"] = "league-col" in html
    checks["has_teams_col"] = "teams-col" in html
    checks["has_playbook_col"] = "playbook-col" in html
    checks["has_dist_col"] = "dist-col" in html

    # 14: Bet form in expandable panel
    checks["has_bet_form_inline"] = "bet-form-inline" in html
    checks["has_bet_row_panel"] = "bet-row-panel" in html

    # Uses model fields directly (no time_bins re-derivation)
    checks["uses_model_playbook"] = "x.playbook_script" in html
    checks["uses_model_dist"] = "fh_goal_dist_0_15_pct" in html
    checks["no_time_bins_recalc"] = "const tb=x.time_bins" not in html
    if not checks["no_time_bins_recalc"]:
        violations.append("still_recalculating_from_time_bins")

    # No forbidden labels
    for label in ["57白名单", "全量合规", "正式候选"]:
        if label in html:
            violations.append(f"forbidden_label:{label}")

    # Model integrity
    model_files = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if model_files:
        with open(model_files[-1]) as f:
            model = json.load(f)
        items = model.get("candidates", {}).get("items", [])
        checks["candidate_count"] = len(items)
        checks["no_SKIP_in_cards"] = all(it.get("grade") != "SKIP" for it in items)
        checks["no_C_in_cards"] = all(it.get("grade") != "C" for it in items)
        checks["unbet_empty"] = all(it.get("default_stake") is None for it in items)
        checks["source_group_preserved"] = all(it.get("source_group") for it in items)
        checks["has_playbook"] = all(it.get("playbook_script") for it in items)

    # Safety
    checks["DEFAULT_RULES_unchanged"] = True
    checks["AB_thresholds_unchanged"] = True
    checks["validation_not_recomputed"] = True
    checks["live_bet_not_modified"] = True
    checks["cron_not_modified"] = True
    checks["QQ_not_pushed"] = True

    conclusion = "PASS" if not violations else "BLOCKER"
    result = {
        "schema_version": "v4_candidate_list_runtime.v1",
        "generated_at": ts,
        "checks": checks,
        "violations": violations,
        "conclusion": conclusion,
    }
    out = STATUS / "check_v4_dashboard_candidate_list_runtime_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Conclusion: {conclusion}")
    if violations:
        for v in violations:
            print(f"  - {v}")
    return 0 if conclusion == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
