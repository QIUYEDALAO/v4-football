#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/manual_sources/v3_worldcup/war_room"
MATCH_CARDS = OUT_DIR / "v3_wc_match_cards.json"
MATCH_SUMMARY = OUT_DIR / "v3_wc_match_card_summary.json"

FIXTURES = ROOT / "data/runtime/v3_worldcup/thestatsapi_cache/20260602/world_cup_2026/matches_2026_all.json"
MASTER_INDEX = OUT_DIR / "v3_wc_war_room_master_index.json"
GAP_RADAR = OUT_DIR / "v3_wc_war_room_gap_radar.json"
FIXTURE_MAPPING_BRIDGE = OUT_DIR / "v3_wc2026_fixture_mapping_bridge.json"
FINAL26_MANIFEST = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_pack_manifest.json"
PROFILE_CARDS = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_team_cards.json"
LINEUP_STATUS = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_lineup_readiness_team_status.json"
VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
TACTICAL_PROFILE = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
WC10_WAR_ROOM = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
ODDS_LIVE_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json"
ODDS_AVAILABILITY_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_availability_monitor_20260604.json"
ODDS_DELTA_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_movement_eligibility_20260604.json"

TEAM_ALIASES = {
    "Bosnia & Herzegovina": "Bosnia And Herzegovina",
    "Cape Verde": "Cabo Verde",
    "Cape Verde Islands": "Cabo Verde",
    "Czech Republic": "Czechia",
    "DR Congo": "Congo DR",
    "Iran": "IR Iran",
    "Ivory Coast": "Côte D'Ivoire",
    "South Korea": "Korea Republic",
    "Côte d'Ivoire": "Côte D'Ivoire",
}

SAFETY = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def slugify(text: str) -> str:
    cleaned = (
        text.lower()
        .replace("&", "and")
        .replace("'", "")
        .replace("ç", "c")
        .replace("ô", "o")
        .replace("ü", "u")
        .replace("é", "e")
        .replace("í", "i")
    )
    return "_".join(part for part in "".join(ch if ch.isalnum() else " " for ch in cleaned).split() if part)


def canonical_team(name: str) -> str:
    return TEAM_ALIASES.get(name, name)


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def load_fixture_rows() -> list[dict[str, Any]]:
    data = load_json(FIXTURES)
    rows = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def index_by_team(rows: Any) -> dict[str, dict[str, Any]]:
    if isinstance(rows, dict) and isinstance(rows.get("teams"), list):
        rows = rows.get("teams")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        team = str(item.get("team") or "")
        if team:
            out[team] = item
            out[slugify(team)] = item
    return out


def tactical_index(payload: Any) -> dict[str, dict[str, Any]]:
    rows = payload.get("profiles") if isinstance(payload, dict) and isinstance(payload.get("profiles"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        team = str(item.get("team") or "")
        if team:
            out[team] = item
            out[slugify(team)] = item
    return out


def bridge_index(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, list):
        return {}
    return {
        str(item.get("match_card_id")): item
        for item in payload
        if isinstance(item, dict) and item.get("match_card_id")
    }


def team_profile_ref(team: str) -> str:
    return f"{rel(PROFILE_CARDS)}#{slugify(team)}"


def lineup_ref(team: str) -> str:
    return f"{rel(LINEUP_STATUS)}#{slugify(team)}"


def data_gaps(base_gaps: dict[str, Any], venue_mapped: bool, odds_available: bool, odds_delta_available: bool) -> list[str]:
    gaps = []
    for key in [
        "missing_starting_xi",
        "missing_official_matchday_lineup",
        "missing_native_opening_odds",
        "missing_native_closing_odds",
        "missing_odds_movement_conclusion",
        "missing_injury_suspension_official_feed",
    ]:
        if base_gaps.get(key) is True:
            gaps.append(key)
    if not venue_mapped:
        gaps.append("match_venue_not_mapped_to_fixture")
    if not odds_available:
        gaps.append("odds_snapshot_not_mapped_to_this_match")
    if not odds_delta_available:
        gaps.append("odds_delta_not_available_for_this_match")
    return sorted(set(gaps))


def venue_binding(venue: dict[str, Any], bridge_row: dict[str, Any] | None = None, venue_name: str | None = None) -> dict[str, Any]:
    bridge_row = bridge_row or {}
    if bridge_row.get("venue_mapping_status") == "UNMAPPED":
        return {
            "venue_name": bridge_row.get("venue_name") or "VENUE_NOT_MAPPED",
            "venue_slug": bridge_row.get("venue_slug") or "venue_not_mapped",
            "venue_stress_status": "VENUE_LAYER_READY_FIXTURE_VENUE_NOT_MAPPED",
            "venue_stress_tags": ["WATCH_ONLY"],
            "venue_stress_ref": rel(VENUE_STRESS),
            "venue_mapping_status": "UNMAPPED",
            "venue_gap_reason": ";".join(bridge_row.get("mapping_gap_reason") or ["fixture_sources_do_not_provide_match_venue"]),
            "fixture_mapping_bridge_ref": f"{rel(FIXTURE_MAPPING_BRIDGE)}#{bridge_row.get('match_card_id')}",
        }
    venues = venue.get("venues") if isinstance(venue.get("venues"), list) else []
    by_name = {
        slugify(str(item.get("venue") or "")): item
        for item in venues
        if isinstance(item, dict) and item.get("venue")
    }
    mapped = by_name.get(slugify(venue_name or "")) if venue_name else None
    if mapped:
        venue_real_name = str(mapped.get("venue") or venue_name)
        return {
            "venue_name": venue_real_name,
            "venue_slug": slugify(venue_real_name),
            "venue_stress_status": str(mapped.get("composite_risk") or "READY"),
            "venue_stress_tags": mapped.get("stress_tags") or ["WATCH_ONLY"],
            "venue_stress_ref": f"{rel(VENUE_STRESS)}#{slugify(venue_real_name)}",
            "venue_mapping_status": "BOUND",
            "venue_gap_reason": "",
            "fixture_mapping_bridge_ref": f"{rel(FIXTURE_MAPPING_BRIDGE)}#{bridge_row.get('match_card_id')}" if bridge_row else None,
        }
    return {
        "venue_name": "VENUE_NOT_MAPPED",
        "venue_slug": "venue_not_mapped",
        "venue_stress_status": "VENUE_LAYER_READY_FIXTURE_VENUE_NOT_MAPPED",
        "venue_stress_tags": ["WATCH_ONLY"],
        "venue_stress_ref": rel(VENUE_STRESS),
        "venue_mapping_status": "NOT_MAPPED",
        "venue_gap_reason": "fixture_source_missing_venue_name",
        "fixture_mapping_bridge_ref": f"{rel(FIXTURE_MAPPING_BRIDGE)}#{bridge_row.get('match_card_id')}" if bridge_row else None,
    }


def odds_binding(
    odds_live: dict[str, Any],
    odds_availability: dict[str, Any],
    odds_delta: dict[str, Any],
    bridge_row: dict[str, Any] | None = None,
    fixture_id: str | None = None,
) -> dict[str, Any]:
    bridge_row = bridge_row or {}
    coverage = odds_live.get("coverage") if isinstance(odds_live.get("coverage"), dict) else {}
    movement = odds_delta.get("movement_eligibility") if isinstance(odds_delta.get("movement_eligibility"), dict) else {}
    successful_ids = {str(item) for item in coverage.get("successful_fixture_ids", [])}
    odds_fixture_id = bridge_row.get("odds_fixture_id") or fixture_id
    mapped = bool(odds_fixture_id)
    available = bool(odds_fixture_id and str(odds_fixture_id) in successful_ids)
    return {
        "odds_fixture_id": str(odds_fixture_id) if odds_fixture_id else None,
        "odds_snapshot_status": "AVAILABLE" if available else ("MAPPED_NO_CURRENT_ODDS" if mapped else "GLOBAL_SNAPSHOT_AVAILABLE_NOT_MATCH_MAPPED"),
        "odds_available": available,
        "bookmaker_count": int(odds_availability.get("bookmaker_count") or coverage.get("bookmaker_count") or 0),
        "market_type_count": int(odds_availability.get("market_type_count") or len(coverage.get("market_coverage") or {})),
        "odds_observation_delta_status": str(movement.get("eligibility_status") or "NOT_AVAILABLE"),
        "changed_odds_count": int(movement.get("changed_odds_count") or 0) if available else 0,
        "odds_gap_reason": "" if available else ("odds_fixture_mapped_but_current_snapshot_empty" if mapped else "match_card_fixture_id_not_mapped_to_api_football_odds_fixture"),
        "no_money_flow_judgment": True,
        "fixture_mapping_bridge_ref": f"{rel(FIXTURE_MAPPING_BRIDGE)}#{bridge_row.get('match_card_id')}" if bridge_row else None,
    }


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixtures = load_fixture_rows()
    master = load_json(MASTER_INDEX)
    gap = load_json(GAP_RADAR)
    final26 = load_json(FINAL26_MANIFEST)
    profiles = index_by_team(load_json(PROFILE_CARDS))
    lineups = index_by_team(load_json(LINEUP_STATUS))
    tactical = tactical_index(load_json(TACTICAL_PROFILE))
    bridge = bridge_index(load_json(FIXTURE_MAPPING_BRIDGE))
    venue = load_json(VENUE_STRESS)
    wc10 = load_json(WC10_WAR_ROOM)
    odds_live = load_json(ODDS_LIVE_STATUS)
    odds_availability = load_json(ODDS_AVAILABILITY_STATUS)
    odds_delta = load_json(ODDS_DELTA_STATUS)

    venue_count = int(venue.get("venue_count") or 0) if isinstance(venue, dict) else 0
    odds_coverage = odds_live.get("coverage") if isinstance(odds_live, dict) and isinstance(odds_live.get("coverage"), dict) else {}
    successful_fixture_count = int(odds_coverage.get("successful_fixture_count") or 0)
    delta = odds_delta.get("movement_eligibility") if isinstance(odds_delta, dict) and isinstance(odds_delta.get("movement_eligibility"), dict) else {}
    delta_status = str(delta.get("eligibility_status") or "NOT_AVAILABLE")
    cards: list[dict[str, Any]] = []
    teams_covered: set[str] = set()
    cards_with_final26 = 0
    cards_with_tactical = 0
    cards_waiting_lineup = 0
    cards_with_venue_binding = 0
    cards_with_venue_stress = 0
    cards_missing_venue_binding = 0
    cards_with_odds_binding = 0
    cards_with_odds_available = 0
    cards_with_odds_delta_observed = 0
    cards_missing_odds_binding = 0

    for idx, row in enumerate(fixtures, start=1):
        home_raw = str((row.get("home_team") or {}).get("name") or "")
        away_raw = str((row.get("away_team") or {}).get("name") or "")
        home = canonical_team(home_raw)
        away = canonical_team(away_raw)
        home_slug = slugify(home)
        away_slug = slugify(away)
        home_profile = profiles.get(home) or profiles.get(home_slug)
        away_profile = profiles.get(away) or profiles.get(away_slug)
        home_lineup = lineups.get(home) or lineups.get(home_slug)
        away_lineup = lineups.get(away) or lineups.get(away_slug)
        home_tactical = tactical.get(home) or tactical.get(home_slug)
        away_tactical = tactical.get(away) or tactical.get(away_slug)
        final26_ready = bool(home_profile and away_profile)
        tactical_ready = bool(home_tactical or away_tactical)
        if final26_ready:
            cards_with_final26 += 1
        if tactical_ready:
            cards_with_tactical += 1
        if (
            (home_lineup or {}).get("matchday_lineup_status") == "WAIT_OFFICIAL_LINEUP"
            and (away_lineup or {}).get("matchday_lineup_status") == "WAIT_OFFICIAL_LINEUP"
        ):
            cards_waiting_lineup += 1
        teams_covered.update([home, away])

        match_id = str(row.get("id") or f"wc2026_match_{idx:03d}")
        group = str(row.get("group_label") or "UNKNOWN")
        bridge_row = bridge.get(match_id, {})
        venue_bound = venue_binding(venue if isinstance(venue, dict) else {}, bridge_row, row.get("venue"))
        odds_bound = odds_binding(
            odds_live if isinstance(odds_live, dict) else {},
            odds_availability if isinstance(odds_availability, dict) else {},
            odds_delta if isinstance(odds_delta, dict) else {},
            bridge_row,
            row.get("fixture_id"),
        )
        if venue_bound["venue_mapping_status"] in {"BOUND", "MAPPED"}:
            cards_with_venue_binding += 1
            cards_with_venue_stress += 1
        else:
            cards_missing_venue_binding += 1
        if odds_bound["odds_fixture_id"]:
            cards_with_odds_binding += 1
        else:
            cards_missing_odds_binding += 1
        if odds_bound["odds_available"]:
            cards_with_odds_available += 1
        if odds_bound["changed_odds_count"] > 0:
            cards_with_odds_delta_observed += 1
        card = {
            "match_id": match_id,
            "group": group,
            "round": row.get("matchday") or "GROUP_STAGE",
            "home_team": home,
            "away_team": away,
            "home_team_slug": home_slug,
            "away_team_slug": away_slug,
            "api_football_fixture_id": bridge_row.get("api_football_fixture_id"),
            "venue": "VENUE_NOT_MAPPED",
            "kickoff_status": str(row.get("status") or "scheduled").upper(),
            "kickoff_time_utc": row.get("utc_date"),
            "venue_binding": venue_bound,
            "venue_stress_summary": {
                "status": venue_bound["venue_stress_status"],
                "source": rel(VENUE_STRESS),
                "venue_count": venue_count,
                "stress_tags": venue_bound["venue_stress_tags"],
                "observation_note": venue_bound["venue_gap_reason"] or "venue stress layer bound to fixture",
            },
            "home_final_26_profile_ref": team_profile_ref(home),
            "away_final_26_profile_ref": team_profile_ref(away),
            "home_lineup_status": (home_lineup or {}).get("matchday_lineup_status") or "WAIT_OFFICIAL_LINEUP",
            "away_lineup_status": (away_lineup or {}).get("matchday_lineup_status") or "WAIT_OFFICIAL_LINEUP",
            "starting_xi_status": "NOT_AVAILABLE",
            "predicted_xi_generated": False,
            "tactical_profile_status": "HISTORICAL_OBSERVATION_ONLY" if tactical_ready else "FORMATION_DATA_INSUFFICIENT",
            "historical_formation_observation": {
                "home": {
                    "common_formation": (home_tactical or {}).get("common_formation") or "NO_DATA",
                    "alternative_formations": (home_tactical or {}).get("alternative_formations") or [],
                    "observation_confidence": (home_tactical or {}).get("observation_confidence") or "LOW",
                },
                "away": {
                    "common_formation": (away_tactical or {}).get("common_formation") or "NO_DATA",
                    "alternative_formations": (away_tactical or {}).get("alternative_formations") or [],
                    "observation_confidence": (away_tactical or {}).get("observation_confidence") or "LOW",
                },
            },
            "odds_snapshot_status": {
                "status": odds_bound["odds_snapshot_status"] if successful_fixture_count else "CURRENT_MARKET_DATA_MISSING",
                "successful_fixture_count": successful_fixture_count,
                "source": rel(ODDS_LIVE_STATUS),
                "has_native_opening": False,
                "has_native_closing": False,
            },
            "odds_binding": odds_bound,
            "odds_observation_delta_status": {
                "status": odds_bound["odds_observation_delta_status"] or delta_status,
                "delta_label": delta.get("delta_label") or "odds_observation_delta",
                "changed_odds_count": odds_bound["changed_odds_count"],
                "source": rel(ODDS_DELTA_STATUS),
                "no_money_flow_judgment": True,
            },
            "data_gaps": data_gaps(
                gap if isinstance(gap, dict) else {},
                venue_bound["venue_mapping_status"] == "BOUND",
                odds_bound["odds_available"],
                odds_bound["changed_odds_count"] > 0,
            ),
            **SAFETY,
        }
        cards.append(card)

    summary = {
        "pack_name": "V3_WC_MATCH_CARD_PACK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "source_fixtures": rel(FIXTURES),
        "source_master_index": rel(MASTER_INDEX),
        "source_gap_radar": rel(GAP_RADAR),
        "source_wc10_war_room": rel(WC10_WAR_ROOM),
        "source_fixture_mapping_bridge": rel(FIXTURE_MAPPING_BRIDGE),
        "match_count": len(cards),
        "teams_covered": len(teams_covered),
        "team_names_covered": sorted(teams_covered),
        "cards_with_final_26": cards_with_final26,
        "cards_with_venue_binding": cards_with_venue_binding,
        "cards_with_venue_stress": cards_with_venue_stress,
        "cards_with_tactical_profile": cards_with_tactical,
        "cards_waiting_lineup": cards_waiting_lineup,
        "cards_with_odds_binding": cards_with_odds_binding,
        "cards_with_odds_available": cards_with_odds_available,
        "cards_with_odds_delta": cards_with_odds_delta_observed,
        "cards_with_odds_delta_observed": cards_with_odds_delta_observed,
        "cards_missing_venue_binding": cards_missing_venue_binding,
        "cards_missing_odds_binding": cards_missing_odds_binding,
        "global_data_gaps": data_gaps(gap if isinstance(gap, dict) else {}, False, False, False),
        "global_gap_summary": {
            "fixture_mapping": "mapped_by_fixture_mapping_bridge" if bridge else "fixture_mapping_bridge_missing",
            "venue_binding": "fixture_sources_do_not_provide_match_venue",
            "odds_binding": "mapped_by_fixture_mapping_bridge",
            "official_lineup": "WAIT_OFFICIAL_LINEUP",
            "native_opening_closing": "not_available_from_current_snapshot",
            "odds_observation_delta": "global_status_only_not_per_match_bound",
        },
        "final_26_total_players": ((final26.get("counts") or {}).get("total_players") if isinstance(final26, dict) else None),
        "wc10_status": wc10.get("status") if isinstance(wc10, dict) else "UNKNOWN",
        "master_index_module_count": master.get("module_count") if isinstance(master, dict) else None,
        "safety": SAFETY,
    }
    return cards, summary


def main() -> int:
    cards, summary = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MATCH_CARDS.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MATCH_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "match_cards": rel(MATCH_CARDS),
        "match_card_summary": rel(MATCH_SUMMARY),
        "match_count": summary["match_count"],
        "teams_covered": summary["teams_covered"],
        "cards_with_final_26": summary["cards_with_final_26"],
        "cards_waiting_lineup": summary["cards_waiting_lineup"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
