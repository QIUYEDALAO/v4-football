#!/usr/bin/env python3
"""Build V4 market strategy research cards from existing local artifacts.

No live API is called. The output is manual-source research material, not
runtime state and not an official strategy signal.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.v4_league_admission import admission_rule_status, classify_league


OUT_DIR = ROOT / "data/manual_sources/v4/market_strategy_research_cards"
OUT_JSON = OUT_DIR / "v4_market_strategy_research_cards_20260606.json"
OUT_SUMMARY = OUT_DIR / "v4_market_strategy_research_cards_summary_20260606.json"
SCOUT_DIR = ROOT / "data/daily_reports"
STATUS_DIR = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))
BUILD_TIMESTAMP = "2026-06-06T00:00:00+08:00"

STRATEGY_DIRECTIONS = [
    "FULLTIME_OVER",
    "HANDICAP_HOME_AWAY",
    "DOUBLE_CHANCE_STRONG_SIDE",
    "HT_OVER_AUXILIARY",
]
ALLOWED_CONCLUSIONS = ["OBSERVE", "WAIT", "PASS"]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def price_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    price_source = first_present(row, ("price_source", "opening_market_source", "odds_source"))
    odds_source = str(row.get("odds_source") or price_source or "")
    paper_forbidden = "paper_default" in odds_source.lower()
    bookmaker = first_present(row, ("bookmaker", "opening_market_bookmaker_used"))
    market = first_present(row, ("market", "opening_market_market_name", "market_name"))
    line = first_present(row, ("line", "opening_ft_ou_line", "opening_ah_line", "opening_ht_ou_line", "prematch_ht_line"))
    odds = first_present(row, ("odds", "opening_ft_ou_over_odds", "opening_ht_ou_over_odds", "prematch_over_odds"))
    snapshot_time = first_present(row, ("snapshot_time", "opening_market_snapshot_time", "market_snapshot_time"))
    if paper_forbidden:
        return {
            "price_source": price_source or odds_source,
            "bookmaker": "",
            "market": "",
            "line": None,
            "odds": None,
            "snapshot_time": "",
            "price_status": "PAPER_PROXY_FORBIDDEN",
        }
    has_real = bool(bookmaker and market and line is not None and odds is not None and snapshot_time)
    return {
        "price_source": price_source or ("artifact_market_snapshot" if has_real else ""),
        "bookmaker": bookmaker or "",
        "market": market or "",
        "line": line,
        "odds": odds,
        "snapshot_time": snapshot_time or "",
        "price_status": "REAL_PRICE" if has_real else "PRICE_MISSING",
    }


def market_family_flags(row: dict[str, Any], price: dict[str, Any]) -> dict[str, bool]:
    market_text = " ".join(
        str(x or "")
        for x in [
            price.get("market"),
            row.get("opening_market_market_name"),
            row.get("opening_market_bet_name"),
        ]
    ).upper()
    return {
        "1X2": any(token in market_text for token in ("MATCH WINNER", "1X2")),
        "FT_OU": any(token in market_text for token in ("FULLTIME_OVER", "GOALS OVER/UNDER", "OVER/UNDER", "TOTAL GOALS")),
        "AH_OR_HANDICAP": any(token in market_text for token in ("HANDICAP", "ASIAN")),
        "DOUBLE_CHANCE": "DOUBLE CHANCE" in market_text,
        "HT_OVER_AUXILIARY": any(token in market_text for token in ("FIRST HALF", "HT", "HALF")),
    }


def strength_gap(row: dict[str, Any]) -> dict[str, Any]:
    score = first_present(row, ("candidate_score", "best_score", "rf_shadow_score", "recent_form_primary_score"))
    confidence = first_present(row, ("rf_shadow_confidence", "confidence"))
    return {
        "status": "DATA_INSUFFICIENT" if score in (None, "", "DATA_MISSING") else "OBSERVABLE",
        "score_ref": score if score not in (None, "") else "DATA_INSUFFICIENT",
        "confidence_ref": confidence if confidence not in (None, "") else "DATA_INSUFFICIENT",
        "notes": ["historical_form_is_auxiliary_only"],
    }


def strategy_rows(row: dict[str, Any], price: dict[str, Any], flags: dict[str, bool]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for direction in STRATEGY_DIRECTIONS:
        if direction == "FULLTIME_OVER":
            has_market = flags["FT_OU"]
            has_line = bool(has_market and price.get("line") is not None)
        elif direction == "HANDICAP_HOME_AWAY":
            has_market = flags["AH_OR_HANDICAP"]
            has_line = bool(has_market and price.get("line") is not None)
        elif direction == "DOUBLE_CHANCE_STRONG_SIDE":
            has_market = flags["DOUBLE_CHANCE"]
            has_line = True
        else:
            has_market = flags["HT_OVER_AUXILIARY"]
            has_line = bool(has_market and price.get("line") is not None)

        missing = []
        if not has_market:
            missing.append("MARKET_MISSING")
        if direction != "DOUBLE_CHANCE_STRONG_SIDE" and not has_line:
            missing.append("LINE_MISSING")
        if price.get("price_status") != "REAL_PRICE":
            missing.append(price.get("price_status") or "PRICE_MISSING")

        status = "WAIT" if missing else "OBSERVE"
        if direction == "HT_OVER_AUXILIARY":
            status = "WAIT" if missing else "WAIT"
            missing.append("HT_OVER_AUXILIARY_ONLY")
        rows.append({
            "direction": direction,
            "market_present": has_market,
            "line_present": has_line,
            "price_status": price.get("price_status"),
            "status": status,
            "missing_context": sorted(set(missing)),
            "standalone_ab_allowed": False if direction == "HT_OVER_AUXILIARY" else None,
        })
    return rows


def conclusion_for(league_policy: dict[str, Any], directions: list[dict[str, Any]], missing: list[str]) -> str:
    if not league_policy.get("strategy_pool_allowed"):
        return "PASS"
    non_ht_observe = [
        row for row in directions
        if row.get("direction") != "HT_OVER_AUXILIARY" and row.get("status") == "OBSERVE"
    ]
    if non_ht_observe and not missing:
        return "OBSERVE"
    return "WAIT"


def card_from_row(row: dict[str, Any], source_path: Path) -> dict[str, Any]:
    league_id = row.get("league_id") or row.get("league")
    league_name = row.get("league_name") or row.get("league") or ""
    league_type = row.get("league_type") or ""
    league_policy = classify_league(league_id, league_name, league_type)
    price = price_snapshot(row)
    flags = market_family_flags(row, price)
    families = [name for name, present in flags.items() if present and name != "HT_OVER_AUXILIARY"]
    admission = admission_rule_status(
        market_families=families,
        bookmaker_count=1 if price.get("bookmaker") else 0,
        has_ft_ou_line=bool(flags["FT_OU"] and price.get("line") is not None),
        has_handicap_line=bool(flags["AH_OR_HANDICAP"] and price.get("line") is not None),
        has_standings=False,
        has_team_stats=False,
        has_injuries=False,
        has_lineup=False,
    )
    directions = strategy_rows(row, price, flags)
    missing = sorted(set(admission.get("admission_blockers", []) + admission.get("data_gap_tags", [])))
    if price.get("price_status") != "REAL_PRICE":
        missing.append(price.get("price_status") or "PRICE_MISSING")
    if not any(flags.values()):
        missing.append("MARKET_MISSING")
    if not any((flags["FT_OU"], flags["AH_OR_HANDICAP"])) or price.get("line") is None:
        missing.append("LINE_MISSING")
    if not missing:
        missing.append("DATA_INSUFFICIENT")
    conclusion = conclusion_for(league_policy, directions, missing)
    return {
        "schema_version": "v4_market_strategy_research_card.v1",
        "card_type": "MARKET_STRATEGY_RESEARCH",
        "source_artifact": str(source_path.relative_to(ROOT)),
        "match_info": {
            "fixture_id": row.get("fixture_id"),
            "home": row.get("home") or row.get("home_team") or "?",
            "away": row.get("away") or row.get("away_team") or "?",
            "league": league_name or "?",
            "league_id": league_id,
            "kickoff_time": first_present(row, ("kickoff_time", "kickoff", "kickoff_local")) or "",
            "official_grade_snapshot": row.get("official_grade") or row.get("grade") or "UNKNOWN",
            "official_grade_unchanged": True,
        },
        "league_admission_status": {
            **league_policy,
            "admission_info_complete": admission.get("admission_info_complete"),
            "admission_blockers": admission.get("admission_blockers", []),
        },
        "strategy_directions": directions,
        "strength_gap": strength_gap(row),
        "market_confirmation": {
            "status": "MISSING" if any(d.get("market_present") for d in directions[:3]) is False else "PARTIAL",
            "market_families_present": families,
            "ht_over_auxiliary_present": flags["HT_OVER_AUXILIARY"],
            "no_standalone_ht_over": True,
        },
        "price_quality": price,
        "data_quality": {
            "status": "DATA_INSUFFICIENT" if missing else "OBSERVABLE",
            "injury_status": "INJURY_SOURCE_MISSING",
            "lineup_status": "LINEUP_WAIT_EVENT",
            "standings_or_team_stats": "DATA_INSUFFICIENT",
        },
        "missing_context": sorted(set(missing)),
        "conclusion": conclusion,
        "safety": {
            "research_only": True,
            "not_official_strategy": True,
            "official_grade_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "realtime_reminder": False,
        },
    }


def candidate_rows() -> list[tuple[dict[str, Any], Path]]:
    rows: list[tuple[dict[str, Any], Path]] = []
    for path in sorted(SCOUT_DIR.glob("scout_v4_202606*.json"), reverse=True) + sorted(SCOUT_DIR.glob("scout_v4_20260531.json"), reverse=True):
        data = load_json(path)
        if isinstance(data, list):
            rows.extend((row, path) for row in data if isinstance(row, dict))
    for path in sorted(STATUS_DIR.glob("v4_official_candidate_view_202606*.json"), reverse=True):
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        for key in ("A_candidates", "B_candidates", "C_candidates", "SKIP_candidates"):
            rows.extend((row, path) for row in data.get(key, []) if isinstance(row, dict))
    return rows


def pick_samples(rows: list[tuple[dict[str, Any], Path]]) -> list[tuple[dict[str, Any], Path]]:
    picked: list[tuple[dict[str, Any], Path]] = []
    wanted = ["INCLUDE_CURRENT", "OBSERVE_ONLY", "EXCLUDE_DEFAULT"]
    seen: set[str] = set()
    for wanted_group in wanted:
        group_rows: list[tuple[dict[str, Any], Path]] = []
        for row, path in rows:
            league_id = row.get("league_id") or row.get("league")
            league_name = row.get("league_name") or row.get("league") or ""
            league_type = row.get("league_type") or ""
            group = classify_league(league_id, league_name, league_type).get("admission_group")
            if group == wanted_group and str(row.get("fixture_id")) not in seen:
                group_rows.append((row, path))
        if wanted_group in {"OBSERVE_ONLY", "EXCLUDE_DEFAULT"}:
            group_rows.sort(key=lambda item: 0 if price_snapshot(item[0]).get("price_status") != "REAL_PRICE" else 1)
        if group_rows:
            row, path = group_rows[0]
            picked.append((row, path))
            seen.add(str(row.get("fixture_id")))
    if len(picked) < 3:
        for row, path in rows:
            fid = str(row.get("fixture_id"))
            if fid not in seen:
                picked.append((row, path))
                seen.add(fid)
            if len(picked) >= 3:
                break
    return picked[:3]


def main() -> int:
    samples = [card_from_row(row, path) for row, path in pick_samples(candidate_rows())]
    payload = {
        "schema_version": "v4_market_strategy_research_cards.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source": "existing_local_artifacts_only",
        "live_api_called": False,
        "allowed_conclusions": ALLOWED_CONCLUSIONS,
        "strategy_directions_required": STRATEGY_DIRECTIONS,
        "missing_context_required": [
            "PRICE_MISSING",
            "LINE_MISSING",
            "MARKET_MISSING",
            "INJURY_SOURCE_MISSING",
            "LINEUP_MISSING",
            "LINEUP_WAIT_EVENT",
            "DATA_INSUFFICIENT",
        ],
        "cards": samples,
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
    summary = {
        "schema_version": "v4_market_strategy_research_cards_summary.v1",
        "generated_at": payload["generated_at"],
        "card_count": len(samples),
        "conclusion_counts": {label: sum(1 for c in samples if c.get("conclusion") == label) for label in ALLOWED_CONCLUSIONS},
        "covered_markets": STRATEGY_DIRECTIONS,
        "missing_context_counts": {},
        "policy_lock": payload["policy_lock"],
    }
    counts: dict[str, int] = {}
    for card in samples:
        for tag in card.get("missing_context", []):
            counts[tag] = counts.get(tag, 0) + 1
    summary["missing_context_counts"] = counts
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "cards": str(OUT_JSON.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "card_count": len(samples),
        "conclusion_counts": summary["conclusion_counts"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
