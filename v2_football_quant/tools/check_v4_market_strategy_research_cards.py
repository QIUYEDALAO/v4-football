#!/usr/bin/env python3
"""Check V4 market strategy research cards stay observation-only."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260607.json"
SUMMARY = ROOT / "data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_summary_20260607.json"
BUILDER = ROOT / "tools/build_v4_market_strategy_research_cards.py"
DOC = ROOT / "docs/V4_MARKET_STRATEGY_RESEARCH_CARD_PACK_20260607.md"
FIVE_CHECKER = ROOT / "tools/check_v4_five_dimension_lite.py"
MAIN_LEAGUE_CHECKER = ROOT / "tools/check_v4_main_league_admission_guard.py"
PRICE_CHECKER = ROOT / "tools/check_v4_price_field_persistence_pipeline.py"
SELECTION_CHECKER = ROOT / "tools/check_v4_selection_strategy_redesign_freeze.py"
PRODUCTION_GUARD = ROOT / "tools/check_v4_production_default_rules_guard.py"

REQUIRED_DIRECTIONS = {
    "FULLTIME_OVER",
    "HANDICAP_HOME_AWAY",
    "DOUBLE_CHANCE_STRONG_SIDE",
    "HT_OVER_AUXILIARY",
}
ALLOWED_CONCLUSIONS = {"OBSERVE", "WAIT", "PASS"}
FORBIDDEN_CARD_TERMS = re.compile(
    r"推荐|投注|下注|实单|必中|稳胆|梭哈|资金流|sharp|steam|drift|sure win|must bet|betting signal",
    re.IGNORECASE,
)


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def run_checker(path: Path) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    text = proc.stdout.strip()
    payload: Any = {}
    if "{" in text:
        try:
            payload = json.loads(text[text.find("{"):])
        except Exception:
            payload = {}
    return {"returncode": proc.returncode, "payload": payload}


def staged_forbidden(staged: list[str]) -> list[str]:
    bad: list[str] = []
    for path in staged:
        if path.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/")):
            bad.append(path)
        if re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", path):
            bad.append(path)
    return sorted(set(bad))


def direction_map(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in card.get("strategy_directions", []):
        if isinstance(row, dict):
            out[str(row.get("direction"))] = row
    return out


def card_guard(card: dict[str, Any]) -> dict[str, bool]:
    dirs = direction_map(card)
    missing = set(card.get("missing_context", []))
    conclusion = card.get("conclusion")
    league = card.get("league_admission_status") or {}
    market_readout = card.get("market_confirmation_readout") or {}
    strength_readout = card.get("strength_gap_readout") or {}
    squad_readout = card.get("squad_context_readout") or {}
    external_readout = card.get("external_risk_readout") or {}
    policy = card.get("policy_lock") or {}
    non_ht_observe = [
        row for row in dirs.values()
        if row.get("direction") != "HT_OVER_AUXILIARY" and row.get("status") == "OBSERVE"
    ]
    return {
        "structure_complete": all(
            key in card
            for key in [
                "match_info",
                "league_admission_status",
                "five_dimension_summary",
                "strategy_directions",
                "strength_gap_readout",
                "tactical_efficiency_readout",
                "squad_context_readout",
                "market_confirmation_readout",
                "external_risk_readout",
                "missing_context",
                "conclusion",
            ]
        ),
        "directions_complete": set(dirs) == REQUIRED_DIRECTIONS,
        "conclusion_allowed": conclusion in ALLOWED_CONCLUSIONS,
        "price_missing_no_market_edge": not (
            "PRICE_MISSING" in missing and market_readout.get("market_edge_status") != "NOT_EVALUABLE"
        ),
        "line_missing_no_market_confirmation": not (
            "LINE_MISSING" in missing and market_readout.get("line_confirmation_status") != "NOT_EVALUABLE"
        ),
        "market_missing_wait_or_pass": not ("MARKET_MISSING" in missing and conclusion == "OBSERVE"),
        "strength_missing_no_pass": not (
            {"STANDINGS_MISSING", "TEAM_STATS_MISSING"}.issubset(missing)
            and strength_readout.get("status") == "OBSERVE"
        ),
        "lineup_wait_event": squad_readout.get("lineup_status") == "LINEUP_WAIT_EVENT",
        "injury_missing_not_assumed_clear": squad_readout.get("injury_status") == "INJURY_SOURCE_MISSING"
        and squad_readout.get("assume_no_injury") is False,
        "external_pending_no_positive": external_readout.get("positive_external_conclusion") is False,
        "ht_over_not_standalone_observe": dirs.get("HT_OVER_AUXILIARY", {}).get("status") != "OBSERVE"
        and dirs.get("HT_OVER_AUXILIARY", {}).get("standalone_ab_allowed") is False,
        "observe_only_no_realtime": not (league.get("observe_only") and policy.get("realtime_reminder")),
        "official_unchanged": (card.get("match_info") or {}).get("official_grade_unchanged") is True
        and policy.get("official_grade_changed") is False,
        "pending_qq_cron_unchanged": policy.get("pending_written") is False
        and policy.get("qq_sent") is False
        and policy.get("cron_or_launchd_modified") is False,
        "b_realtime_paused": policy.get("b_realtime_restored") is False,
        "rf_shadow_blocked": policy.get("rf_shadow_promotion_released") is False,
        "c_skip_shadow_no_realtime": all(row.get("realtime_reminder") is False for row in dirs.values())
        and policy.get("realtime_reminder") is False,
    }


def main() -> int:
    builder_proc = subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    payload = load(CARDS) or {}
    summary = load(SUMMARY) or {}
    cards = payload.get("cards", []) if isinstance(payload, dict) else []
    card_text = json.dumps(payload, ensure_ascii=False)
    five = run_checker(FIVE_CHECKER)
    main_league = run_checker(MAIN_LEAGUE_CHECKER)
    price = run_checker(PRICE_CHECKER)
    selection = run_checker(SELECTION_CHECKER)
    production = run_checker(PRODUCTION_GUARD)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = staged_forbidden(staged)
    card_checks = [card_guard(card) for card in cards]

    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder_proc.returncode == 0,
        "cards_exist": CARDS.exists(),
        "summary_exists": SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "card_count_1_to_3": 1 <= len(cards) <= 3,
        "source_is_five_dimension_lite": payload.get("source") == "five_dimension_lite_local_artifacts_only",
        "allowed_conclusion_catalog_complete": set(payload.get("allowed_conclusions", [])) == ALLOWED_CONCLUSIONS,
        "summary_conclusion_catalog_complete": set((summary.get("conclusion_counts") or {}).keys()) == ALLOWED_CONCLUSIONS,
        "directions_required": set(payload.get("strategy_directions_required", [])) == REQUIRED_DIRECTIONS,
        "cards_pass_individual_guards": all(all(v is True for v in row.values()) for row in card_checks),
        "no_forbidden_card_terms": FORBIDDEN_CARD_TERMS.search(card_text) is None,
        "no_live_api": payload.get("live_api_called") is False,
        "policy_lock": all(
            (payload.get("policy_lock") or {}).get(key) is False
            for key in [
                "official_grade_changed",
                "ab_threshold_changed",
                "pending_written",
                "qq_sent",
                "cron_or_launchd_modified",
                "b_realtime_restored",
                "rf_shadow_promotion_released",
            ]
        ),
        "five_dimension_lite_pass": five["returncode"] == 0 and five.get("payload", {}).get("conclusion") == "PASS",
        "main_league_guard_pass": main_league["returncode"] == 0 and main_league.get("payload", {}).get("conclusion") == "PASS",
        "price_persistence_pass": price["returncode"] == 0 and price.get("payload", {}).get("conclusion") == "PASS",
        "selection_freeze_pass": selection["returncode"] == 0 and selection.get("payload", {}).get("conclusion") == "PASS",
        "production_guard_pass": production["returncode"] == 0 and production.get("payload", {}).get("conclusion") == "PASS",
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_market_strategy_research_cards_guard.v2",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "card_checks": card_checks,
        "card_count": len(cards),
        "covered_markets": sorted(REQUIRED_DIRECTIONS),
        "conclusion_counts": summary.get("conclusion_counts"),
        "forbidden_staged": forbidden_staged,
        "official_grade_changed": False,
        "pending_written": False,
        "qq_sent": False,
        "cron_or_launchd_modified": False,
        "b_realtime_restored": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
