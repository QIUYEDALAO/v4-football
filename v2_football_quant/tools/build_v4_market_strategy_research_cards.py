#!/usr/bin/env python3
"""Build V4 market strategy research cards from five-dimension Lite samples.

No live API is called. The output is manual-source research material, not
runtime state and not an official strategy signal.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIVE_DIMENSION = ROOT / "data/manual_sources/v4/five_dimension_lite/v4_five_dimension_lite_samples_20260607.json"
OUT_DIR = ROOT / "data/manual_sources/v4/market_strategy_research_cards"
OUT_JSON = OUT_DIR / "v4_market_strategy_research_cards_20260607.json"
OUT_SUMMARY = OUT_DIR / "v4_market_strategy_research_cards_summary_20260607.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

STRATEGY_DIRECTIONS = [
    "FULLTIME_OVER",
    "HANDICAP_HOME_AWAY",
    "DOUBLE_CHANCE_STRONG_SIDE",
    "HT_OVER_AUXILIARY",
]
ALLOWED_CONCLUSIONS = ["OBSERVE", "WAIT", "PASS"]
CRITICAL_MARKET_MISSING = {"PRICE_MISSING", "LINE_MISSING", "MARKET_MISSING"}
CRITICAL_STRENGTH_MISSING = {"STANDINGS_MISSING", "TEAM_STATS_MISSING"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def status_from_missing(missing: set[str], *, direction: str) -> str:
    if direction == "HT_OVER_AUXILIARY":
        return "WAIT"
    if CRITICAL_MARKET_MISSING.intersection(missing):
        return "WAIT"
    return "OBSERVE"


def market_presence(five: dict[str, Any], direction: str) -> tuple[bool, bool]:
    market = five.get("market_confirmation") or {}
    families = market.get("market_families") or {}
    line_present = market.get("line") is not None
    if direction == "FULLTIME_OVER":
        return bool(families.get("FT_OU")), bool(families.get("FT_OU") and line_present)
    if direction == "HANDICAP_HOME_AWAY":
        return bool(families.get("AH_OR_HANDICAP")), bool(families.get("AH_OR_HANDICAP") and line_present)
    if direction == "DOUBLE_CHANCE_STRONG_SIDE":
        return bool(families.get("DOUBLE_CHANCE")), bool(families.get("DOUBLE_CHANCE"))
    return bool(market.get("ht_over_auxiliary_present")), bool(market.get("ht_over_auxiliary_present") and line_present)


def direction_row(five: dict[str, Any], direction: str) -> dict[str, Any]:
    missing = set(five.get("missing_context") or [])
    market_present, line_present = market_presence(five, direction)
    direction_missing: list[str] = []
    if not market_present:
        direction_missing.append("MARKET_MISSING")
    if direction != "DOUBLE_CHANCE_STRONG_SIDE" and not line_present:
        direction_missing.append("LINE_MISSING")
    if "PRICE_MISSING" in missing:
        direction_missing.append("PRICE_MISSING")
    if direction == "HT_OVER_AUXILIARY":
        direction_missing.append("HT_OVER_AUXILIARY_ONLY")
    status = status_from_missing(set(direction_missing), direction=direction)
    if direction == "HT_OVER_AUXILIARY":
        status = "WAIT"
    return {
        "direction": direction,
        "market_present": market_present,
        "line_present": line_present,
        "status": status,
        "missing_context": sorted(set(direction_missing)),
        "standalone_ab_allowed": False if direction == "HT_OVER_AUXILIARY" else None,
        "realtime_reminder": False,
    }


def readout_status(dimension: dict[str, Any], blocking_tags: set[str], missing: set[str]) -> str:
    if blocking_tags.intersection(missing):
        return "WAIT"
    value = str(dimension.get("status") or "").upper()
    return "OBSERVE" if value == "PASS" else "WAIT"


def conclusion_for(five: dict[str, Any], directions: list[dict[str, Any]]) -> str:
    league = five.get("league_admission_status") or {}
    missing = set(five.get("missing_context") or [])
    if not league.get("strategy_pool_allowed"):
        return "PASS"
    if CRITICAL_MARKET_MISSING.intersection(missing):
        return "WAIT"
    if CRITICAL_STRENGTH_MISSING.issubset(missing):
        return "WAIT"
    if "LINEUP_WAIT_EVENT" in missing or "EXTERNAL_CONTEXT_PENDING" in missing:
        return "WAIT"
    non_ht_observe = [
        row for row in directions
        if row.get("direction") != "HT_OVER_AUXILIARY" and row.get("status") == "OBSERVE"
    ]
    return "OBSERVE" if non_ht_observe else "WAIT"


def card_from_five_dimension(five: dict[str, Any]) -> dict[str, Any]:
    missing = set(five.get("missing_context") or [])
    market = five.get("market_confirmation") or {}
    strength = five.get("strength_gap") or {}
    tactical = five.get("tactical_efficiency") or {}
    squad = five.get("squad_context") or {}
    external = five.get("external_risk") or {}
    directions = [direction_row(five, direction) for direction in STRATEGY_DIRECTIONS]
    conclusion = conclusion_for(five, directions)
    return {
        "schema_version": "v4_market_strategy_research_card.v2",
        "card_type": "MARKET_STRATEGY_RESEARCH_CARD",
        "source_artifact": five.get("source_artifact"),
        "source_five_dimension_schema": five.get("schema_version"),
        "match_info": five.get("match_info") or {},
        "league_admission_status": five.get("league_admission_status") or {},
        "five_dimension_summary": {
            "strength_gap": strength.get("status"),
            "tactical_efficiency": tactical.get("status"),
            "squad_context": squad.get("status"),
            "market_confirmation": market.get("status"),
            "external_risk": external.get("status"),
        },
        "strategy_directions": directions,
        "strength_gap_readout": {
            "status": readout_status(strength, CRITICAL_STRENGTH_MISSING, missing),
            "league_tier": strength.get("league_tier"),
            "standings_status": strength.get("standings_status"),
            "team_stats_status": strength.get("team_stats_status"),
            "h2h_policy": (strength.get("h2h") or {}).get("policy"),
            "historical_form_policy": strength.get("historical_form_policy"),
        },
        "tactical_efficiency_readout": {
            "status": readout_status(tactical, {"TEAM_STATS_MISSING"}, missing),
            "home_away_stats_status": tactical.get("home_away_stats_status"),
            "ft_ou_context_status": tactical.get("ft_ou_context_status"),
            "shots_status": tactical.get("shots_status"),
        },
        "squad_context_readout": {
            "status": "WAIT",
            "lineup_status": squad.get("lineup_status"),
            "injury_status": squad.get("injury_status"),
            "formation_status": squad.get("formation_status"),
            "assume_no_injury": False,
        },
        "market_confirmation_readout": {
            "status": "WAIT" if CRITICAL_MARKET_MISSING.intersection(missing) else "OBSERVE",
            "market_edge_status": "NOT_EVALUABLE" if "PRICE_MISSING" in missing else "OBSERVATION_ONLY",
            "line_confirmation_status": "NOT_EVALUABLE" if "LINE_MISSING" in missing else "OBSERVATION_ONLY",
            "market_families": market.get("market_families") or {},
            "bookmaker_count": market.get("bookmaker_count"),
            "price_status": market.get("price_status"),
            "snapshot_time": market.get("snapshot_time"),
            "ht_over_auxiliary_present": market.get("ht_over_auxiliary_present"),
            "ht_over_standalone_ab_allowed": False,
        },
        "external_risk_readout": {
            "status": "WAIT",
            "rest_days": external.get("rest_days"),
            "travel_status": external.get("travel_status"),
            "venue": external.get("venue"),
            "weather_status": external.get("weather_status"),
            "referee_status": external.get("referee_status"),
            "positive_external_conclusion": False,
        },
        "missing_context": sorted(missing),
        "conclusion": conclusion,
        "policy_lock": {
            "research_only": True,
            "official_grade_changed": False,
            "ab_threshold_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "realtime_reminder": False,
            "b_realtime_restored": False,
            "rf_shadow_promotion_released": False,
        },
    }


def main() -> int:
    five_payload = load_json(FIVE_DIMENSION) or {}
    samples = five_payload.get("samples", []) if isinstance(five_payload, dict) else []
    cards = [card_from_five_dimension(sample) for sample in samples[:3] if isinstance(sample, dict)]
    conclusion_counts = {label: sum(1 for card in cards if card.get("conclusion") == label) for label in ALLOWED_CONCLUSIONS}
    payload = {
        "schema_version": "v4_market_strategy_research_cards.v2",
        "generated_at": BUILD_TIMESTAMP,
        "source": "five_dimension_lite_local_artifacts_only",
        "source_five_dimension": str(FIVE_DIMENSION.relative_to(ROOT)),
        "live_api_called": False,
        "allowed_conclusions": ALLOWED_CONCLUSIONS,
        "strategy_directions_required": STRATEGY_DIRECTIONS,
        "cards": cards,
        "policy_lock": {
            "official_grade_changed": False,
            "ab_threshold_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "b_realtime_restored": False,
            "rf_shadow_promotion_released": False,
        },
    }
    missing_counts: dict[str, int] = {}
    for card in cards:
        for tag in card.get("missing_context", []):
            missing_counts[tag] = missing_counts.get(tag, 0) + 1
    summary = {
        "schema_version": "v4_market_strategy_research_cards_summary.v2",
        "generated_at": BUILD_TIMESTAMP,
        "card_count": len(cards),
        "conclusion_counts": conclusion_counts,
        "covered_markets": STRATEGY_DIRECTIONS,
        "missing_context_counts": missing_counts,
        "source_five_dimension": payload["source_five_dimension"],
        "policy_lock": payload["policy_lock"],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "cards": str(OUT_JSON.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "card_count": len(cards),
        "conclusion_counts": conclusion_counts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
