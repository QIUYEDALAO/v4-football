#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_match_cards import MATCH_CARDS, MATCH_SUMMARY, build

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_match_cards_20260604.json"
SCOPE_DOC = ROOT / "docs/V3_WC_MATCH_CARD_SCOPE_CLARIFICATION_20260605.md"
GROUP_STAGE_MATCH_COUNT = 72
TOTAL_TOURNAMENT_EXPECTED_MATCH_COUNT = 104

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
DISALLOWED_KEYS = {
    "starting_xi_players",
    "predicted_lineup",
    "confirmed_lineup",
    "official_starting_xi",
    "injury_status",
    "suspension_status",
    "recommended_pick",
    "recommendation_output",
    "betting_signal",
    "fund_flow_signal",
    "steam_signal",
    "drift_signal",
    "sharp_signal",
}
DISALLOWED_PHRASES = [
    "fund flow",
    "money flow conclusion",
    "steam conclusion",
    "drift conclusion",
    "sharp move",
    "starting xi generated",
    "predicted xi",
    "confirmed lineup",
]


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def tracked_runtime_hits() -> list[str]:
    result = git(["ls-files", "data/runtime", "runtime", "logs", "cache", "tmp"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def walk_keys(obj: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.append(str(key))
            keys.extend(walk_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(walk_keys(item))
    return keys


def main() -> int:
    cards, summary = build()
    MATCH_CARDS.parent.mkdir(parents=True, exist_ok=True)
    MATCH_CARDS.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MATCH_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    add(failures, MATCH_CARDS.exists(), "match_cards_missing", MATCH_CARDS)
    add(failures, MATCH_SUMMARY.exists(), "match_summary_missing", MATCH_SUMMARY)
    add(failures, isinstance(cards, list) and len(cards) > 0, "match_count_not_positive", len(cards) if isinstance(cards, list) else "not_list")
    add(failures, len(cards) == GROUP_STAGE_MATCH_COUNT, "match_cards_scope_not_group_stage_72", len(cards))
    add(failures, summary.get("match_count") == len(cards), "summary_match_count_mismatch", summary.get("match_count"))
    add(failures, summary.get("teams_covered") == 48, "teams_covered_unexpected", summary.get("teams_covered"))
    add(failures, summary.get("cards_with_final_26") == len(cards), "cards_with_final_26_unexpected", summary.get("cards_with_final_26"))
    add(failures, SCOPE_DOC.exists(), "scope_doc_missing", SCOPE_DOC.relative_to(ROOT))
    scope_doc = SCOPE_DOC.read_text(encoding="utf-8") if SCOPE_DOC.exists() else ""
    add(failures, "group stage only" in scope_doc.lower(), "scope_doc_group_stage_only_missing")
    add(failures, str(GROUP_STAGE_MATCH_COUNT) in scope_doc, "scope_doc_group_stage_count_missing", GROUP_STAGE_MATCH_COUNT)
    add(failures, str(TOTAL_TOURNAMENT_EXPECTED_MATCH_COUNT) in scope_doc, "scope_doc_total_expected_missing", TOTAL_TOURNAMENT_EXPECTED_MATCH_COUNT)
    add(
        failures,
        "not the complete 2026 world cup match set" in scope_doc.lower(),
        "scope_doc_full_tournament_warning_missing",
    )

    for card in cards:
        match_id = card.get("match_id")
        for key in ["home_team", "away_team", "home_team_slug", "away_team_slug"]:
            add(failures, bool(card.get(key)), f"card_{key}_missing", match_id)
        add(failures, bool(card.get("api_football_fixture_id")), "api_football_fixture_id_missing", match_id)
        add(failures, bool(card.get("home_final_26_profile_ref")) and bool(card.get("away_final_26_profile_ref")), "final_26_profile_ref_missing", match_id)
        add(failures, isinstance(card.get("venue_binding"), dict), "venue_binding_missing", match_id)
        add(failures, isinstance(card.get("odds_binding"), dict), "odds_binding_missing", match_id)
        add(failures, bool(card.get("venue_binding", {}).get("venue_gap_reason")), "venue_gap_reason_missing", match_id)
        add(failures, bool(card.get("venue_binding", {}).get("venue_mapping_bridge_ref")), "venue_mapping_bridge_ref_missing", match_id)
        add(failures, card.get("odds_binding", {}).get("no_money_flow_judgment") is True, "no_money_flow_judgment_missing", match_id)
        add(failures, bool(card.get("odds_binding", {}).get("odds_fixture_id")), "odds_fixture_id_missing", match_id)
        add(failures, card.get("home_lineup_status") in {"WAIT_OFFICIAL_LINEUP", "NOT_AVAILABLE"}, "home_lineup_status_unexpected", match_id)
        add(failures, card.get("away_lineup_status") in {"WAIT_OFFICIAL_LINEUP", "NOT_AVAILABLE"}, "away_lineup_status_unexpected", match_id)
        add(failures, card.get("starting_xi_status") == "NOT_AVAILABLE", "starting_xi_status_unexpected", match_id)
        add(failures, card.get("predicted_xi_generated") is False, "predicted_xi_generated_true", match_id)
        add(failures, card.get("observation_only") is True, "observation_only_unexpected", match_id)
        add(failures, card.get("no_starting_xi_generated") is True, "no_starting_xi_generated_unexpected", match_id)
        add(failures, card.get("no_prediction") is True, "no_prediction_unexpected", match_id)
        add(failures, card.get("no_injury_judgment") is True, "no_injury_judgment_unexpected", match_id)
        add(failures, card.get("betting_recommendation") is False, "betting_recommendation_true", match_id)
        add(failures, card.get("affects_v4") is False, "affects_v4_true", match_id)

    add(failures, summary.get("safety", {}).get("observation_only") is True, "summary_observation_only_unexpected", summary.get("safety"))
    add(failures, summary.get("safety", {}).get("betting_recommendation") is False, "summary_betting_recommendation_true", summary.get("safety"))
    add(failures, summary.get("safety", {}).get("affects_v4") is False, "summary_affects_v4_true", summary.get("safety"))
    for key in [
        "cards_with_venue_binding",
        "cards_with_venue_stress",
        "cards_with_odds_binding",
        "cards_with_odds_available",
        "cards_with_odds_delta_observed",
        "cards_missing_venue_binding",
        "cards_missing_odds_binding",
        "global_gap_summary",
    ]:
        add(failures, key in summary, f"summary_{key}_missing")

    keys = {key.lower() for key in walk_keys({"cards": cards, "summary": summary})}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    combined = json.dumps({"cards": cards, "summary": summary}, ensure_ascii=False).lower()
    for phrase in DISALLOWED_PHRASES:
        add(failures, phrase not in combined, "disallowed_phrase", phrase)

    staged = staged_files()
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    relevant_runtime = [path for path in tracked_runtime_hits() if "match_card" in path]
    add(failures, not relevant_runtime, "runtime_match_card_output_tracked", relevant_runtime)
    secrets = secret_hits([
        MATCH_CARDS,
        MATCH_SUMMARY,
        ROOT / "tools/build_v3_worldcup_match_cards.py",
        Path(__file__).resolve(),
        ROOT / "docs/V3_WC_MATCH_CARD_PACK_PHASE_1_MATCH_CARD_FOUNDATION_20260604.md",
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "scope": "GROUP_STAGE_ONLY",
        "current_scope_match_count": GROUP_STAGE_MATCH_COUNT,
        "total_tournament_expected_match_count": TOTAL_TOURNAMENT_EXPECTED_MATCH_COUNT,
        "full_tournament_complete": False,
        "match_count": len(cards),
        "teams_covered": summary.get("teams_covered"),
        "cards_with_final_26": summary.get("cards_with_final_26"),
        "cards_with_venue_stress": summary.get("cards_with_venue_stress"),
        "cards_with_venue_binding": summary.get("cards_with_venue_binding"),
        "cards_with_tactical_profile": summary.get("cards_with_tactical_profile"),
        "cards_waiting_lineup": summary.get("cards_waiting_lineup"),
        "cards_with_odds_binding": summary.get("cards_with_odds_binding"),
        "cards_with_odds_available": summary.get("cards_with_odds_available"),
        "cards_with_odds_delta": summary.get("cards_with_odds_delta"),
        "cards_with_odds_delta_observed": summary.get("cards_with_odds_delta_observed"),
        "cards_missing_venue_binding": summary.get("cards_missing_venue_binding"),
        "cards_missing_odds_binding": summary.get("cards_missing_odds_binding"),
        "runtime_staged": runtime_staged,
        "v4_staged": v4_staged,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
