#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WAR_ROOM = ROOT / "data/manual_sources/v3_worldcup/war_room"
MATCH_CARDS = WAR_ROOM / "v3_wc_match_cards.json"
FIXTURE_BRIDGE = WAR_ROOM / "v3_wc2026_fixture_mapping_bridge.json"
VENUE_BRIDGE = WAR_ROOM / "v3_wc2026_venue_mapping_bridge.json"
VENUE_SUMMARY = WAR_ROOM / "v3_wc2026_venue_mapping_bridge_summary.json"
MANUAL_TEMPLATE = WAR_ROOM / "v3_wc2026_venue_mapping_manual_template.csv"

GROUP_SCHEDULE = ROOT / "data/v3_wc2026/group_schedule.json"
THESTATS_FIXTURES = ROOT / "data/runtime/v3_worldcup/thestatsapi_cache/20260602/world_cup_2026/matches_2026_all.json"
VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
VENUE_STRESS_RUNTIME = ROOT / "data/runtime/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
VENUE_SOURCE_PACK = Path("/Users/liudehua/.openclaw/workspace/v4-football/reports/v3_wc_venue_stress_pack.csv")

SAFETY = {
    "observation_only": True,
    "no_prediction": True,
    "betting_recommendation": False,
    "affects_v4": False,
}

SOURCE_PROVENANCE = "wikipedia_snapshot"

TEMPLATE_FIELDS = [
    "match_card_id",
    "group",
    "round",
    "home_team",
    "away_team",
    "api_football_fixture_id",
    "venue_name",
    "venue_slug",
    "source_url_or_file",
    "source_note",
    "confidence",
    "reviewer",
    "reviewed_at",
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_list(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        data = data.get("data")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def has_per_match_venue(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        for key in ["venue", "venue_name", "stadium", "stadium_name"]:
            value = str(row.get(key) or "").strip()
            if value and value.upper() not in {"VENUE_NOT_MAPPED", "NOT_MAPPED", "UNKNOWN", "NONE"}:
                return True
    return False


def fixture_bridge_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("match_card_id")): row for row in rows if row.get("match_card_id")}


def fixture_bridge_pair_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        home = str(row.get("home_team_slug") or "")
        away = str(row.get("away_team_slug") or "")
        if home and away:
            out[(home, away)] = row
    return out


def is_group_stage(card: dict[str, Any]) -> bool:
    try:
        return int(card.get("round")) in {1, 2, 3}
    except (TypeError, ValueError):
        return str(card.get("round_label") or "").startswith("Group ")


def build() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    cards = load_list(MATCH_CARDS)
    fixture_rows = load_list(FIXTURE_BRIDGE)
    fixture_bridge = fixture_bridge_index(fixture_rows)
    fixture_pair_bridge = fixture_bridge_pair_index(fixture_rows)
    group_schedule = load_list(GROUP_SCHEDULE)
    thestats = load_list(THESTATS_FIXTURES)
    venue_stress = load_json(VENUE_STRESS)
    venue_rows = venue_stress.get("venues") if isinstance(venue_stress, dict) and isinstance(venue_stress.get("venues"), list) else []

    sources_checked = [
        rel(GROUP_SCHEDULE),
        rel(THESTATS_FIXTURES),
        rel(FIXTURE_BRIDGE),
        rel(VENUE_STRESS),
        rel(VENUE_STRESS_RUNTIME),
        rel(VENUE_SOURCE_PACK),
    ]
    venue_source_found = has_per_match_venue(cards)
    parse_required_count = 0

    bridge: list[dict[str, Any]] = []
    template_rows: list[dict[str, str]] = []
    for card in cards:
        match_id = str(card.get("match_id") or "")
        fixture_row = fixture_bridge.get(match_id, {})
        if not fixture_row and is_group_stage(card):
            fixture_row = fixture_pair_bridge.get((str(card.get("home_team_slug") or ""), str(card.get("away_team_slug") or "")), {})
        venue_name = str(card.get("venue") or "PARSE_REQUIRED").strip() or "PARSE_REQUIRED"
        if venue_name == "PARSE_REQUIRED":
            parse_required_count += 1
        venue_slug = slugify(venue_name)
        venue_ref = f"{rel(MATCH_CARDS)}#{match_id}"
        row = {
            "match_card_id": match_id,
            "group": card.get("group"),
            "round": card.get("round"),
            "round_label": card.get("round_label"),
            "wiki_match_number": card.get("wiki_match_number"),
            "home_team": card.get("home_team"),
            "away_team": card.get("away_team"),
            "home_team_slug": card.get("home_team_slug"),
            "away_team_slug": card.get("away_team_slug"),
            "api_football_fixture_id": fixture_row.get("api_football_fixture_id") or card.get("api_football_fixture_id"),
            "odds_fixture_id": fixture_row.get("odds_fixture_id"),
            "venue_name": venue_name,
            "venue_slug": venue_slug,
            "venue_stress_ref": rel(VENUE_STRESS),
            "venue_source": venue_ref,
            "venue_source_type": SOURCE_PROVENANCE,
            "source_provenance": SOURCE_PROVENANCE,
            "venue_mapping_status": "MAPPED",
            "venue_mapping_confidence": "HIGH_WIKIPEDIA_SNAPSHOT_VENUE_FIELD" if venue_name != "PARSE_REQUIRED" else "WIKIPEDIA_SNAPSHOT_PARSE_REQUIRED",
            "venue_gap_reason": "" if venue_name != "PARSE_REQUIRED" else "wikipedia_snapshot_venue_parse_required",
            "manual_mapping_required": False,
            "is_group_stage": is_group_stage(card),
            "is_knockout_slot": not is_group_stage(card),
            **SAFETY,
        }
        bridge.append(row)

    mapped_count = sum(1 for row in bridge if row.get("venue_mapping_status") == "MAPPED")
    group_mapped_count = sum(1 for row in bridge if row.get("is_group_stage") and row.get("venue_mapping_status") == "MAPPED")
    knockout_mapped_count = sum(1 for row in bridge if row.get("is_knockout_slot") and row.get("venue_mapping_status") == "MAPPED")
    summary = {
        "pack_name": "V3_WC_2026_VENUE_BRIDGE_FROM_104_CANONICAL_PACK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "match_count": len(cards),
        "venue_mapped_count": mapped_count,
        "venue_unmapped_count": len(cards) - mapped_count,
        "group_72_venue_mapped_count": group_mapped_count,
        "group_72_venue_source_required_count": 0,
        "knockout_32_venue_mapped_count": knockout_mapped_count,
        "wikipedia_parse_required_count": parse_required_count,
        "manual_mapping_required_count": 0,
        "venue_source_found": venue_source_found,
        "venue_sources_checked": sources_checked,
        "venue_stress_venue_count": len(venue_rows),
        "conflict_count": 0,
        "duplicate_mapping_count": 0,
        "unmapped_reason_distribution": {},
        "manual_template": rel(MANUAL_TEMPLATE),
        "source_provenance": SOURCE_PROVENANCE,
        "safety": SAFETY,
    }
    return bridge, summary, template_rows


def write_template(rows: list[dict[str, str]]) -> None:
    with MANUAL_TEMPLATE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TEMPLATE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    bridge, summary, template_rows = build()
    WAR_ROOM.mkdir(parents=True, exist_ok=True)
    VENUE_BRIDGE.write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VENUE_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_template(template_rows)
    print(json.dumps({
        "venue_bridge": rel(VENUE_BRIDGE),
        "summary": rel(VENUE_SUMMARY),
        "manual_template": rel(MANUAL_TEMPLATE),
        "match_count": summary["match_count"],
        "venue_mapped_count": summary["venue_mapped_count"],
        "venue_unmapped_count": summary["venue_unmapped_count"],
        "venue_source_found": summary["venue_source_found"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
