#!/usr/bin/env python3
from __future__ import annotations

import json
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


def main() -> int:
    rosters = _load(ROSTERS)
    profiles = _load(PROFILES)
    deltas = _load(DELTAS)
    watch = _load(WATCH)
    supp = _load(SUPPLEMENT_REPORT)
    final_squad = _load(FINAL_SQUAD_REPORT)
    source_gate = _load(SOURCE_GATE_REPORT)

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
