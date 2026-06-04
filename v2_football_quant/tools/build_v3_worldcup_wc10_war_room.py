#!/usr/bin/env python3
from __future__ import annotations

import json
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/v3_worldcup"
OUT_DIR = V3 / "war_room"
STATUS_DIR = ROOT / "data/runtime/status"

ROSTERS = V3 / "rosters/worldcup_rosters_20260526.json"
PROFILES = V3 / "team_profiles/team_profiles_20260526.json"
DELTAS = V3 / "team_profiles/roster_delta_20260526.json"
WATCH = V3 / "market_baseline/v3_perception_gap_roster_watchlist_20260526.json"
SUPPLEMENT_REPORT = ROOT / "data/runtime/v3_worldcup/supplement_reports/v3_worldcup_supplement_coverage_20260602.json"
FINAL_SQUAD_REPORT = ROOT / "data/runtime/v3_worldcup/final_squads/v3_worldcup_final_squad_canonicalization_20260602.json"
SOURCE_GATE_REPORT = ROOT / "data/runtime/v3_worldcup/source_authorization/v3_worldcup_source_authorization_gate_20260602.json"
DRYRUN_REPORT = ROOT / "data/runtime/v3_worldcup/final_squads/v3_worldcup_authorized_final_squad_ingestion_dryrun_20260602.json"
WC5D_REVIEW_ARTIFACT = ROOT / "data/runtime/v3_worldcup/final_squads/v3_wc5d_candidate_review_artifact_20260602.json"
HISTORICAL_MARKET_SUMMARY = ROOT / "data/runtime/v3_worldcup/historical_market_baseline/20260602/v3_wc4a_historical_market_summary_v1.json"
PERCEPTION_GAP_BLUEPRINT = ROOT / "data/v3_worldcup/perception_gap_blueprint/v3_worldcup_perception_gap_blueprint_20260602.json"
VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
MATCH_LEVEL_PG_DRYRUN_CSV = ROOT / "data/runtime/v3_worldcup/perception_gap_dryrun/v3_wc4d_match_level_perception_gap_dryrun_20260603.csv"
MATCH_LEVEL_PG_DRYRUN_STATUS = ROOT / "data/runtime/v3_worldcup/perception_gap_dryrun/v3_wc4d_match_level_perception_gap_dryrun_status_20260603.json"
TACTICAL_PROFILE_LAYER = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
CLOSING_1X2_LAYER = ROOT / "data/v3_worldcup/closing_1x2_market_structure/v3_worldcup_closing_1x2_market_structure_20260604.json"

CST = timezone(timedelta(hours=8))


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def _watch_item(x: dict[str, Any]) -> dict[str, Any]:
    team = str(x.get("team") or x.get("country") or "UNKNOWN")
    direction = str(x.get("gap_direction") or "ALIGNED")
    signal_type = "UNDERVALUE_WATCH" if direction == "UNDERRATED" else ("OVERHYPE_RISK_WATCH" if direction == "OVERRATED" else "WATCHLIST_ONLY")
    missing = [
        "caps_goals_minutes",
        "injury_reports",
        "friendly_form",
        "market_baseline",
        "club_form",
        "coach_profiles",
        "wc_history",
    ]
    return {
        "team": team,
        "signal_type": signal_type,
        "reason": str(x.get("reason") or x.get("roster_reality") or "Roster intelligence pre-screen only"),
        "confidence": str(x.get("confidence") or "LOW"),
        "data_coverage": "SUPPLEMENT_INCOMPLETE",
        "missing_supplements": missing,
        "action_hint": "NEED_SUPPLEMENT" if signal_type != "WATCHLIST_ONLY" else "WATCHLIST_ONLY",
    }


def _candidate_review_view(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    teams = payload.get("teams") if isinstance(payload.get("teams"), list) else []
    safe = [t for t in teams if isinstance(t, dict) and bool(t.get("safe_for_candidate_review"))]
    hold = [t for t in teams if isinstance(t, dict) and not bool(t.get("safe_for_candidate_review"))]
    status_dist = meta.get("status_distribution") if isinstance(meta.get("status_distribution"), dict) else {}
    by_name = {str(t.get("team_name") or "").strip(): t for t in teams if isinstance(t, dict)}
    focus_names = ["England", "Uzbekistan", "Turkey", "France", "Sweden", "Haiti"]
    focus_teams = [by_name[n] for n in focus_names if n in by_name]
    return {
        "candidate_review_status": "CANDIDATE_REVIEW_ONLY",
        "candidate_review_summary": {
            "source_status": "CANDIDATE_REVIEW_ONLY",
            "official_final_squad_written": bool(meta.get("official_final_squad_written")),
            "final_squad_complete": False,
            "teams_total": len(teams),
            "teams_safe": int(meta.get("safe_teams") or len(safe)),
            "teams_hold": int(meta.get("hold_teams") or len(hold)),
            "api_teams": 48,
            "api_players": 1381,
            "wikipedia_teams": 48,
            "wikipedia_players": 1266,
            "official_confirmed": int(status_dist.get("OFFICIAL_CONFIRMED") or 0),
            "primary_blocker": "Turkey final 26 not found",
        },
        "candidate_review_counts": {
            "OFFICIAL_CONFIRMED": int(status_dist.get("OFFICIAL_CONFIRMED") or 0),
            "API_CLEAN_CANDIDATE": int(status_dist.get("API_CLEAN_CANDIDATE") or 0),
            "API_WIKI_ALIGNED_CANDIDATE": int(status_dist.get("API_WIKI_ALIGNED_CANDIDATE") or 0),
            "WIKI_PREFERRED_API_POOL_OVERFULL": int(status_dist.get("WIKI_PREFERRED_API_POOL_OVERFULL") or 0),
            "API_INCOMPLETE_NEED_REVIEW": int(status_dist.get("API_INCOMPLETE_NEED_REVIEW") or 0),
            "PROVISIONAL_OVERFULL_NEED_REVIEW": int(status_dist.get("PROVISIONAL_OVERFULL_NEED_REVIEW") or 0),
        },
        "candidate_review_safe_teams": safe,
        "candidate_review_hold_teams": hold,
        "candidate_review_focus_teams": focus_teams,
        "candidate_review_safety_guard": {
            "candidate_review_only": True,
            "official_final_squad_written": False,
            "final_squad_complete": False,
            "no_betting_recommendations": True,
            "no_v4_changes": True,
        },
    }


def _historical_market_view(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {
            "historical_market_baseline_status": "HISTORICAL_MARKET_BASELINE_MISSING_WARN_ONLY",
            "historical_market_baseline_summary": {},
            "historical_market_baseline_years": [],
            "historical_market_baseline_counts": {},
            "historical_market_baseline_key_rates": {},
            "historical_market_baseline_data_quality": {"qualifiers_in_baseline": False, "source": "DATA_MISSING"},
            "historical_market_baseline_safety_guard": {"observation_only": True, "no_betting_recommendations": True, "no_v4_changes": True},
        }
    years = summary.get("matches_by_year") if isinstance(summary.get("matches_by_year"), dict) else {}
    return {
        "historical_market_baseline_status": "READY",
        "historical_market_baseline_summary": {
            "source_status": "HISTORICAL_MARKET_BASELINE_READY",
            "data_source": "WorldCup2026.xlsx + TheStatsAPI cache",
            "total_world_cup_finals_matches": int(summary.get("total_world_cup_finals_matches") or 0),
            "qualifiers_in_baseline": False,
        },
        "historical_market_baseline_years": [{"year": int(k), "matches": int(v)} for k, v in sorted(years.items())],
        "historical_market_baseline_counts": {
            "heavy_favorite_count": int(summary.get("heavy_favorite_count") or 0),
            "strong_favorite_count": int(summary.get("strong_favorite_count") or 0),
            "favorite_failed_count": int(summary.get("favorite_failed_count") or 0),
            "underdog_upset_count": int(summary.get("underdog_upset_count") or 0),
            "draw_result_count": int(summary.get("draw_result_count") or 0),
            "ht_draw_count": int(summary.get("ht_draw_count") or 0),
            "over_2_5_count": int(summary.get("over_2_5_count") or 0),
            "btts_count": int(summary.get("btts_count") or 0),
        },
        "historical_market_baseline_key_rates": {
            "heavy_favorite_win_rate": float(summary.get("heavy_favorite_win_rate") or 0),
            "strong_favorite_win_rate": float(summary.get("strong_favorite_win_rate") or 0),
            "favorite_failed_rate": float(summary.get("favorite_failed_rate") or 0),
        },
        "historical_market_baseline_data_quality": {
            "qualifiers_in_baseline": False,
            "qualifiers_rows": 889,
            "thestatsapi_match_coverage": summary.get("thestatsapi_match_id_coverage") or "128/192",
            "thestatsapi_odds_coverage": {"2018": summary.get("thestatsapi_odds_2018"), "2022": summary.get("thestatsapi_odds_2022")},
            "thestatsapi_lineup_coverage": {"2018": summary.get("thestatsapi_lineups_2018"), "2022": summary.get("thestatsapi_lineups_2022")},
            "xg_statistics_events_status": "UNAVAILABLE_SUPPLEMENT_ONLY",
        },
        "historical_market_baseline_safety_guard": {
            "observation_only": True,
            "no_betting_recommendations": True,
            "not_v4_official_grade": True,
            "no_v4_changes": True,
        },
    }


def _perception_gap_blueprint_view(blueprint: dict[str, Any]) -> dict[str, Any]:
    if not blueprint:
        return {
            "perception_gap_blueprint_status": "PERCEPTION_GAP_BLUEPRINT_MISSING_WARN_ONLY",
            "perception_gap_input_layers": {},
            "perception_gap_output_tags": [],
            "perception_gap_safety_guard": {
                "observation_only": True,
                "betting_recommendation": False,
                "affects_v4_grade": False,
                "auto_bet_allowed": False,
                "official_final_squad_required": False,
            },
            "perception_gap_next_required_inputs": [],
        }
    return {
        "perception_gap_blueprint_status": blueprint.get("status") or "PERCEPTION_GAP_SCORING_BLUEPRINT_READY",
        "perception_gap_input_layers": blueprint.get("input_layers") if isinstance(blueprint.get("input_layers"), dict) else {},
        "perception_gap_output_tags": blueprint.get("output_tags") if isinstance(blueprint.get("output_tags"), list) else [],
        "perception_gap_safety_guard": blueprint.get("safety_guard") if isinstance(blueprint.get("safety_guard"), dict) else {
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
            "auto_bet_allowed": False,
            "official_final_squad_required": False,
        },
        "perception_gap_next_required_inputs": blueprint.get("next_required_inputs") if isinstance(blueprint.get("next_required_inputs"), list) else [],
    }


def _venue_stress_view(payload: dict[str, Any]) -> dict[str, Any]:
    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}
    rows = payload.get("venues") if isinstance(payload.get("venues"), list) else []
    focus = payload.get("focus_venue_rows") if isinstance(payload.get("focus_venue_rows"), list) else []
    if not payload:
        return {
            "venue_stress_status": "VENUE_STRESS_MISSING_WARN_ONLY",
            "venue_stress_count": 0,
            "venue_stress_focus_count": 0,
            "venue_stress_tags_allowed": [],
            "venue_stress_venues": [],
            "venue_stress_focus_venues": [],
            "venue_stress_safety_guard": {
                "observation_only": True,
                "betting_recommendation": False,
                "video_claim_not_scoring_input": True,
            },
        }
    return {
        "venue_stress_status": "VENUE_STRESS_READY",
        "venue_stress_count": int(payload.get("venue_count") or len(rows)),
        "venue_stress_focus_count": int(payload.get("focus_venue_count") or len(focus)),
        "venue_stress_tags_allowed": payload.get("stress_tags_allowed") if isinstance(payload.get("stress_tags_allowed"), list) else [],
        "venue_stress_venues": rows,
        "venue_stress_focus_venues": focus,
        "venue_stress_safety_guard": {
            "observation_only": guard.get("observation_only") is True,
            "betting_recommendation": False,
            "no_stake": guard.get("no_stake", True),
            "no_v4_changes": guard.get("no_v4_changes", True),
            "video_claim_not_scoring_input": guard.get("video_claim_not_scoring_input", True),
        },
    }


def _match_level_perception_gap_dryrun_view(csv_path: Path, status_path: Path) -> dict[str, Any]:
    status = _load(status_path)
    rows: list[dict[str, Any]] = []
    if csv_path.exists():
        try:
            with csv_path.open(encoding="utf-8", newline="") as f:
                rows = [dict(row) for row in csv.DictReader(f)]
        except Exception:
            rows = []
    if not rows:
        return {
            "match_level_perception_gap_dryrun_status": "DRY_RUN_MISSING_WARN_ONLY",
            "match_level_perception_gap_dryrun_sample_count": 0,
            "match_level_perception_gap_dryrun_samples": [],
            "match_level_perception_gap_dryrun_safety_guard": {
                "observation_only": True,
                "betting_recommendation": False,
                "affects_v4_grade": False,
                "scoring_changed": False,
            },
        }
    samples = []
    for row in rows:
        samples.append(
            {
                "sample_id": row.get("sample_id") or "",
                "match_id": row.get("match_id") or "",
                "match": row.get("match") or f"{row.get('home_team', '')} vs {row.get('away_team', '')}".strip(),
                "home_team": row.get("home_team") or "",
                "away_team": row.get("away_team") or "",
                "utc_date": row.get("utc_date") or "",
                "venue": row.get("venue") or row.get("dryrun_venue") or "",
                "venue_city": row.get("dryrun_venue_city") or "",
                "venue_country": row.get("dryrun_venue_country") or "",
                "sample_priority": row.get("sample_priority") or "",
                "dryrun_market_data_sample": row.get("dryrun_market_data_sample") == "true",
                "real_market_cache_used": row.get("real_market_cache_used") == "true",
                "market_upgrade_case": row.get("market_upgrade_case") or "",
                "dryrun_has_odds": row.get("dryrun_has_odds") == "true",
                "dryrun_has_xg": row.get("dryrun_has_xg") == "true",
                "dryrun_has_api_prediction": row.get("dryrun_has_api_prediction") == "true",
                "market_data_status": row.get("market_data_status") or row.get("market_gap_tag") or "CURRENT_MARKET_DATA_MISSING",
                "market_data_status_source": row.get("market_data_status_source") or "DRYRUN_SIMULATED_INPUT_NOT_REAL_CACHE",
                "market_gap_tag": row.get("market_gap_tag") or "DATA_INSUFFICIENT",
                "venue_stress_tag": row.get("venue_stress_tag") or "WATCH_ONLY",
                "upset_watch_definition": row.get("upset_watch_definition") or "",
                "venue_upset_watch_scoring": row.get("venue_upset_watch_scoring") == "true",
                "home_candidate_status": row.get("home_candidate_status") or "",
                "away_candidate_status": row.get("away_candidate_status") or "",
                "squad_data_quality": row.get("squad_data_quality") or "SQUAD_DATA_INSUFFICIENT",
                "perception_gap_tag": row.get("perception_gap_tag") or "DATA_INSUFFICIENT;WATCH_ONLY",
                "data_insufficient_reason": row.get("data_insufficient_reason") or "",
                "odds_available": row.get("odds_available") == "true",
                "xg_available": row.get("xg_available") == "true",
                "observation_only": row.get("observation_only") == "true",
                "betting_recommendation": row.get("betting_recommendation") == "true",
                "affects_v4_grade": row.get("affects_v4_grade") == "true",
                "scoring_changed": row.get("scoring_changed") == "true",
            }
        )
    return {
        "match_level_perception_gap_dryrun_status": "DRY_RUN_READY",
        "match_level_perception_gap_dryrun_sample_count": int(status.get("sample_count") or len(samples)),
        "match_level_perception_gap_dryrun_samples": samples,
        "match_level_perception_gap_dryrun_coverage": {
            "has_high_heat_or_humidity_sample": status.get("has_high_heat_or_humidity_sample") is True,
            "has_altitude_sample": status.get("has_altitude_sample") is True,
            "has_ordinary_sample": status.get("has_ordinary_sample") is True,
            "has_popular_strong_team_sample": status.get("has_popular_strong_team_sample") is True,
            "has_mixed_pressure_sample": status.get("has_mixed_pressure_sample") is True,
            "local_2026_odds_or_prediction_available_for_samples": status.get("local_2026_odds_or_prediction_available_for_samples") is True,
        },
        "match_level_perception_gap_dryrun_market_data_status_path": status.get("market_data_status_path") if isinstance(status.get("market_data_status_path"), list) else [
            "CURRENT_MARKET_DATA_MISSING",
            "MARKET_DATA_PARTIAL",
            "MARKET_DATA_AVAILABLE",
        ],
        "match_level_perception_gap_dryrun_market_data_status_cases": status.get("market_data_status_cases") if isinstance(status.get("market_data_status_cases"), dict) else {},
        "match_level_perception_gap_dryrun_real_market_cache_used": status.get("real_market_cache_used") is True,
        "match_level_perception_gap_dryrun_upset_watch_definition": status.get("upset_watch_definition") or "historical_data_insufficient_for_probability",
        "match_level_perception_gap_dryrun_safety_guard": {
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
            "scoring_changed": False,
            "venue_upset_watch_scoring": False,
            "recommendation_output": False,
        },
    }


def _tactical_profile_view(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {
            "tactical_profile_status": "TACTICAL_PROFILE_MISSING_WARN_ONLY",
            "tactical_profile_team_count": 0,
            "tactical_profile_real_sample_team_count": 0,
            "tactical_profile_data_insufficient_team_count": 0,
            "tactical_profile_matchup_count": 0,
            "tactical_profile_unique_formations_count": 0,
            "tactical_profile_allowed_tags": [],
            "tactical_profile_focus_profiles": [],
            "tactical_profile_safety_guard": {
                "observation_only": True,
                "no_scoring": True,
                "betting_recommendation": False,
                "affects_v4_grade": False,
                "scoring_changed": False,
            },
        }
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), list) else []
    focus_names = ["Belgium", "France", "Brazil", "Spain", "England", "Mexico", "USA", "Uzbekistan"]
    by_name = {str(p.get("team") or ""): p for p in profiles if isinstance(p, dict)}
    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}
    return {
        "tactical_profile_status": payload.get("status") or "TACTICAL_PROFILE_LAYER_READY",
        "tactical_profile_team_count": int(payload.get("teams_profiled_count") or len(profiles)),
        "tactical_profile_real_sample_team_count": int(payload.get("teams_with_real_formation_samples") or 0),
        "tactical_profile_data_insufficient_team_count": int(payload.get("teams_formation_data_insufficient") or 0),
        "tactical_profile_matchup_count": int(payload.get("formation_matchup_samples_count") or 0),
        "tactical_profile_unique_formations_count": int(payload.get("unique_formations_count") or 0),
        "tactical_profile_unique_formations": payload.get("unique_formations") if isinstance(payload.get("unique_formations"), list) else [],
        "tactical_profile_allowed_tags": payload.get("allowed_observation_tags") if isinstance(payload.get("allowed_observation_tags"), list) else [],
        "tactical_profile_focus_profiles": [by_name[name] for name in focus_names if name in by_name],
        "tactical_profile_safety_guard": {
            "observation_only": guard.get("observation_only") is True,
            "no_scoring": guard.get("no_scoring") is True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
            "scoring_changed": False,
            "no_v4_changes": guard.get("no_v4_changes", True),
        },
    }


def _closing_1x2_view(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {
            "closing_1x2_status": "CLOSING_1X2_MISSING_WARN_ONLY",
            "closing_1x2_match_count": 0,
            "closing_1x2_complete": False,
            "closing_1x2_favorite_failed_rate": 0,
            "closing_1x2_favorite_failed_rate_by_band": {},
            "closing_1x2_allowed_tags": [],
            "closing_1x2_disabled_tags": [],
            "closing_1x2_focus_records": [],
            "closing_1x2_safety_guard": {
                "observation_only": True,
                "betting_recommendation": False,
                "affects_v4_grade": False,
                "scoring_changed": False,
                "no_opening_odds": True,
                "no_steam_drift": True,
            },
        }
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}
    focus = sorted(
        [r for r in records if isinstance(r, dict)],
        key=lambda r: (float(r.get("bookmaker_spread") or 0), float(r.get("max_avg_gap") or 0)),
        reverse=True,
    )[:8]
    return {
        "closing_1x2_status": payload.get("status") or "CLOSING_1X2_MARKET_STRUCTURE_READY",
        "closing_1x2_match_count": int(payload.get("total_matches") or len(records)),
        "closing_1x2_by_year": payload.get("by_year") if isinstance(payload.get("by_year"), dict) else {},
        "closing_1x2_complete": payload.get("closing_1x2_complete") is True,
        "closing_1x2_favorite_failed_rate": float(payload.get("favorite_failed_rate") or 0),
        "closing_1x2_favorite_failed_rate_by_band": payload.get("favorite_failed_rate_by_band") if isinstance(payload.get("favorite_failed_rate_by_band"), dict) else {},
        "closing_1x2_allowed_tags": payload.get("allowed_observation_tags") if isinstance(payload.get("allowed_observation_tags"), list) else [],
        "closing_1x2_disabled_tags": payload.get("disabled_tags") if isinstance(payload.get("disabled_tags"), list) else [],
        "closing_1x2_focus_records": focus,
        "closing_1x2_safety_guard": {
            "observation_only": guard.get("observation_only") is True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
            "scoring_changed": False,
            "no_opening_odds": guard.get("no_opening_odds", True),
            "no_steam_drift": guard.get("no_steam_drift", True),
            "no_fund_flow": guard.get("no_fund_flow", True),
            "no_v4_changes": guard.get("no_v4_changes", True),
        },
    }


def main() -> int:
    rosters = _load(ROSTERS)
    profiles = _load(PROFILES)
    deltas = _load(DELTAS)
    watch = _load(WATCH)
    supp = _load(SUPPLEMENT_REPORT)
    final_squad = _load(FINAL_SQUAD_REPORT)
    source_gate = _load(SOURCE_GATE_REPORT)
    dryrun = _load(DRYRUN_REPORT)
    wc5d = _load(WC5D_REVIEW_ARTIFACT)
    historical_market = _load(HISTORICAL_MARKET_SUMMARY)
    perception_gap_blueprint = _load(PERCEPTION_GAP_BLUEPRINT)
    venue_stress = _load(VENUE_STRESS)
    tactical_profile = _load(TACTICAL_PROFILE_LAYER)
    closing_1x2 = _load(CLOSING_1X2_LAYER)

    meta = rosters.get("meta") or {}
    teams_total = _safe_int(meta.get("total_teams") or 46)
    teams_with_roster = _safe_int(meta.get("teams_with_squad") or teams_total)
    players_total = _safe_int(meta.get("total_players") or 1375)

    deltas_list = deltas.get("deltas") if isinstance(deltas.get("deltas"), list) else []
    watch_list_raw = watch.get("watchlist") if isinstance(watch.get("watchlist"), list) else []
    watch_list = [_watch_item(x) for x in watch_list_raw if isinstance(x, dict)]

    undervalued = [x for x in watch_list if x["signal_type"] == "UNDERVALUE_WATCH"][:10]
    overhyped = [x for x in watch_list if x["signal_type"] == "OVERHYPE_RISK_WATCH"][:10]
    high_stability = sorted(
        [x for x in deltas_list if isinstance(x, dict)],
        key=lambda x: _safe_int(x.get("core_stability_score")),
        reverse=True,
    )[:8]
    high_spine = sorted(
        [x for x in deltas_list if isinstance(x, dict)],
        key=lambda x: _safe_int(x.get("spine_change_score")),
        reverse=True,
    )[:8]
    age_risk = sorted(
        [x for x in deltas_list if isinstance(x, dict)],
        key=lambda x: _safe_int(x.get("age_risk_score")),
        reverse=True,
    )[:8]
    depth_risk = sorted(
        [x for x in deltas_list if isinstance(x, dict)],
        key=lambda x: _safe_int(x.get("depth_score")),
    )[:8]

    warn_only_items = [
        "CAPS_GOALS_MINUTES_SUPPLEMENT_MISSING",
        "INJURY_SUPPLEMENT_MISSING",
        "FRIENDLY_FORM_SUPPLEMENT_MISSING",
        "MARKET_BASELINE_SUPPLEMENT_MISSING",
        "CLUB_FORM_SUPPLEMENT_MISSING",
        "COACH_PROFILE_SUPPLEMENT_MISSING",
        "WC_HISTORY_SUPPLEMENT_MISSING",
    ]

    supp_cov = supp.get("coverage_by_category") if isinstance(supp.get("coverage_by_category"), dict) else {}
    caps_cov = (supp_cov.get("caps_goals_minutes") or {}).get("coverage_status")
    injury_cov = (supp_cov.get("injuries") or {}).get("coverage_status")
    friendly_cov = (supp_cov.get("friendly_form") or {}).get("coverage_status")
    market_cov = (supp_cov.get("market_baseline") or {}).get("coverage_status")
    supp_status = supp.get("status") if supp else "DATA_MISSING"
    if supp and isinstance(supp.get("warn_only_items"), list):
        for x in supp["warn_only_items"]:
            if x not in warn_only_items:
                warn_only_items.append(x)

    fs_status = final_squad.get("status") if final_squad else "DATA_MISSING"
    fs_found = final_squad.get("final_squad_files_found") if isinstance(final_squad.get("final_squad_files_found"), list) else []
    fs_missing_count = int(final_squad.get("teams_missing_count") or max(0, 48 - teams_total)) if final_squad else max(0, 48 - teams_total)
    fs_missing_list = final_squad.get("teams_missing_list") if isinstance(final_squad.get("teams_missing_list"), list) else []
    fs_complete = int(final_squad.get("final_26_complete_teams_count") or 0) if final_squad else 0
    fs_coverage_status = final_squad.get("final_squad_coverage_status") if final_squad else "DATA_MISSING"
    if final_squad and isinstance(final_squad.get("warn_only_items"), list):
        for x in final_squad["warn_only_items"]:
            if x not in warn_only_items:
                warn_only_items.append(x)
    if source_gate and isinstance(source_gate.get("warn_only_items"), list):
        for x in source_gate["warn_only_items"]:
            if x not in warn_only_items:
                warn_only_items.append(x)
    if dryrun and isinstance(dryrun.get("warn_only_items"), list):
        for x in dryrun["warn_only_items"]:
            if x not in warn_only_items:
                warn_only_items.append(x)
    candidate_review = _candidate_review_view(wc5d) if wc5d else {
        "candidate_review_status": "WC5D_MISSING_WARN_ONLY",
        "candidate_review_summary": {"source_status": "WC5D_MISSING_WARN_ONLY", "official_final_squad_written": False, "final_squad_complete": False, "teams_total": 48, "teams_safe": 0, "teams_hold": 48, "api_teams": 0, "api_players": 0, "wikipedia_teams": 0, "wikipedia_players": 0, "official_confirmed": 0, "primary_blocker": "WC5D artifact missing"},
        "candidate_review_counts": {"OFFICIAL_CONFIRMED": 0, "API_CLEAN_CANDIDATE": 0, "API_WIKI_ALIGNED_CANDIDATE": 0, "WIKI_PREFERRED_API_POOL_OVERFULL": 0, "API_INCOMPLETE_NEED_REVIEW": 0, "PROVISIONAL_OVERFULL_NEED_REVIEW": 0},
        "candidate_review_safe_teams": [],
        "candidate_review_hold_teams": [],
        "candidate_review_focus_teams": [],
        "candidate_review_safety_guard": {"candidate_review_only": True, "official_final_squad_written": False, "final_squad_complete": False, "no_betting_recommendations": True, "no_v4_changes": True},
    }
    if not wc5d and "WC5D_MISSING_WARN_ONLY" not in warn_only_items:
        warn_only_items.append("WC5D_MISSING_WARN_ONLY")
    historical_market_view = _historical_market_view(historical_market)
    if not historical_market and "HISTORICAL_MARKET_BASELINE_MISSING_WARN_ONLY" not in warn_only_items:
        warn_only_items.append("HISTORICAL_MARKET_BASELINE_MISSING_WARN_ONLY")
    perception_gap_blueprint_view = _perception_gap_blueprint_view(perception_gap_blueprint)
    if not perception_gap_blueprint and "PERCEPTION_GAP_BLUEPRINT_MISSING_WARN_ONLY" not in warn_only_items:
        warn_only_items.append("PERCEPTION_GAP_BLUEPRINT_MISSING_WARN_ONLY")
    venue_stress_view = _venue_stress_view(venue_stress)
    if not venue_stress and "VENUE_STRESS_MISSING_WARN_ONLY" not in warn_only_items:
        warn_only_items.append("VENUE_STRESS_MISSING_WARN_ONLY")
    match_level_pg_dryrun_view = _match_level_perception_gap_dryrun_view(
        MATCH_LEVEL_PG_DRYRUN_CSV,
        MATCH_LEVEL_PG_DRYRUN_STATUS,
    )
    if match_level_pg_dryrun_view["match_level_perception_gap_dryrun_status"] != "DRY_RUN_READY":
        warn = "WC4D_MATCH_LEVEL_PERCEPTION_GAP_DRYRUN_MISSING_WARN_ONLY"
        if warn not in warn_only_items:
            warn_only_items.append(warn)
    tactical_profile_view = _tactical_profile_view(tactical_profile)
    if tactical_profile_view["tactical_profile_status"] != "TACTICAL_PROFILE_LAYER_READY":
        warn = "WC4G_TACTICAL_PROFILE_MISSING_WARN_ONLY"
        if warn not in warn_only_items:
            warn_only_items.append(warn)
    closing_1x2_view = _closing_1x2_view(closing_1x2)
    if closing_1x2_view["closing_1x2_status"] != "CLOSING_1X2_MARKET_STRUCTURE_READY":
        warn = "WC4H_CLOSING_1X2_MISSING_WARN_ONLY"
        if warn not in warn_only_items:
            warn_only_items.append(warn)

    now = datetime.now(CST)
    payload = {
        "generated_at": now.isoformat(),
        "phase": "V3-WC10",
        "status": "WAR_ROOM_READY_WITH_WARN_ONLY",
        "status_level": "CODE_READY",
        "blocker": "NONE",
        "warn_only_items": warn_only_items,
        "teams_total": teams_total,
        "teams_with_roster": teams_with_roster,
        "players_total": players_total,
        "roster_source": str(ROSTERS),
        "roster_coverage_status": "READY_46_OF_46" if teams_total == 46 and teams_with_roster == 46 else "PARTIAL",
        "supplement_coverage_status": supp_status,
        "caps_goals_minutes_coverage_status": caps_cov or "MISSING",
        "injury_coverage_status": injury_cov or "MISSING",
        "friendly_form_coverage_status": friendly_cov or "MISSING",
        "market_baseline_coverage_status": market_cov or "PARTIAL_BASELINE_ONLY",
        "supplement_coverage_by_category": supp_cov or {},
        "final_squad_status": fs_status,
        "teams_expected_final_squad": int(final_squad.get("teams_expected") or 48) if final_squad else 48,
        "teams_detected_in_baseline": int(final_squad.get("teams_detected_in_baseline") or teams_total) if final_squad else teams_total,
        "players_total_baseline": int(final_squad.get("players_total_baseline") or players_total) if final_squad else players_total,
        "final_squad_files_found_count": len(fs_found),
        "final_squad_coverage_status": fs_coverage_status,
        "final_26_complete_teams_count": fs_complete,
        "final_squad_missing_team_count": fs_missing_count,
        "final_squad_missing_team_list": fs_missing_list[:8],
        "baseline_pool_not_final_26": True,
        "source_authorization_gate_status": source_gate.get("status") if source_gate else "DATA_MISSING",
        "source_authorization_approved_sources_count": int(source_gate.get("approved_sources_count") or 0) if source_gate else 0,
        "source_authorization_intake_files_found": int(source_gate.get("intake_files_found") or 0) if source_gate else 0,
        "source_authorization_unauthorized_files_found": int(source_gate.get("unauthorized_files_found") or 0) if source_gate else 0,
        "source_authorization_authorized_files_found": int(source_gate.get("authorized_files_found") or 0) if source_gate else 0,
        "source_authorization_ready_for_ingestion": int(source_gate.get("final_squad_files_ready_for_ingestion") or 0) if source_gate else 0,
        "wc6_ingestion_dryrun_status": dryrun.get("status") if dryrun else "DATA_MISSING",
        "wc6_ingestion_dryrun_files_parsed": int(dryrun.get("dryrun_files_parsed") or 0) if dryrun else 0,
        "wc6_ingestion_dryrun_official_written": bool(dryrun.get("official_final_squad_written")) if dryrun else False,
        "wc6_ingestion_dryrun_only": bool((dryrun.get("safety_guard") or {}).get("dryrun_only")) if dryrun else True,
        **candidate_review,
        **historical_market_view,
        **perception_gap_blueprint_view,
        **venue_stress_view,
        **match_level_pg_dryrun_view,
        **tactical_profile_view,
        **closing_1x2_view,
        "perception_gap_watchlist": watch_list,
        "perception_gap_watchlist_count": len(watch_list),
        "undervalued_candidates": undervalued,
        "overhyped_risk_candidates": overhyped,
        "high_stability_teams": high_stability,
        "high_spine_change_teams": high_spine,
        "age_risk_teams": age_risk,
        "depth_risk_teams": depth_risk,
        "group_readiness_summary": {
            "status": "PLACEHOLDER_GROUP_LAYER_PENDING",
            "note": "Group-level supplement not ingested yet",
        },
        "opening_match_watch": {
            "status": "WATCH_ONLY_PLACEHOLDER",
            "teams": [],
            "data_coverage": "MISSING_OPENER_SUPPLEMENT",
            "note": "Observation-only placeholder until official opener layer is ingested",
        },
        "T_minus_days": 10,
        "policy_note": "V3 World Cup war room is observation-only and not a betting recommendation output.",
        "safety_guard": {
            "observation_only": True,
            "no_betting_recommendations": True,
            "no_stake": True,
            "no_qq_push": True,
            "no_pending_write": True,
            "no_v4_changes": True,
            "venue_stress_observation_only": True,
            "no_default_rules_change": True,
            "no_ab_thresholds_change": True,
            "no_live_bet_change": True,
            "no_cron_change": True,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    war_path = OUT_DIR / "v3_worldcup_wc10_war_room_20260602.json"
    status_path = STATUS_DIR / "v3_worldcup_wc10_war_room_20260602.json"
    war_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    status_path.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "status": payload["status"],
                "status_level": payload["status_level"],
                "blocker": payload["blocker"],
                "warn_only_items": payload["warn_only_items"],
                "no_scan": True,
                "no_api": True,
                "no_qq_push": True,
                "no_pending_write": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "war_room_json": str(war_path), "status_json": str(status_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
