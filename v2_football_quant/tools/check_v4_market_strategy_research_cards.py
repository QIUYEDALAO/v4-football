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
CARDS = ROOT / "data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260606.json"
SUMMARY = ROOT / "data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_summary_20260606.json"
BUILDER = ROOT / "tools/build_v4_market_strategy_research_cards.py"
DOC = ROOT / "docs/V4_MARKET_STRATEGY_RESEARCH_CARD_PACK_20260606.md"
MAIN_LEAGUE_CHECKER = ROOT / "tools/check_v4_main_league_admission_guard.py"
SELECTION_CHECKER = ROOT / "tools/check_v4_selection_strategy_redesign_freeze.py"

REQUIRED_DIRECTIONS = {
    "FULLTIME_OVER",
    "HANDICAP_HOME_AWAY",
    "DOUBLE_CHANCE_STRONG_SIDE",
    "HT_OVER_AUXILIARY",
}
ALLOWED_CONCLUSIONS = {"OBSERVE", "WAIT", "PASS"}
REQUIRED_MISSING_TAGS = {
    "PRICE_MISSING",
    "LINE_MISSING",
    "MARKET_MISSING",
    "INJURY_SOURCE_MISSING",
    "LINEUP_WAIT_EVENT",
    "DATA_INSUFFICIENT",
}
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
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=120)
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


def main() -> int:
    if BUILDER.exists():
        proc = subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, capture_output=True, text=True, timeout=120)
        builder_returncode = proc.returncode
    else:
        builder_returncode = 127
    payload = load(CARDS) or {}
    summary = load(SUMMARY) or {}
    cards = payload.get("cards", []) if isinstance(payload, dict) else []
    card_text = json.dumps(payload, ensure_ascii=False)
    main_league = run_checker(MAIN_LEAGUE_CHECKER)
    selection = run_checker(SELECTION_CHECKER)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = staged_forbidden(staged)

    card_checks = []
    for card in cards:
        dirs = direction_map(card)
        missing = set(card.get("missing_context", []))
        conclusion = card.get("conclusion")
        price_status = str((card.get("price_quality") or {}).get("price_status") or "")
        league = card.get("league_admission_status") or {}
        safety = card.get("safety") or {}
        non_ht_observe = [
            d for d in dirs.values()
            if d.get("direction") != "HT_OVER_AUXILIARY" and d.get("status") == "OBSERVE"
        ]
        card_checks.append({
            "fixture_id": (card.get("match_info") or {}).get("fixture_id"),
            "directions_complete": set(dirs) == REQUIRED_DIRECTIONS,
            "conclusion_allowed": conclusion in ALLOWED_CONCLUSIONS,
            "missing_tags_present": bool(REQUIRED_MISSING_TAGS.intersection(missing)),
            "price_missing_no_observe": not (price_status in {"PRICE_MISSING", "PAPER_PROXY_FORBIDDEN"} and conclusion == "OBSERVE"),
            "market_missing_no_confirmation": not ("MARKET_MISSING" in missing and (card.get("market_confirmation") or {}).get("status") == "CONFIRMED"),
            "line_missing_no_direction_observe": not ("LINE_MISSING" in missing and non_ht_observe),
            "ht_over_not_standalone_observe": dirs.get("HT_OVER_AUXILIARY", {}).get("status") != "OBSERVE"
            and dirs.get("HT_OVER_AUXILIARY", {}).get("standalone_ab_allowed") is False,
            "observe_only_no_realtime": not (league.get("observe_only") and safety.get("realtime_reminder")),
            "official_unchanged": (card.get("match_info") or {}).get("official_grade_unchanged") is True
            and safety.get("official_grade_changed") is False,
            "pending_qq_cron_unchanged": safety.get("pending_written") is False
            and safety.get("qq_sent") is False
            and safety.get("cron_or_launchd_modified") is False,
        })

    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder_returncode == 0,
        "cards_exist": CARDS.exists(),
        "summary_exists": SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "card_count_1_to_3": 1 <= len(cards) <= 3,
        "allowed_conclusion_catalog_complete": set(payload.get("allowed_conclusions", [])) == ALLOWED_CONCLUSIONS,
        "summary_conclusion_catalog_complete": set((summary.get("conclusion_counts") or {}).keys()) == ALLOWED_CONCLUSIONS,
        "directions_required": set(payload.get("strategy_directions_required", [])) == REQUIRED_DIRECTIONS,
        "cards_pass_individual_guards": all(all(v is True for k, v in c.items() if k != "fixture_id") for c in card_checks),
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
        "main_league_guard_pass": main_league["returncode"] == 0 and main_league.get("payload", {}).get("conclusion") == "PASS",
        "selection_freeze_pass": selection["returncode"] == 0 and selection.get("payload", {}).get("conclusion") == "PASS",
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_market_strategy_research_cards_guard.v1",
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
