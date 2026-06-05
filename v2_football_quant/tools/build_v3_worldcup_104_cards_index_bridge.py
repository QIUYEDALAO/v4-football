#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/manual_sources/v3_worldcup/war_room"

GROUP_CARDS = OUT_DIR / "v3_wc_match_cards.json"
GROUP_SUMMARY = OUT_DIR / "v3_wc_match_card_summary.json"
FIXTURE_MAPPING_BRIDGE = OUT_DIR / "v3_wc2026_fixture_mapping_bridge.json"
VENUE_MAPPING_BRIDGE = OUT_DIR / "v3_wc2026_venue_mapping_bridge.json"
SCOPE_DOC = ROOT / "docs/V3_WC_MATCH_CARD_SCOPE_CLARIFICATION_20260605.md"
GROUP_SCHEDULE = ROOT / "data/v3_wc2026/group_schedule.json"

SCHEDULE_INDEX_104 = OUT_DIR / "v3_wc2026_schedule_index_104.json"
CARDS_INDEX_BRIDGE_104 = OUT_DIR / "v3_wc2026_104_cards_index_bridge.json"
CARDS_INDEX_SUMMARY_104 = OUT_DIR / "v3_wc2026_104_cards_index_bridge_summary.json"

GROUP_STAGE_COUNT = 72
KNOCKOUT_SLOT_COUNT = 32
TOTAL_EXPECTED_COUNT = 104

SAFETY = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}

KNOCKOUT_ROUNDS = [
    ("ROUND_OF_32", 16),
    ("ROUND_OF_16", 8),
    ("QUARTER_FINAL", 4),
    ("SEMI_FINAL", 2),
    ("THIRD_PLACE", 1),
    ("FINAL", 1),
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [] if path == GROUP_CARDS else {}


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


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def is_group_stage_source_card(card: dict[str, Any]) -> bool:
    round_value = card.get("round")
    try:
        return int(round_value) in {1, 2, 3}
    except (TypeError, ValueError):
        return str(round_value or "").upper() == "GROUP_STAGE"


def fixture_pair_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        home = str(row.get("home_team_slug") or "")
        away = str(row.get("away_team_slug") or "")
        if home and away:
            out[(home, away)] = row
    return out


def bridge_by_match_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("match_card_id")): row for row in rows if row.get("match_card_id")}


def _venue_fields(card: dict[str, Any], venue_row: dict[str, Any]) -> dict[str, Any]:
    venue_name = venue_row.get("venue_name") or card.get("venue")
    venue_status = venue_row.get("venue_mapping_status") or ("MAPPED" if venue_name else "VENUE_SOURCE_REQUIRED")
    return {
        "venue_name": venue_name,
        "venue_slug": venue_row.get("venue_slug"),
        "venue_mapping_status": venue_status,
        "venue_gap_reason": venue_row.get("venue_gap_reason") or "",
        "venue_source": venue_row.get("venue_source") or f"{rel(GROUP_CARDS)}#{card.get('match_id')}",
        "venue_source_type": venue_row.get("venue_source_type") or "wikipedia_snapshot",
        "source_provenance": venue_row.get("source_provenance") or "wikipedia_snapshot",
        "venue_mapping_confidence": venue_row.get("venue_mapping_confidence"),
    }


def group_stage_rows(cards: list[dict[str, Any]], fixture_rows: list[dict[str, Any]], venue_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    group_cards = [card for card in cards if is_group_stage_source_card(card)]
    venues_by_match = bridge_by_match_id(venue_rows)
    for index, fixture_row in enumerate(fixture_rows, start=1):
        card = group_cards[index - 1] if index - 1 < len(group_cards) else {}
        match_id = str(fixture_row.get("match_card_id") or fixture_row.get("fixture_id") or f"group_stage_{index:03d}")
        wiki_match_id = str(card.get("match_id") or f"wc_{index:03d}")
        venue = _venue_fields(card, venues_by_match.get(wiki_match_id, {}))
        fixture_id = fixture_row.get("api_football_fixture_id") or fixture_row.get("fixture_id")
        source_ref_path = FIXTURE_MAPPING_BRIDGE if fixture_row.get("match_card_id") else GROUP_SCHEDULE
        rows.append({
            "canonical_card_id": f"wc2026_104_{index:03d}",
            "card_scope": "FULL_TOURNAMENT_CANONICAL",
            "card_kind": "GROUP_STAGE_MATCH",
            "source_view": "GROUP_STAGE_VIEW_72",
            "source_card_ref": f"{rel(source_ref_path)}#{match_id}",
            "match_card_id": match_id,
            "group_stage_view_ref": f"{rel(GROUP_CARDS)}#{wiki_match_id}",
            "round": "GROUP_STAGE",
            "round_order": 1,
            "slot_number": index,
            "group": card.get("group") or fixture_row.get("group"),
            "home_team": fixture_row.get("home_team"),
            "away_team": fixture_row.get("away_team"),
            "home_team_slug": fixture_row.get("home_team_slug") or slugify(str(fixture_row.get("home_team") or "")),
            "away_team_slug": fixture_row.get("away_team_slug") or slugify(str(fixture_row.get("away_team") or "")),
            "api_football_fixture_id": str(fixture_id) if fixture_id is not None else None,
            "odds_fixture_id": str(fixture_id) if fixture_id is not None else None,
            "venue_wikipedia_match_id": wiki_match_id,
            **venue,
            "schedule_source_status": "LOCAL_GROUP_STAGE_SOURCE",
            "team_source_status": "KNOWN_FROM_GROUP_STAGE_SOURCE",
            "knockout_team_generated": False,
            "venue_generated": True,
            **SAFETY,
        })
    return rows


def knockout_rows(cards: list[dict[str, Any]], start_index: int, venue_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start_index
    venues_by_match = bridge_by_match_id(venue_rows)
    knockout_cards = [card for card in cards if not is_group_stage_source_card(card)]
    for card in knockout_cards:
        match_id = str(card.get("match_id") or f"knockout_{cursor:03d}")
        venue = _venue_fields(card, venues_by_match.get(match_id, {}))
        rows.append({
            "canonical_card_id": f"wc2026_104_{cursor:03d}",
            "card_scope": "FULL_TOURNAMENT_CANONICAL",
            "card_kind": "KNOCKOUT_SLOT",
            "source_view": "STRUCTURAL_TOURNAMENT_SLOT",
            "source_card_ref": f"{rel(GROUP_CARDS)}#{match_id}",
            "match_card_id": match_id,
            "group_stage_view_ref": None,
            "round": card.get("round_label") or "KNOCKOUT_SLOT",
            "round_order": card.get("round"),
            "slot_number": card.get("wiki_match_number"),
            "group": None,
            "home_team": None,
            "away_team": None,
            "home_team_slug": None,
            "away_team_slug": None,
            "api_football_fixture_id": None,
            "odds_fixture_id": None,
            **venue,
            "schedule_source_status": "STRUCTURAL_SLOT_ONLY_WAIT_OFFICIAL_FIXTURE",
            "team_source_status": "WAIT_QUALIFICATION_NO_TEAM_GENERATED",
            "knockout_team_generated": False,
            "venue_generated": True,
            **SAFETY,
        })
        cursor += 1
    return rows


def build() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    cards_obj = load_json(GROUP_CARDS)
    group_cards = cards_obj if isinstance(cards_obj, list) else []
    fixture_bridge_obj = load_json(FIXTURE_MAPPING_BRIDGE)
    fixture_bridge_cards = fixture_bridge_obj if isinstance(fixture_bridge_obj, list) else []
    group_schedule_obj = load_json(GROUP_SCHEDULE)
    group_schedule_rows = group_schedule_obj if isinstance(group_schedule_obj, list) else []
    venue_bridge_obj = load_json(VENUE_MAPPING_BRIDGE)
    venue_bridge_cards = venue_bridge_obj if isinstance(venue_bridge_obj, list) else []
    group_stage_source_cards = [card for card in group_cards if isinstance(card, dict) and is_group_stage_source_card(card)]
    group_summary = load_json(GROUP_SUMMARY)

    mapped_fixture_rows = [row for row in fixture_bridge_cards if row.get("api_football_fixture_id") and row.get("odds_fixture_id")]
    fixture_source_rows = mapped_fixture_rows[:GROUP_STAGE_COUNT] if len(mapped_fixture_rows) >= GROUP_STAGE_COUNT else group_schedule_rows[:GROUP_STAGE_COUNT]
    rows = group_stage_rows(group_cards, fixture_source_rows, venue_bridge_cards)
    rows.extend(knockout_rows(group_cards, len(rows) + 1, venue_bridge_cards))

    schedule_index = {
        "pack_name": "V3_WC_2026_104_CARDS_INDEX_BRIDGE_PACK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "canonical_source": rel(CARDS_INDEX_BRIDGE_104),
        "canonical_scope": "FULL_TOURNAMENT_104_INDEX",
        "group_stage_view": rel(GROUP_CARDS),
        "group_stage_view_scope": "GROUP_STAGE_ONLY_72",
        "total_expected_match_count": TOTAL_EXPECTED_COUNT,
        "group_stage_match_count": GROUP_STAGE_COUNT,
        "knockout_slot_count": KNOCKOUT_SLOT_COUNT,
        "full_tournament_canonical_source": True,
        "full_tournament_match_data_complete": False,
        "dashboard_index_read_policy": {
            "canonical_reader": rel(CARDS_INDEX_BRIDGE_104),
            "group_stage_view_reader": rel(GROUP_CARDS),
            "do_not_merge_canonical_and_group_view": True,
            "group_view_is_subset_of_canonical": True,
            "duplicate_read_guard": "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE",
        },
        "sources": {
            "group_cards": rel(GROUP_CARDS),
            "group_summary": rel(GROUP_SUMMARY),
            "fixture_mapping_bridge": rel(FIXTURE_MAPPING_BRIDGE),
            "group_schedule": rel(GROUP_SCHEDULE),
            "venue_mapping_bridge": rel(VENUE_MAPPING_BRIDGE),
            "group_stage_source": rel(GROUP_CARDS),
            "group_stage_source_filter": "round in [1, 2, 3]",
            "scope_doc": rel(SCOPE_DOC),
        },
        "safety": SAFETY,
    }

    summary = {
        "pack_name": "V3_WC_2026_104_CARDS_INDEX_BRIDGE_PACK",
        "generated_at": schedule_index["generated_at"],
        "current_head": schedule_index["current_head"],
        "canonical_source": rel(CARDS_INDEX_BRIDGE_104),
        "schedule_index": rel(SCHEDULE_INDEX_104),
        "group_stage_view": rel(GROUP_CARDS),
        "total_expected_match_count": TOTAL_EXPECTED_COUNT,
        "canonical_card_count": len(rows),
        "group_stage_match_count": sum(1 for item in rows if item.get("card_kind") == "GROUP_STAGE_MATCH"),
        "knockout_slot_count": sum(1 for item in rows if item.get("card_kind") == "KNOCKOUT_SLOT"),
        "group_stage_source_match_count": len(group_stage_source_cards),
        "legacy_match_card_file_count": len(group_cards),
        "knockout_team_generated_count": sum(1 for item in rows if item.get("knockout_team_generated") is True),
        "venue_generated_count": sum(1 for item in rows if item.get("venue_generated") is True),
        "venue_mapped_count": sum(1 for item in rows if item.get("venue_mapping_status") == "MAPPED"),
        "source_provenance": "wikipedia_snapshot",
        "full_tournament_canonical_source": True,
        "group_stage_view_preserved": True,
        "double_read_guard": schedule_index["dashboard_index_read_policy"],
        "safety": SAFETY,
    }
    return schedule_index, rows, summary


def main() -> int:
    schedule_index, rows, summary = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULE_INDEX_104.write_text(json.dumps(schedule_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CARDS_INDEX_BRIDGE_104.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CARDS_INDEX_SUMMARY_104.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "schedule_index": rel(SCHEDULE_INDEX_104),
        "canonical_source": rel(CARDS_INDEX_BRIDGE_104),
        "summary": rel(CARDS_INDEX_SUMMARY_104),
        "canonical_card_count": summary["canonical_card_count"],
        "group_stage_match_count": summary["group_stage_match_count"],
        "knockout_slot_count": summary["knockout_slot_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
