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
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_match_card_venue_odds_binding_20260604.json"

DISALLOWED_KEYS = {
    "fund_flow",
    "fund_flow_signal",
    "steam",
    "steam_signal",
    "drift",
    "drift_signal",
    "sharp",
    "sharp_move",
    "sharp_signal",
    "recommended_pick",
    "prediction_output",
}
DISALLOWED_PHRASES = [
    "fund flow",
    "steam",
    "drift",
    "sharp move",
    "starting xi generated",
    "predicted xi",
    "confirmed lineup",
]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


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


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def main() -> int:
    cards, summary = build()
    MATCH_CARDS.parent.mkdir(parents=True, exist_ok=True)
    MATCH_CARDS.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MATCH_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    add(failures, len(cards) == 72, "match_count_unexpected", len(cards))
    for card in cards:
        match_id = card.get("match_id")
        venue_binding = card.get("venue_binding")
        odds_binding = card.get("odds_binding")
        add(failures, isinstance(venue_binding, dict), "venue_binding_missing", match_id)
        add(failures, isinstance(odds_binding, dict), "odds_binding_missing", match_id)
        if isinstance(venue_binding, dict):
            for key in ["venue_name", "venue_slug", "venue_stress_status", "venue_stress_tags", "venue_stress_ref", "venue_mapping_status", "venue_gap_reason"]:
                add(failures, key in venue_binding, f"venue_binding_{key}_missing", match_id)
        if isinstance(odds_binding, dict):
            for key in [
                "odds_fixture_id",
                "odds_snapshot_status",
                "odds_available",
                "bookmaker_count",
                "market_type_count",
                "odds_observation_delta_status",
                "changed_odds_count",
                "odds_gap_reason",
                "no_money_flow_judgment",
            ]:
                add(failures, key in odds_binding, f"odds_binding_{key}_missing", match_id)
            add(failures, odds_binding.get("no_money_flow_judgment") is True, "no_money_flow_judgment_unexpected", match_id)
        add(failures, card.get("home_lineup_status") == "WAIT_OFFICIAL_LINEUP", "home_lineup_not_waiting", match_id)
        add(failures, card.get("away_lineup_status") == "WAIT_OFFICIAL_LINEUP", "away_lineup_not_waiting", match_id)
        add(failures, card.get("starting_xi_status") == "NOT_AVAILABLE", "starting_xi_status_unexpected", match_id)
        add(failures, card.get("predicted_xi_generated") is False, "predicted_xi_generated_true", match_id)
        add(failures, card.get("observation_only") is True, "observation_only_unexpected", match_id)
        add(failures, card.get("betting_recommendation") is False, "betting_recommendation_true", match_id)
        add(failures, card.get("affects_v4") is False, "affects_v4_true", match_id)

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
    add(failures, summary.get("cards_missing_venue_binding") == 72, "cards_missing_venue_binding_unexpected", summary.get("cards_missing_venue_binding"))
    add(failures, summary.get("cards_missing_odds_binding") == 72, "cards_missing_odds_binding_unexpected", summary.get("cards_missing_odds_binding"))

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
    secrets = secret_hits([
        MATCH_CARDS,
        MATCH_SUMMARY,
        ROOT / "tools/build_v3_worldcup_match_cards.py",
        ROOT / "tools/check_v3_worldcup_match_cards.py",
        Path(__file__).resolve(),
        ROOT / "docs/V3_WC_MATCH_CARD_PACK_PHASE_2_VENUE_AND_ODDS_STATUS_BINDING_20260604.md",
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "match_count": len(cards),
        "cards_with_venue_binding": summary.get("cards_with_venue_binding"),
        "cards_with_venue_stress": summary.get("cards_with_venue_stress"),
        "cards_with_odds_binding": summary.get("cards_with_odds_binding"),
        "cards_with_odds_available": summary.get("cards_with_odds_available"),
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
