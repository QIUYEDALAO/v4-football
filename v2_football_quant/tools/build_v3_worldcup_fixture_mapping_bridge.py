#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WAR_ROOM = ROOT / "data/manual_sources/v3_worldcup/war_room"
MATCH_CARDS = WAR_ROOM / "v3_wc_match_cards.json"
BRIDGE = WAR_ROOM / "v3_wc2026_fixture_mapping_bridge.json"
BRIDGE_SUMMARY = WAR_ROOM / "v3_wc2026_fixture_mapping_bridge_summary.json"

GROUP_SCHEDULE = ROOT / "data/v3_wc2026/group_schedule.json"
THESTATS_FIXTURES = ROOT / "data/runtime/v3_worldcup/thestatsapi_cache/20260602/world_cup_2026/matches_2026_all.json"
VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
ODDS_LIVE_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json"

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
    "no_prediction": True,
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


def canonical_team(name: str) -> str:
    return TEAM_ALIASES.get(name, name)


def slugify(text: str) -> str:
    cleaned = (
        canonical_team(text)
        .lower()
        .replace("&", "and")
        .replace("'", "")
        .replace("ç", "c")
        .replace("ô", "o")
        .replace("ü", "u")
        .replace("é", "e")
        .replace("í", "i")
    )
    return "_".join(part for part in "".join(ch if ch.isalnum() else " " for ch in cleaned).split() if part)


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def load_list(path: Path, key: str | None = None) -> list[dict[str, Any]]:
    data = load_json(path)
    if key and isinstance(data, dict):
        data = data.get(key)
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        data = data.get("data")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def schedule_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        home = slugify(str(row.get("home_team") or ""))
        away = slugify(str(row.get("away_team") or ""))
        if home and away:
            out[(home, away)] = row
    return out


def thestats_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        match_id = str(row.get("id") or "")
        if match_id:
            out[match_id] = row
    return out


def venue_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = str(row.get("venue") or "")
        if name:
            out[slugify(name)] = row
    return out


def fixture_gap(schedule_row: dict[str, Any] | None, thestats_row: dict[str, Any] | None) -> str:
    if schedule_row:
        return ""
    if not thestats_row:
        return "match_card_not_found_in_thestats_fixture_cache"
    return "no_exact_home_away_pair_in_group_schedule"


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cards = load_list(MATCH_CARDS)
    schedule_rows = load_list(GROUP_SCHEDULE)
    thestats_rows = load_list(THESTATS_FIXTURES)
    venues_payload = load_json(VENUE_STRESS)
    venues = venues_payload.get("venues") if isinstance(venues_payload, dict) and isinstance(venues_payload.get("venues"), list) else []
    odds_status = load_json(ODDS_LIVE_STATUS)
    coverage = odds_status.get("coverage") if isinstance(odds_status, dict) and isinstance(odds_status.get("coverage"), dict) else {}
    odds_success_ids = {str(item) for item in coverage.get("successful_fixture_ids", [])}

    schedule_by_pair = schedule_index(schedule_rows)
    thestats_by_id = thestats_index(thestats_rows)
    venues_by_slug = venue_index(venues)

    bridge: list[dict[str, Any]] = []
    fixture_ids: list[str] = []
    odds_ids: list[str] = []
    conflicts = 0
    fixture_mapped = 0
    venue_mapped = 0

    for card in cards:
        match_id = str(card.get("match_id") or "")
        home = str(card.get("home_team") or "")
        away = str(card.get("away_team") or "")
        home_slug = str(card.get("home_team_slug") or slugify(home))
        away_slug = str(card.get("away_team_slug") or slugify(away))
        mapping_key = f"{home_slug}__vs__{away_slug}"
        schedule_row = schedule_by_pair.get((home_slug, away_slug))
        thestats_row = thestats_by_id.get(match_id)
        if schedule_row and thestats_row:
            ts_date = str(thestats_row.get("utc_date") or "")[:10]
            sched_date = str(schedule_row.get("date") or "")
            if sched_date and ts_date and sched_date != ts_date:
                conflicts += 1
        fixture_id = str(schedule_row.get("fixture_id")) if schedule_row and schedule_row.get("fixture_id") is not None else None
        if fixture_id:
            fixture_ids.append(fixture_id)
            odds_ids.append(fixture_id)
            fixture_mapped += 1

        venue_name = str((thestats_row or {}).get("venue") or (schedule_row or {}).get("venue") or "")
        venue_row = venues_by_slug.get(slugify(venue_name)) if venue_name else None
        if venue_row:
            venue_mapped += 1
        venue_real_name = str(venue_row.get("venue") or venue_name) if venue_row else "VENUE_NOT_MAPPED"

        bridge.append({
            "match_card_id": match_id,
            "group": card.get("group"),
            "round": card.get("round"),
            "home_team": home,
            "away_team": away,
            "home_team_slug": home_slug,
            "away_team_slug": away_slug,
            "mapping_key": mapping_key,
            "api_football_fixture_id": fixture_id,
            "odds_fixture_id": fixture_id,
            "fixture_source": rel(GROUP_SCHEDULE) if fixture_id else rel(THESTATS_FIXTURES),
            "fixture_mapping_status": "MAPPED" if fixture_id else "UNMAPPED",
            "fixture_mapping_confidence": "HIGH_EXACT_HOME_AWAY_PAIR" if fixture_id else "NONE",
            "venue_name": venue_real_name,
            "venue_slug": slugify(venue_real_name),
            "venue_source": rel(VENUE_STRESS) if venue_row else rel(THESTATS_FIXTURES),
            "venue_mapping_status": "MAPPED" if venue_row else "UNMAPPED",
            "venue_mapping_confidence": "HIGH_EXACT_VENUE_NAME" if venue_row else "NONE",
            "kickoff_time_local": (schedule_row or {}).get("date"),
            "kickoff_time_utc": (thestats_row or {}).get("utc_date") or card.get("kickoff_time_utc"),
            "mapping_gap_reason": [
                reason for reason in [
                    fixture_gap(schedule_row, thestats_row),
                    "" if venue_row else "fixture_sources_do_not_provide_match_venue",
                ] if reason
            ],
            "odds_available_from_snapshot": bool(fixture_id and fixture_id in odds_success_ids),
            **SAFETY,
        })

    duplicate_fixture_ids = len(fixture_ids) - len(set(fixture_ids))
    duplicate_odds_ids = len(odds_ids) - len(set(odds_ids))
    summary = {
        "pack_name": "V3_WC_MATCH_CARD_PACK_PHASE_3_FIXTURE_MAPPING_BRIDGE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "source_match_cards": rel(MATCH_CARDS),
        "mapping_sources_used": [rel(GROUP_SCHEDULE), rel(THESTATS_FIXTURES), rel(VENUE_STRESS), rel(ODDS_LIVE_STATUS)],
        "match_count": len(cards),
        "bridge_count": len(bridge),
        "fixture_id_mapped_count": fixture_mapped,
        "odds_fixture_id_mapped_count": len(odds_ids),
        "venue_mapped_count": venue_mapped,
        "fixture_unmapped_count": len(cards) - fixture_mapped,
        "venue_unmapped_count": len(cards) - venue_mapped,
        "conflict_count": conflicts,
        "duplicate_fixture_id_count": duplicate_fixture_ids,
        "duplicate_odds_fixture_id_count": duplicate_odds_ids,
        "odds_available_fixture_count": sum(1 for row in bridge if row.get("odds_available_from_snapshot") is True),
        "global_gap_summary": {
            "fixture_mapping": "mapped_by_exact_home_away_pair_from_group_schedule",
            "venue_mapping": "fixture_sources_do_not_provide_match_venue",
            "odds_mapping": "odds_fixture_id_uses_api_football_fixture_id_from_group_schedule",
            "odds_availability": "only fixtures present in live snapshot success list are odds_available",
        },
        "safety": SAFETY,
    }
    return bridge, summary


def main() -> int:
    bridge, summary = build()
    WAR_ROOM.mkdir(parents=True, exist_ok=True)
    BRIDGE.write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    BRIDGE_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "bridge": rel(BRIDGE),
        "summary": rel(BRIDGE_SUMMARY),
        "bridge_count": summary["bridge_count"],
        "fixture_id_mapped_count": summary["fixture_id_mapped_count"],
        "odds_fixture_id_mapped_count": summary["odds_fixture_id_mapped_count"],
        "venue_mapped_count": summary["venue_mapped_count"],
        "conflict_count": summary["conflict_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
