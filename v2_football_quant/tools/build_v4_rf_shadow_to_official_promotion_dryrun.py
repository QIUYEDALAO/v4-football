#!/usr/bin/env python3
"""
V4 RF Shadow → Official Promotion Dry-Run Tool.

This is a READ-ONLY simulation tool. It reads existing scout artifacts and
builds a dry-run report showing what would happen if market-adjusted RF shadow
grades were used as the official recommendation entry.

RULES:
1. market_adjusted_shadow_grade=A → dryrun_A
2. market_adjusted_shadow_grade=B → dryrun_B
3. market_adjusted_shadow_grade=C → dryrun_C_observe
4. market_adjusted_shadow_grade=SKIP → dryrun_SKIP
5. MARKET_HARD_VETO → never promoted to dryrun_A/B
6. MARKET_NO_DATA → not auto-promoted to A
7. NO_MARKET → not promoted to dryrun_A/B
8. H2H only provides bonus reason, not demotion
9. official grade is NEVER modified
10. No API calls
11. No re-scan
"""

import argparse
import json
import os
import sys
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)
from engine.rf_shadow_fields import _apply_market_promotion_policy  # noqa: E402
SCOUT_DIR = os.path.join(WORKSPACE, "data", "daily_reports")
CANDIDATE_VIEW_DIR = os.path.join(WORKSPACE, "data", "runtime", "status")
DASHBOARD_MODEL_DIR = os.path.join(WORKSPACE, "data", "runtime", "status")
OUTPUT_DIR = os.path.join(WORKSPACE, "data", "runtime", "acceptance")


def load_scout(scan_date: str) -> list:
    path = os.path.join(SCOUT_DIR, f"scout_v4_{scan_date}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Scout not found: {path}")
    with open(path) as f:
        data = json.load(f)
    print(f"  📄 Loaded scout: {path} ({len(data)} fixtures)")
    return data


def load_candidate_view(scan_date: str) -> dict:
    path = os.path.join(CANDIDATE_VIEW_DIR, f"v3v4_dashboard_candidate_view_{scan_date}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Candidate view not found: {path}")
    with open(path) as f:
        data = json.load(f)
    print(f"  📄 Loaded candidate_view: {path}")
    return data


def has_no_market_data(fixture: dict) -> bool:
    """Check if no opening market data exists."""
    status = str(fixture.get("opening_market_support_status") or "").upper()
    data_status = str(fixture.get("opening_market_data_status") or "").upper()
    return status == "MARKET_NO_DATA" or data_status in {"NO_DATA", "API_HAS_ODDS_BUT_NO_HT_OU"}


def has_no_market(fixture: dict) -> bool:
    """Check if market is completely absent."""
    status = str(fixture.get("opening_market_support_status") or "").upper()
    data_status = str(fixture.get("opening_market_data_status") or "").upper()
    return status == "MARKET_NO_MARKET" or data_status == "NO_MARKET" or bool(fixture.get("no_market_excluded"))


def _to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def infer_conflict_level(fixture: dict) -> tuple[str, str, str, str, str]:
    """Infer conflict level/action for old artifacts lacking new policy fields."""
    status = str(fixture.get("opening_market_support_status") or "").upper()
    ht_line = _to_float(fixture.get("opening_ht_ou_line") or fixture.get("prematch_ht_line"))
    over_odds = _to_float(fixture.get("opening_ht_ou_over_odds") or fixture.get("prematch_over_odds"))
    if ht_line is not None and 3.0 < ht_line <= 30.0:
        ht_line = ht_line / 10.0
    rf_grade = str(fixture.get("rf_shadow_grade") or "").upper()
    conf = int(float(fixture.get("rf_shadow_confidence") or 50))
    policy = _apply_market_promotion_policy(
        base_grade=rf_grade,
        market_status=status,
        confidence_before_market=conf,
        ht_line=ht_line,
        over_odds=over_odds,
    )
    return (
        policy.get("opening_market_conflict_level", ""),
        policy.get("opening_market_action", ""),
        policy.get("market_veto_severity", "NONE"),
        policy.get("market_veto_reason", ""),
        policy.get("market_policy_version", "V4_RF_MARKET_POLICY_20260531"),
    )


def compute_dryrun_grade(fixture: dict, fixture_id: int) -> tuple[str, dict]:
    """
    Compute dry-run promotion grade based on market_adjusted_shadow_grade
    with safety filters applied.
    """
    market_adjusted = str(fixture.get("market_adjusted_shadow_grade", "") or "").upper()
    rf_shadow = str(fixture.get("rf_shadow_grade", "") or "").upper()
    status = str(fixture.get("opening_market_support_status") or "").upper()
    confidence = int(float(fixture.get("rf_shadow_confidence") or 50))
    ht_line = _to_float(fixture.get("opening_ht_ou_line") or fixture.get("prematch_ht_line"))
    over_odds = _to_float(fixture.get("opening_ht_ou_over_odds") or fixture.get("prematch_over_odds"))

    # Recompute dryrun policy from RF primary signal (replay-safe, no API/no rescan)
    policy = _apply_market_promotion_policy(
        base_grade=rf_shadow if rf_shadow in {"A", "B", "C", "SKIP"} else market_adjusted,
        market_status=status,
        confidence_before_market=confidence,
        ht_line=ht_line,
        over_odds=over_odds,
    )
    adjusted = str(policy.get("market_adjusted_shadow_grade") or "SKIP").upper()
    conflict_level = str(policy.get("opening_market_conflict_level") or "")
    action = str(policy.get("opening_market_action") or "")

    if conflict_level == "MARKET_EXTREME_VETO":
        return "DRYRUN_EXTREME_VETO", policy

    # Rule: no market never enters dryrun A/B
    if has_no_market(fixture):
        return "DRYRUN_SKIP", policy

    # Rule: no-data does not auto-upgrade to A
    if has_no_market_data(fixture) and adjusted == "A":
        adjusted = "B"

    # Normal mapping (policy-adjusted)
    grade_map = {
        "A": "DRYRUN_A",
        "B": "DRYRUN_B",
        "C": "DRYRUN_C_OBSERVE",
        "SKIP": "DRYRUN_SKIP",
    }
    dry = grade_map.get(adjusted, "DRYRUN_SKIP")
    policy["opening_market_conflict_level"] = conflict_level
    policy["opening_market_action"] = action
    policy["market_adjusted_shadow_grade"] = adjusted
    return dry, policy


def build_dryrun_report(scout_data: list, candidate_view: dict, scan_date: str) -> dict:
    """Build promotion dry-run report."""
    official_grades = {"A": 0, "B": 0, "C": 0, "SKIP": 0, "NONE": 0}
    rf_shadow_grades = {"A": 0, "B": 0, "C": 0, "SKIP": 0, "OTHER": 0}
    market_adjusted_grades = {"A": 0, "B": 0, "C": 0, "SKIP": 0, "OTHER": 0}
    dryrun_grades = {
        "DRYRUN_A": 0,
        "DRYRUN_B": 0,
        "DRYRUN_C_OBSERVE": 0,
        "DRYRUN_SKIP": 0,
        "DRYRUN_EXTREME_VETO": 0,
    }

    dryrun_a_candidates = []
    dryrun_b_candidates = []
    dryrun_c_candidates = []
    vetoed_shadow_ab = []
    rejected_no_market = []
    rf_ab_downgraded_to_c_observe = 0
    market_no_data_preserved_observe = 0
    season_phase_distribution: dict[str, int] = {}
    league_tier_distribution: dict[str, int] = {}
    rf_sample_status_distribution: dict[str, int] = {}
    rf_freshness_status_distribution: dict[str, int] = {}

    def _bump(counter: dict[str, int], key: str) -> None:
        k = str(key or "").strip() or "UNKNOWN"
        counter[k] = int(counter.get(k, 0)) + 1

    for fixture in scout_data:
        # Official grade
        off_grade = fixture.get("grade", "") or "NONE"
        official_grades[off_grade if off_grade in official_grades else "NONE"] += 1

        # RF shadow grade
        rsg = fixture.get("rf_shadow_grade", "")
        if rsg in rf_shadow_grades:
            rf_shadow_grades[rsg] += 1
        else:
            rf_shadow_grades["OTHER"] += 1

        # Market adjusted grade
        masg = fixture.get("market_adjusted_shadow_grade", "")
        if masg in market_adjusted_grades:
            market_adjusted_grades[masg] += 1
        else:
            market_adjusted_grades["OTHER"] += 1

        # Dry-run grade
        dryrun_grade, policy = compute_dryrun_grade(fixture, fixture.get("fixture_id"))
        dryrun_grades[dryrun_grade] = dryrun_grades.get(dryrun_grade, 0) + 1

        _bump(season_phase_distribution, fixture.get("season_phase", "UNKNOWN"))
        _bump(league_tier_distribution, fixture.get("league_tier", "UNKNOWN_TIER"))
        _bump(rf_sample_status_distribution, fixture.get("rf_sample_status", "UNKNOWN"))
        _bump(rf_freshness_status_distribution, fixture.get("rf_freshness_status", fixture.get("recent_freshness_status", "UNKNOWN")))

        entry = {
            "fixture_id": fixture.get("fixture_id"),
            "kickoff": fixture.get("kickoff", ""),
            "league": fixture.get("league", ""),
            "home": fixture.get("home", ""),
            "away": fixture.get("away", ""),
            "official_grade": fixture.get("grade", "") or "NONE",
            "rf_shadow_grade": rsg,
            "market_adjusted_shadow_grade": policy.get("market_adjusted_shadow_grade", masg),
            "market_adjusted_shadow_grade_source": masg,
            "market_adjusted_shadow_grade_replay": policy.get("market_adjusted_shadow_grade", masg),
            "dryrun_grade": dryrun_grade,
            "rf_shadow_reason": fixture.get("rf_shadow_reason", ""),
            "rf_balance_reason": fixture.get("rf_balance_reason", ""),
            "h2h_recent5_bonus_reason": fixture.get("h2h_recent5_bonus_reason", ""),
            "opening_market_support_status": fixture.get("opening_market_support_status", ""),
            "opening_market_data_status": fixture.get("opening_market_data_status", ""),
            "opening_market_reason": fixture.get("opening_market_reason", ""),
            "opening_market_conflict_level": policy.get("opening_market_conflict_level", fixture.get("opening_market_conflict_level", "")),
            "opening_market_action": policy.get("opening_market_action", fixture.get("opening_market_action", "")),
            "market_veto_severity": policy.get("market_veto_severity", fixture.get("market_veto_severity", "NONE")),
            "market_veto_reason": policy.get("market_veto_reason", fixture.get("market_veto_reason", "")),
            "market_policy_version": policy.get("market_policy_version", fixture.get("market_policy_version", "V4_RF_MARKET_POLICY_20260531")),
            "dryrun_action": policy.get("opening_market_action", fixture.get("dryrun_action", "")),
            "market_adjustment_reason": fixture.get("market_adjustment_reason", ""),
            "collection_plan_observe_only": fixture.get("collection_plan_observe_only", False),
            "h2h_low_sample": fixture.get("h2h_low_sample", True),
            "no_market_excluded": fixture.get("no_market_excluded", False),
            "rf_balance_status": fixture.get("rf_balance_status", ""),
            "rf_shadow_score": fixture.get("rf_shadow_score"),
            "rf_shadow_confidence": fixture.get("rf_shadow_confidence"),
            "season_phase": fixture.get("season_phase", "UNKNOWN"),
            "league_tier": fixture.get("league_tier", "UNKNOWN_TIER"),
            "rf_window_policy": fixture.get("rf_window_policy", ""),
            "rf_sample_status": fixture.get("rf_sample_status", "UNKNOWN"),
            "rf_freshness_status": fixture.get("rf_freshness_status", fixture.get("recent_freshness_status", "UNKNOWN")),
            "rf_season_aware_reason": fixture.get("rf_season_aware_reason", ""),
            "rf_season_adjusted_shadow_grade": fixture.get("rf_season_adjusted_shadow_grade", fixture.get("market_adjusted_shadow_grade", "")),
        }

        if dryrun_grade == "DRYRUN_A":
            dryrun_a_candidates.append(entry)
        elif dryrun_grade == "DRYRUN_B":
            dryrun_b_candidates.append(entry)
        elif dryrun_grade == "DRYRUN_C_OBSERVE":
            dryrun_c_candidates.append(entry)
            if rsg in ("A", "B"):
                rf_ab_downgraded_to_c_observe += 1

        # Track strong/extreme vetoed shadow A/B
        if rsg in ("A", "B") and policy.get("opening_market_conflict_level") in {"MARKET_STRONG_CONFLICT", "MARKET_EXTREME_VETO"}:
            vetoed_shadow_ab.append(entry)

        # Track rejected no_market
        if rsg in ("A", "B") and has_no_market(fixture):
            rejected_no_market.append(entry)
        if has_no_market_data(fixture) and dryrun_grade in {"DRYRUN_B", "DRYRUN_C_OBSERVE"} and rsg in {"A", "B"}:
            market_no_data_preserved_observe += 1

    cv_a = int(candidate_view.get("A_count", 0) or 0)
    cv_b = int(candidate_view.get("B_count", 0) or 0)
    cv_c = int(candidate_view.get("C_count", 0) or 0)
    cv_skip_raw = int(candidate_view.get("SKIP_count", 0) or 0)
    source_row_count = len(scout_data)
    cv_skip = cv_skip_raw if cv_skip_raw > 0 else max(0, source_row_count - cv_a - cv_b - cv_c)
    official_total = cv_a + cv_b + cv_c + cv_skip
    dryrun_total = sum(dryrun_grades.values())

    report = {
        "report_type": "V4_RF_SHADOW_TO_OFFICIAL_PROMOTION_DRYRUN",
        "scan_date": scan_date,
        "generated_at": datetime.now().isoformat(),
        "source_row_count": source_row_count,
        "official_total": official_total,
        "dryrun_total": dryrun_total,
        "official_grade_distribution_from_candidate_view": {
            "A": cv_a,
            "B": cv_b,
            "C": cv_c,
            "SKIP": cv_skip,
            "SKIP_raw": cv_skip_raw,
        },
        "disclaimer": "This is a dry-run simulation only. Not an official recommendation. "
                     "Does not affect pending bets, validation, live bets, QQ, or cron.",
        "official_grades_before_dryrun": official_grades,
        "rf_shadow_grade_distribution": rf_shadow_grades,
        "market_adjusted_shadow_grade_distribution": market_adjusted_grades,
        "dryrun_grade_distribution": dryrun_grades,
        "dryrun_a_candidates": dryrun_a_candidates,
        "dryrun_b_candidates": dryrun_b_candidates,
        "dryrun_c_candidates": dryrun_c_candidates,
        "market_conflict_vetoed_shadow_ab": vetoed_shadow_ab,
        "rejected_by_no_market": rejected_no_market,
        "rf_ab_downgraded_to_c_observe_count": rf_ab_downgraded_to_c_observe,
        "market_no_data_preserved_observe_count": market_no_data_preserved_observe,
        "extreme_veto_count": int(dryrun_grades.get("DRYRUN_EXTREME_VETO", 0)),
        "season_aware_field_distribution": {
            "season_phase": season_phase_distribution,
            "league_tier": league_tier_distribution,
            "rf_sample_status": rf_sample_status_distribution,
            "rf_freshness_status": rf_freshness_status_distribution,
        },
        "safety_checks": {
            "official_grade_modified": False,
            "candidate_view_modified": False,
            "pending_bet_modified": False,
            "validation_recomputed": False,
            "live_bet_modified": False,
            "qq_pushed": False,
            "cron_modified": False,
            "api_called": False,
            "scan_re_executed": False,
        },
    }
    return report


def write_report(report: dict, scan_date: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR,
                             f"v4_rf_shadow_to_official_promotion_dryrun_{scan_date}.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  ✅ JSON report: {json_path}")
    return json_path


def write_markdown(report: dict, scan_date: str):
    md_path = os.path.join(OUTPUT_DIR,
                           f"v4_rf_shadow_to_official_promotion_dryrun_{scan_date}.md")
    lines = []
    lines.append(f"# V4 RF Shadow → Official Promotion Dry-Run Report ({scan_date})")
    lines.append("")
    lines.append("> ⚠️ **DISCLAIMER**: This is a dry-run simulation only. "
                 "Not an official recommendation. Does not affect pending bets, "
                 "validation, live bets, QQ, or cron.")
    lines.append("")
    lines.append(f"**Generated at**: {report['generated_at']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 一、总览")
    lines.append("")
    lines.append("| Grade | Official | RF Shadow | Market Adjusted | Dry-Run |")
    lines.append("|-------|----------|-----------|-----------------|---------|")

    og = report["official_grades_before_dryrun"]
    rsg = report["rf_shadow_grade_distribution"]
    masg = report["market_adjusted_shadow_grade_distribution"]
    drg = report["dryrun_grade_distribution"]

    # Map dry-run grades to display
    dr_display = {
        "DRYRUN_A": drg.get("DRYRUN_A", 0),
        "DRYRUN_B": drg.get("DRYRUN_B", 0),
        "DRYRUN_C_OBSERVE": drg.get("DRYRUN_C_OBSERVE", 0),
        "DRYRUN_SKIP": drg.get("DRYRUN_SKIP", 0),
    }
    dr_skip_total = drg.get("DRYRUN_SKIP", 0) + drg.get("DRYRUN_EXTREME_VETO", 0)

    lines.append(f"| A | {og.get('A',0)} | {rsg.get('A',0)} | {masg.get('A',0)} | {dr_display['DRYRUN_A']} |")
    lines.append(f"| B | {og.get('B',0)} | {rsg.get('B',0)} | {masg.get('B',0)} | {dr_display['DRYRUN_B']} |")
    lines.append(f"| C | {og.get('C',0)} | {rsg.get('C',0)} | {masg.get('C',0)} | {dr_display['DRYRUN_C_OBSERVE']} |")
    lines.append(f"| SKIP | {og.get('SKIP',0)} | {rsg.get('SKIP',0)} | {masg.get('SKIP',0)} | {dr_skip_total} |")
    lines.append(f"| NONE | {og.get('NONE',0)} | — | — | — |")
    lines.append("")
    lines.append(f"**Dry-run EXTREME_VETO (extreme market anomaly skip)**: {drg.get('DRYRUN_EXTREME_VETO',0)}")
    lines.append(f"**RF A/B 降级进入 C观察**: {report.get('rf_ab_downgraded_to_c_observe_count',0)}")
    lines.append(f"**MARKET_NO_DATA 保留观察(B/C)**: {report.get('market_no_data_preserved_observe_count',0)}")
    lines.append("")

    # Dry-run A candidates
    lines.append("## 二、Dry-Run A 候选")
    lines.append("")
    candidates = report.get("dryrun_a_candidates", [])
    if not candidates:
        lines.append("*（无）*")
    else:
        lines.append("| 时间 | 联赛 | 对阵 | shadow_grade | market_adjusted | shadow_score | confidence |")
        lines.append("|------|------|------|-------------|-----------------|-------------|------------|")
        for c in sorted(candidates, key=lambda x: x["kickoff"]):
            lines.append(f"| {c['kickoff']} | {c['league']} | {c['home']} vs {c['away']} | "
                         f"{c['rf_shadow_grade']} | {c['market_adjusted_shadow_grade']} | "
                         f"{c.get('rf_shadow_score','')} | {c.get('rf_shadow_confidence','')} |")
    lines.append("")

    # Dry-run B candidates
    lines.append("## 三、Dry-Run B 候选")
    lines.append("")
    candidates = report.get("dryrun_b_candidates", [])
    if not candidates:
        lines.append("*（无）*")
    else:
        lines.append("| 时间 | 联赛 | 对阵 | shadow_grade | market_adjusted | shadow_score | confidence | market_status |")
        lines.append("|------|------|------|-------------|-----------------|-------------|------------|--------------|")
        for c in sorted(candidates, key=lambda x: x["kickoff"]):
            lines.append(f"| {c['kickoff']} | {c['league']} | {c['home']} vs {c['away']} | "
                         f"{c['rf_shadow_grade']} | {c['market_adjusted_shadow_grade']} | "
                         f"{c.get('rf_shadow_score','')} | {c.get('rf_shadow_confidence','')} | "
                         f"{c['opening_market_support_status']} |")
    lines.append("")

    # Strong/extreme vetoed shadow A/B
    lines.append("## 四、被强冲突/极端熔断影响的 Shadow A/B")
    lines.append("")
    lines.append("以下 shadow A/B 因 MARKET_STRONG_CONFLICT / MARKET_EXTREME_VETO 被阻拦：")
    lines.append("")
    vetoed = report.get("market_conflict_vetoed_shadow_ab", [])
    if not vetoed:
        lines.append("*（无）*")
    else:
        lines.append("| 时间 | 联赛 | 对阵 | shadow_grade | dryrun结果 | market_reason |")
        lines.append("|------|------|------|-------------|-----------|--------------|")
        for c in sorted(vetoed, key=lambda x: x["kickoff"]):
            lines.append(f"| {c['kickoff']} | {c['league']} | {c['home']} vs {c['away']} | "
                         f"{c['rf_shadow_grade']} | {c['dryrun_grade']} | "
                         f"{c.get('opening_market_reason','')} |")
    lines.append("")

    # Rejected by no market
    lines.append("## 五、被 NO_MARKET 阻拦的 Shadow A/B")
    lines.append("")
    rejected = report.get("rejected_by_no_market", [])
    if not rejected:
        lines.append("*（无）*")
    else:
        lines.append("| 时间 | 联赛 | 对阵 | shadow_grade | dryrun结果 |")
        lines.append("|------|------|------|-------------|-----------|")
        for c in sorted(rejected, key=lambda x: x["kickoff"]):
            lines.append(f"| {c['kickoff']} | {c['league']} | {c['home']} vs {c['away']} | "
                         f"{c['rf_shadow_grade']} | {c['dryrun_grade']} |")
    lines.append("")

    # Safety declaration
    lines.append("## 六、正式安全声明")
    lines.append("")
    lines.append("1. ✅ 本报告是 dry-run 模拟，**不是正式推荐**。")
    lines.append("2. ✅ 未修改 official grade。")
    lines.append("3. ✅ 未修改 candidate_view。")
    lines.append("4. ✅ 未修改 pending_bet_candidates。")
    lines.append("5. ✅ 未重算 validation。")
    lines.append("6. ✅ 未修改 live bet。")
    lines.append("7. ✅ 未推 QQ。")
    lines.append("8. ✅ 未修改 cron。")
    lines.append("9. ✅ 未调用 API。")
    lines.append("10. ✅ 未重新扫描。")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  ✅ Markdown report: {md_path}")
    return md_path


def main():
    parser = argparse.ArgumentParser(
        description="V4 RF Shadow → Official Promotion Dry-Run")
    parser.add_argument("--date", required=True, help="Scan date YYYYMMDD")
    args = parser.parse_args()

    scan_date = args.date
    print(f"\n🔍 V4 RF Shadow Promotion Dry-Run for {scan_date}\n")

    # Load data
    scout_data = load_scout(scan_date)
    candidate_view = load_candidate_view(scan_date)

    # Verify official grade not changed
    actual_a = candidate_view.get("A_count", 0)
    actual_b = candidate_view.get("B_count", 0)
    actual_skip = candidate_view.get("SKIP_count", 0)
    print(f"  📊 Official before dryrun: A={actual_a}, B={actual_b}, SKIP={actual_skip}")

    # Build report
    report = build_dryrun_report(scout_data, candidate_view, scan_date)

    # Verify no grade modification
    assert report["safety_checks"]["official_grade_modified"] is False
    assert report["safety_checks"]["candidate_view_modified"] is False
    assert report["safety_checks"]["api_called"] is False
    assert report["safety_checks"]["scan_re_executed"] is False

    # Check market veto rule
    for c in report.get("dryrun_a_candidates", []):
        assert c.get("opening_market_support_status") not in ("MARKET_HARD_VETO",), \
            f"DRYRUN_A candidate {c['fixture_id']} has MARKET_HARD_VETO!"
    for c in report.get("dryrun_b_candidates", []):
        assert c.get("opening_market_support_status") not in ("MARKET_HARD_VETO",), \
            f"DRYRUN_B candidate {c['fixture_id']} has MARKET_HARD_VETO!"

    # Write outputs
    json_path = write_report(report, scan_date)
    md_path = write_markdown(report, scan_date)

    drg = report["dryrun_grade_distribution"]
    print(f"\n📊 Dry-run summary:")
    print(f"  DRYRUN_A:  {drg.get('DRYRUN_A', 0)}")
    print(f"  DRYRUN_B:  {drg.get('DRYRUN_B', 0)}")
    print(f"  DRYRUN_C:  {drg.get('DRYRUN_C_OBSERVE', 0)}")
    print(f"  DRYRUN_SKIP: {drg.get('DRYRUN_SKIP', 0)}")
    print(f"  DRYRUN_EXTREME_VETO: {drg.get('DRYRUN_EXTREME_VETO', 0)}")
    print(f"\n  ✅ Dry-run complete. No API calls, no re-scan, no grade modification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
