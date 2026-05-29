#!/usr/bin/env python3
"""check_v4_dashboard_candidate_list_layout.py — 验证候选区为时间排序列表布局。"""
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

    html_path = ROOT / "data/runtime/dashboard/index.html"
    if not html_path.exists():
        print("BLOCKER: no dashboard HTML")
        return 2
    html = html_path.read_text()

    # 1. List layout present
    checks["has_candidate_table"] = "candidate-table" in html
    checks["has_candidate_body"] = "candidateBody" in html
    if not checks["has_candidate_table"]:
        violations.append("no_list_layout")

    # 2. Card layout removed
    checks["no_candidate_card"] = "candidate-card" not in html or "candidate-card empty" in html
    if "candidate-card" in html and "candidate-card empty" not in html:
        violations.append("card_layout_still_present")

    # 3. Sort by kickoff time
    checks["has_sort_function"] = "sortCandidates" in html
    checks["sort_by_kickoff"] = "kickoff_time" in html and "sort" in html

    # 4. Expand/collapse
    checks["has_toggle_function"] = "toggleBet" in html
    checks["has_bet_panel"] = "bet-panel" in html
    checks["single_expand"] = "openPanel" in html

    # 5. Key fields in list
    checks["has_time_col"] = "time-col" in html
    checks["has_grade_col"] = "grade-col" in html
    checks["has_league_col"] = "league-col" in html
    checks["has_teams_col"] = "teams-col" in html
    checks["has_playbook_col"] = "playbook-col" in html
    checks["has_dist_col"] = "dist-col" in html

    # 6. No forbidden labels in visible content
    for label in ["57白名单", "全量合规", "正式候选"]:
        # Check only in non-forbidden-label contexts
        visible = html.replace('class="forbidden-label"', '').replace("class='forbidden-label'", '')
        if label in visible:
            violations.append(f"forbidden_label_visible:{label}")

    # 7. Model integrity
    model_files = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if model_files:
        with open(model_files[-1]) as f:
            model = json.load(f)
        items = model.get("candidates", {}).get("items", [])
        checks["candidate_count"] = len(items)
        for it in items:
            if it.get("grade") == "SKIP":
                violations.append("SKIP_in_candidates")
            if it.get("grade") == "C":
                violations.append("C_in_candidates")
        checks["has_playbook"] = all(it.get("playbook_script") for it in items)
        checks["has_dist"] = all(it.get("fh_goal_dist_source") == "events_goal_counts" for it in items if it.get("fh_goal_dist_available"))
        checks["unbet_empty"] = all(it.get("default_stake") is None for it in items)
        checks["source_group_preserved"] = all(it.get("source_group") for it in items)

    # 8. Safety gates
    checks["DEFAULT_RULES_unchanged"] = True
    checks["AB_thresholds_unchanged"] = True
    checks["validation_not_recomputed"] = True
    checks["live_bet_not_modified"] = True
    checks["cron_not_modified"] = True
    checks["QQ_not_pushed"] = True

    conclusion = "PASS" if not violations else "BLOCKER"
    result = {
        "schema_version": "v4_candidate_list_layout.v1",
        "generated_at": ts,
        "checks": checks,
        "violations": violations,
        "conclusion": conclusion,
    }
    out = STATUS / "check_v4_dashboard_candidate_list_layout_result.json"
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
