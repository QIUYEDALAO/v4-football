#!/usr/bin/env python3
"""Guard V4 main-league whitelist and admission policy.

This checker is read-only. It verifies the new V4 research-pool admission
policy without calling live APIs or changing official grades.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/v4_main_league_admission_policy.json"
DOC = ROOT / "docs/V4_MAIN_LEAGUE_WHITELIST_AND_ADMISSION_GUARD_20260606.md"
RUNNER = ROOT / "engine/v4_runner.py"
SELECTION_CHECKER = ROOT / "tools/check_v4_selection_strategy_redesign_freeze.py"

EXPECTED_INCLUDE_CURRENT = {
    "J1 League",
    "CSL",
    "Serie A Brazil",
    "Belgian Pro League",
    "UCL",
}
EXPECTED_INCLUDE_SEASON_AWARE = {
    "EPL",
    "LaLiga",
    "Bundesliga",
    "Serie A Italy",
    "Ligue 1",
    "Liga Portugal",
    "Eredivisie",
    "Super Lig",
    "Liga MX",
    "MLS",
}
EXPECTED_OBSERVE_ONLY = {
    "Argentina Liga Profesional",
    "K League 1",
    "UEL",
    "Friendlies",
}
WEAK_OR_NON_FORMAL_EXAMPLES = [
    (493, "UEFA U19 Championship", "Cup"),
    (192, "Australia New South Wales NPL", "League"),
    (99999, "Unknown Regional League", "League"),
    (10, "Friendlies", "Cup"),
]


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def load_module(path: Path):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("v4_league_admission_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["v4_league_admission_check"] = module
    spec.loader.exec_module(module)
    return module


def run_checker(path: Path) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    text = proc.stdout.strip()
    parsed: Any = {}
    if "{" in text:
        try:
            parsed = json.loads(text[text.find("{"):])
        except Exception:
            parsed = {}
    return {"returncode": proc.returncode, "payload": parsed, "stdout_tail": text[-500:]}


def names_for(policy: dict[str, Any], group: str) -> set[str]:
    rows = policy.get("league_groups", {}).get(group, [])
    return {str(row.get("name")) for row in rows if isinstance(row, dict)}


def league_ids_for(policy: dict[str, Any], group: str) -> set[int]:
    rows = policy.get("league_groups", {}).get(group, [])
    out = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            out.add(int(row.get("league_id")))
        except Exception:
            pass
    return out


def staged_forbidden(staged: list[str]) -> list[str]:
    forbidden = []
    for path in staged:
        if re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", path):
            forbidden.append(path)
        if path.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/")):
            forbidden.append(path)
    return sorted(set(forbidden))


def main() -> int:
    policy = json.loads(POLICY.read_text(encoding="utf-8")) if POLICY.exists() else {}
    admission = load_module(ROOT / "engine/v4_league_admission.py")
    runner_text = RUNNER.read_text(encoding="utf-8") if RUNNER.exists() else ""
    doc_text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""

    include_current = names_for(policy, "INCLUDE_CURRENT")
    include_season = names_for(policy, "INCLUDE_SEASON_AWARE")
    observe_only = names_for(policy, "OBSERVE_ONLY")
    include_ids = league_ids_for(policy, "INCLUDE_CURRENT") | league_ids_for(policy, "INCLUDE_SEASON_AWARE")
    observe_ids = league_ids_for(policy, "OBSERVE_ONLY")

    sample_classifications = [
        admission.classify_league(98, "J1 League", "League"),
        admission.classify_league(39, "Premier League", "League"),
        admission.classify_league(128, "Liga Profesional Argentina", "League"),
        admission.classify_league(10, "Friendlies", "Cup"),
        admission.classify_league(493, "UEFA U19 Championship", "Cup"),
        admission.classify_league(192, "Australia New South Wales NPL", "League"),
    ]
    weak_results = [
        admission.classify_league(league_id, name, league_type)
        for league_id, name, league_type in WEAK_OR_NON_FORMAL_EXAMPLES
    ]
    complete_admission = admission.admission_rule_status(
        market_families=["1X2", "FT_OU", "AH_OR_HANDICAP"],
        bookmaker_count=8,
        has_ft_ou_line=True,
        has_standings=True,
        has_injuries=True,
        has_lineup=True,
    )
    missing_admission = admission.admission_rule_status(
        market_families=["1X2", "BTTS"],
        bookmaker_count=3,
        has_ft_ou_line=False,
        has_handicap_line=False,
        has_standings=False,
        has_team_stats=False,
        has_injuries=False,
        has_lineup=False,
    )

    selection = run_checker(SELECTION_CHECKER)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = staged_forbidden(staged)

    checks = {
        "policy_exists": POLICY.exists(),
        "doc_exists": DOC.exists(),
        "include_current_exact": include_current == EXPECTED_INCLUDE_CURRENT,
        "include_season_aware_exact": include_season == EXPECTED_INCLUDE_SEASON_AWARE,
        "observe_only_exact": observe_only == EXPECTED_OBSERVE_ONLY,
        "include_and_observe_disjoint": include_ids.isdisjoint(observe_ids),
        "friendlies_observe_only": admission.classify_league(10, "Friendlies", "Cup").get("admission_group") == "OBSERVE_ONLY",
        "weak_leagues_excluded_from_include": all(r.get("admission_group") != "INCLUDE_CURRENT" and r.get("admission_group") != "INCLUDE_SEASON_AWARE" for r in weak_results),
        "observe_only_not_strategy_pool": all(not admission.classify_league(i, n, "League").get("strategy_pool_allowed") for i, n in [(128, "Liga Profesional Argentina"), (292, "K League 1")]),
        "all_eligible_uses_admission_policy": "classify_league" in runner_text and "strategy_pool_allowed" in runner_text,
        "whitelist_path_also_blocks_non_strategy_pool": 'fixture_universe == "whitelist"' in runner_text and 'if not league_policy.get("strategy_pool_allowed")' in runner_text,
        "admission_market_family_rule": "MARKET_FAMILY_COVERAGE_LT_3" in missing_admission.get("admission_blockers", []),
        "admission_bookmaker_rule": "BOOKMAKER_COUNT_LT_5" in missing_admission.get("admission_blockers", []),
        "admission_line_rule": "LINE_MISSING_FOR_FT_OU_OR_HANDICAP" in missing_admission.get("admission_blockers", []),
        "admission_standings_or_team_stats_rule": "STANDINGS_OR_TEAM_STATS_MISSING" in missing_admission.get("admission_blockers", []),
        "injury_gap_tag": "INJURY_SOURCE_MISSING" in missing_admission.get("data_gap_tags", []),
        "lineup_gap_tag": "LINEUP_WAIT_EVENT" in missing_admission.get("data_gap_tags", []),
        "complete_admission_passes": complete_admission.get("admission_info_complete") is True,
        "ht_over_auxiliary_only": policy.get("admission_rules", {}).get("ht_over_policy") == "AUXILIARY_ONLY_NO_STANDALONE_AB",
        "notification_policy_locked": policy.get("notification_policy", {}).get("b_realtime_reminder") == "PAUSED"
        and policy.get("notification_policy", {}).get("observe_only_realtime_reminder") is False
        and policy.get("notification_policy", {}).get("c_skip_shadow_only_realtime_reminder") is False
        and policy.get("notification_policy", {}).get("rf_shadow_promotion") == "BLOCKED",
        "selection_freeze_checker_keeps_rf_blocked": selection["returncode"] == 0 and selection.get("payload", {}).get("conclusion") == "PASS",
        "doc_safety_terms_present": all(
            term in doc_text
            for term in [
                "not a strategy launch",
                "Friendlies remain OBSERVE_ONLY",
                "HT Over is auxiliary only",
                "B realtime reminder remains paused",
                "RF shadow promotion remains BLOCKED",
                "does not change official A/B/C/SKIP thresholds",
            ]
        ),
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_main_league_admission_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "include_current": sorted(include_current),
        "include_season_aware": sorted(include_season),
        "observe_only": sorted(observe_only),
        "sample_classifications": sample_classifications,
        "missing_admission": missing_admission,
        "forbidden_staged": forbidden_staged,
        "official_grade_changed": False,
        "ab_threshold_changed": False,
        "pending_written": False,
        "qq_sent": False,
        "cron_or_launchd_modified": False,
        "b_realtime_restored": False,
        "rf_shadow_promotion_released": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
