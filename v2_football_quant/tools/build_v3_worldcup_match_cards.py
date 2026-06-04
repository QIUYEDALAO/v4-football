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
FINAL26_MANIFEST = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_pack_manifest.json"
PROFILE_CARDS = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_squad_profile_team_cards.json"
LINEUP_STATUS = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_lineup_readiness_team_status.json"
VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
TACTICAL_PROFILE = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
WC10_WAR_ROOM = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
ODDS_LIVE_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json"
ODDS_DELTA_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_movement_eligibility_20260604.json"

TEAM_ALIASES = {
    "Bosnia & Herzegovina": "Bosnia And Herzegovina",
    "Cape Verde": "Cabo Verde",
    "DR Congo": "Congo DR",
    "Iran": "IR Iran",
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


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixtures = load_fixture_rows()
    master = load_json(MASTER_INDEX)
    gap = load_json(GAP_RADAR)
    final26 = load_json(FINAL26_MANIFEST)
    profiles = index_by_team(load_json(PROFILE_CARDS))
    lineups = index_by_team(load_json(LINEUP_STATUS))
    tactical = tactical_index(load_json(TACTICAL_PROFILE))
    venue = load_json(VENUE_STRESS)
    wc10 = load_json(WC10_WAR_ROOM)
    odds_live = load_json(ODDS_LIVE_STATUS)
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
        card = {
            "match_id": match_id,
            "group": group,
            "round": row.get("matchday") or "GROUP_STAGE",
            "home_team": home,
            "away_team": away,
            "home_team_slug": home_slug,
            "away_team_slug": away_slug,
            "venue": "VENUE_NOT_MAPPED",
            "kickoff_status": str(row.get("status") or "scheduled").upper(),
            "kickoff_time_utc": row.get("utc_date"),
            "venue_stress_summary": {
                "status": "VENUE_LAYER_READY_FIXTURE_VENUE_NOT_MAPPED",
                "source": rel(VENUE_STRESS),
                "venue_count": venue_count,
                "stress_tags": ["WATCH_ONLY"],
                "observation_note": "venue stress layer ready; fixture venue mapping not present in current match source",
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
                "status": "GLOBAL_SNAPSHOT_AVAILABLE_NOT_MATCH_MAPPED" if successful_fixture_count else "CURRENT_MARKET_DATA_MISSING",
                "successful_fixture_count": successful_fixture_count,
                "source": rel(ODDS_LIVE_STATUS),
                "has_native_opening": False,
                "has_native_closing": False,
            },
            "odds_observation_delta_status": {
                "status": delta_status,
                "delta_label": delta.get("delta_label") or "odds_observation_delta",
                "changed_odds_count": int(delta.get("changed_odds_count") or 0),
                "source": rel(ODDS_DELTA_STATUS),
                "no_money_flow_judgment": True,
            },
            "data_gaps": data_gaps(gap if isinstance(gap, dict) else {}, False, False, False),
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
        "match_count": len(cards),
        "teams_covered": len(teams_covered),
        "team_names_covered": sorted(teams_covered),
        "cards_with_final_26": cards_with_final26,
        "cards_with_venue_stress": 0,
        "cards_with_tactical_profile": cards_with_tactical,
        "cards_waiting_lineup": cards_waiting_lineup,
        "cards_with_odds_available": 0,
        "cards_with_odds_delta": 0,
        "global_data_gaps": data_gaps(gap if isinstance(gap, dict) else {}, False, False, False),
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
