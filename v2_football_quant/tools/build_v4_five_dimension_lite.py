#!/usr/bin/env python3
"""Build V4 five-dimension Lite observation samples from local artifacts.

This builder does not call live APIs and does not alter official grades. Its
outputs are manual-source research artifacts for the new V4 data skeleton.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.v4_league_admission import classify_league


SCHEMA = ROOT / "config/v4_five_dimension_lite_schema.json"
OUT_DIR = ROOT / "data/manual_sources/v4/five_dimension_lite"
OUT_JSON = OUT_DIR / "v4_five_dimension_lite_samples_20260607.json"
OUT_SUMMARY = OUT_DIR / "v4_five_dimension_lite_summary_20260607.json"
SCOUT_DIR = ROOT / "data/daily_reports"
STATUS_DIR = ROOT / "data/runtime/status"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

ALLOWED_CONCLUSIONS = ["OBSERVE", "WAIT", "PASS"]
REQUIRED_MISSING_TAGS = [
    "PRICE_MISSING",
    "LINE_MISSING",
    "MARKET_MISSING",
    "STANDINGS_MISSING",
    "TEAM_STATS_MISSING",
    "LINEUP_MISSING",
    "LINEUP_WAIT_EVENT",
    "INJURY_SOURCE_MISSING",
    "EXTERNAL_CONTEXT_PENDING",
    "DATA_INSUFFICIENT",
]
DIMENSIONS = [
    "strength_gap",
    "tactical_efficiency",
    "squad_context",
    "market_confirmation",
    "external_risk",
]


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
            row.get("market_focus"),
            row.get("market_type"),
        ]
    ).upper()
    return {
        "1X2": any(token in market_text for token in ("MATCH WINNER", "1X2")),
        "FT_OU": any(token in market_text for token in ("GOALS OVER/UNDER", "OVER/UNDER", "TOTAL GOALS", "FULLTIME_OVER")),
        "AH_OR_HANDICAP": any(token in market_text for token in ("HANDICAP", "ASIAN")),
        "DOUBLE_CHANCE": "DOUBLE CHANCE" in market_text,
        "HT_OVER_AUXILIARY": any(token in market_text for token in ("FIRST HALF", "HT", "HALF")),
    }


def source_rows() -> list[tuple[dict[str, Any], Path]]:
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
            values = data.get(key)
            if isinstance(values, list):
                rows.extend((row, path) for row in values if isinstance(row, dict))
    return rows


def pick_samples(rows: list[tuple[dict[str, Any], Path]]) -> list[tuple[dict[str, Any], Path]]:
    picked: list[tuple[dict[str, Any], Path]] = []
    seen: set[str] = set()
    for wanted_group in ("INCLUDE_CURRENT", "OBSERVE_ONLY", "EXCLUDE_DEFAULT"):
        for row, path in rows:
            league_id = row.get("league_id") or row.get("league")
            league_name = row.get("league_name") or row.get("league") or ""
            league_type = row.get("league_type") or ""
            group = classify_league(league_id, league_name, league_type).get("admission_group")
            fid = str(row.get("fixture_id"))
            if group == wanted_group and fid not in seen:
                picked.append((row, path))
                seen.add(fid)
                break
    for row, path in rows:
        fid = str(row.get("fixture_id"))
        if fid not in seen:
            picked.append((row, path))
            seen.add(fid)
        if len(picked) >= 3:
            break
    if picked and all(price_snapshot(row).get("price_status") == "REAL_PRICE" for row, _ in picked):
        for row, path in rows:
            fid = str(row.get("fixture_id"))
            if fid not in seen and price_snapshot(row).get("price_status") == "PRICE_MISSING":
                picked[-1] = (row, path)
                break
    return picked[:3]


def missing_add(target: list[str], *tags: str) -> None:
    for tag in tags:
        if tag and tag not in target:
            target.append(tag)


def build_strength_gap(row: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    standings_present = bool(row.get("standings") or row.get("standing") or row.get("league_standings"))
    team_stats_present = bool(row.get("team_stats") or row.get("home_team_stats") or row.get("away_team_stats"))
    if not standings_present:
        missing_add(missing, "STANDINGS_MISSING")
    if not team_stats_present:
        missing_add(missing, "TEAM_STATS_MISSING")
    status = "PASS" if (standings_present or team_stats_present) else "WAIT"
    if status != "PASS":
        missing_add(missing, "DATA_INSUFFICIENT")
    return {
        "status": status,
        "league_tier": row.get("league_tier") or "UNKNOWN",
        "league_tier_reason": row.get("league_tier_reason_code") or "",
        "standings_status": "PRESENT" if standings_present else "STANDINGS_MISSING",
        "team_stats_status": "PRESENT" if team_stats_present else "TEAM_STATS_MISSING",
        "h2h": {
            "sample_count": row.get("h2h_recent5_sample_count"),
            "support_status": row.get("h2h_recent5_support_status") or row.get("h2h_assist_status") or "UNKNOWN",
            "low_sample": bool(row.get("h2h_low_sample")),
            "policy": "AUXILIARY_ONLY_NOT_PRIMARY",
        },
        "historical_form_policy": "AUXILIARY_ONLY",
    }


def build_tactical_efficiency(row: dict[str, Any], flags: dict[str, bool], missing: list[str]) -> dict[str, Any]:
    stats_present = bool(row.get("team_stats") or row.get("home_team_stats") or row.get("away_team_stats"))
    if not stats_present:
        missing_add(missing, "TEAM_STATS_MISSING", "DATA_INSUFFICIENT")
    return {
        "status": "PASS" if stats_present and flags["FT_OU"] else "WAIT",
        "goals_for_refs": {
            "home_recent5_fh_score_rate": row.get("home_recent5_fh_score_rate"),
            "away_recent5_fh_score_rate": row.get("away_recent5_fh_score_rate"),
            "home_recent10_fh_score_rate": row.get("home_recent10_fh_score_rate"),
            "away_recent10_fh_score_rate": row.get("away_recent10_fh_score_rate"),
        },
        "goals_against_refs": {
            "home_recent5_fh_concede_rate": row.get("home_recent5_fh_concede_rate"),
            "away_recent5_fh_concede_rate": row.get("away_recent5_fh_concede_rate"),
        },
        "shots_status": "TEAM_STATS_MISSING" if not stats_present else "PRESENT",
        "home_away_stats_status": "PARTIAL_RECENT_FORM_ONLY",
        "ft_ou_context_status": "PRESENT" if flags["FT_OU"] else "MARKET_MISSING",
    }


def build_squad_context(row: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    lineup = row.get("lineup") or row.get("lineup_gate")
    lineup_present = isinstance(lineup, dict) and bool(lineup) and str(lineup.get("status", "")).upper() not in {"UNKNOWN", "MISSING"}
    injury = row.get("injury") or row.get("injury_status")
    injury_source = str(row.get("injury_source") or row.get("injury_source_status") or "").upper()
    injury_known = injury_source in {"OFFICIAL", "OFFICIAL_AVAILABLE", "CONFIRMED_AVAILABLE"}
    if not injury_known and isinstance(injury, dict):
        injury_known = any(
            str(v).upper() in {"OFFICIAL", "OFFICIAL_AVAILABLE", "CONFIRMED_AVAILABLE"}
            for side in injury.values()
            for v in ([side.get("source_status"), side.get("source")] if isinstance(side, dict) else [side])
        )
    if not lineup_present:
        missing_add(missing, "LINEUP_MISSING", "LINEUP_WAIT_EVENT")
    if not injury_known:
        missing_add(missing, "INJURY_SOURCE_MISSING")
    return {
        "status": "WAIT",
        "lineup_status": "LINEUP_WAIT_EVENT" if not lineup_present else "PRESENT",
        "formation_status": "LINEUP_WAIT_EVENT" if not lineup_present else "PRESENT",
        "injury_status": "INJURY_SOURCE_MISSING" if not injury_known else "PRESENT",
        "lineup_policy": "WAIT_EVENT_UNTIL_OFFICIAL",
    }


def build_market_confirmation(row: dict[str, Any], price: dict[str, Any], flags: dict[str, bool], missing: list[str]) -> dict[str, Any]:
    non_ht_market = any(flags[name] for name in ("1X2", "FT_OU", "AH_OR_HANDICAP", "DOUBLE_CHANCE"))
    has_line = bool(price.get("line") is not None and any(flags[name] for name in ("FT_OU", "AH_OR_HANDICAP")))
    if not non_ht_market:
        missing_add(missing, "MARKET_MISSING")
    if not has_line:
        missing_add(missing, "LINE_MISSING")
    if price.get("price_status") != "REAL_PRICE":
        missing_add(missing, price.get("price_status") or "PRICE_MISSING")
    status = "PASS" if non_ht_market and has_line and price.get("price_status") == "REAL_PRICE" else "WAIT"
    return {
        "status": status,
        "market_families": {key: value for key, value in flags.items() if key != "HT_OVER_AUXILIARY"},
        "bookmaker_count": 1 if price.get("bookmaker") else 0,
        "bookmaker": price.get("bookmaker"),
        "market": price.get("market"),
        "line": price.get("line"),
        "odds": price.get("odds"),
        "snapshot_time": price.get("snapshot_time"),
        "price_status": price.get("price_status"),
        "ht_over_auxiliary_present": flags["HT_OVER_AUXILIARY"],
        "ht_over_standalone_ab_allowed": False,
    }


def build_external_risk(row: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    missing_add(missing, "EXTERNAL_CONTEXT_PENDING")
    return {
        "status": "WAIT",
        "rest_days": {
            "home": row.get("days_since_last_official_match_home"),
            "away": row.get("days_since_last_official_match_away"),
            "status": "PLACEHOLDER_ONLY",
        },
        "travel_status": "EXTERNAL_CONTEXT_PENDING",
        "venue": row.get("venue") or row.get("venue_name") or "",
        "weather_status": "EXTERNAL_CONTEXT_PENDING",
        "referee_status": "EXTERNAL_CONTEXT_PENDING",
    }


def conclusion_for(league_policy: dict[str, Any], dimensions: dict[str, dict[str, Any]], missing: list[str]) -> str:
    if not league_policy.get("strategy_pool_allowed"):
        return "PASS"
    market_pass = dimensions["market_confirmation"].get("status") == "PASS"
    strength_pass = dimensions["strength_gap"].get("status") == "PASS"
    if market_pass and strength_pass and "DATA_INSUFFICIENT" not in missing:
        return "OBSERVE"
    return "WAIT"


def sample_from_row(row: dict[str, Any], source_path: Path) -> dict[str, Any]:
    league_id = row.get("league_id") or row.get("league")
    league_name = row.get("league_name") or row.get("league") or ""
    league_type = row.get("league_type") or ""
    league_policy = classify_league(league_id, league_name, league_type)
    price = price_snapshot(row)
    flags = market_family_flags(row, price)
    missing: list[str] = []
    dimensions = {
        "strength_gap": build_strength_gap(row, missing),
        "tactical_efficiency": build_tactical_efficiency(row, flags, missing),
        "squad_context": build_squad_context(row, missing),
        "market_confirmation": build_market_confirmation(row, price, flags, missing),
        "external_risk": build_external_risk(row, missing),
    }
    if not missing:
        missing_add(missing, "DATA_INSUFFICIENT")
    missing_sorted = sorted(set(missing))
    conclusion = conclusion_for(league_policy, dimensions, missing_sorted)
    return {
        "schema_version": "v4_five_dimension_lite_sample.v1",
        "card_type": "FIVE_DIMENSION_LITE_OBSERVATION",
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
        "league_admission_status": league_policy,
        **dimensions,
        "missing_context": missing_sorted,
        "conclusion_guard": {
            "conclusion": conclusion,
            "allowed_conclusions": ALLOWED_CONCLUSIONS,
            "not_recommendation": True,
            "not_betting_advice": True,
            "official_grade_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "b_realtime_restored": False,
            "rf_shadow_promotion_released": False,
        },
    }


def main() -> int:
    samples = [sample_from_row(row, path) for row, path in pick_samples(source_rows())]
    payload = {
        "schema_version": "v4_five_dimension_lite.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source": "existing_local_artifacts_only",
        "schema_ref": str(SCHEMA.relative_to(ROOT)),
        "live_api_called": False,
        "allowed_conclusions": ALLOWED_CONCLUSIONS,
        "dimensions_required": DIMENSIONS,
        "missing_context_required": REQUIRED_MISSING_TAGS,
        "samples": samples,
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
    conclusion_counts = {label: 0 for label in ALLOWED_CONCLUSIONS}
    for sample in samples:
        conclusion_counts[sample["conclusion_guard"]["conclusion"]] += 1
        for tag in sample.get("missing_context", []):
            missing_counts[tag] = missing_counts.get(tag, 0) + 1
    summary = {
        "schema_version": "v4_five_dimension_lite_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "sample_count": len(samples),
        "dimensions_required": DIMENSIONS,
        "conclusion_counts": conclusion_counts,
        "missing_context_counts": missing_counts,
        "policy_lock": payload["policy_lock"],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "samples": str(OUT_JSON.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "sample_count": len(samples),
        "conclusion_counts": conclusion_counts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
