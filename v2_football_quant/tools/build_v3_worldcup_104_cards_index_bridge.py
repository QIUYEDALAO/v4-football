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
SCOPE_DOC = ROOT / "docs/V3_WC_MATCH_CARD_SCOPE_CLARIFICATION_20260605.md"

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


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def is_group_stage_source_card(card: dict[str, Any]) -> bool:
    round_value = card.get("round")
    try:
        return int(round_value) in {1, 2, 3}
    except (TypeError, ValueError):
        return str(round_value or "").upper() == "GROUP_STAGE"


def group_stage_rows(cards: list[dict[str, Any]], source_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    group_cards = [card for card in cards if is_group_stage_source_card(card)]
    for index, card in enumerate(group_cards, start=1):
        match_id = str(card.get("match_card_id") or card.get("match_id") or f"group_stage_{index:03d}")
        venue_gap = card.get("venue_gap_reason")
        if not venue_gap and card.get("mapping_gap_reason"):
            raw_reasons = card.get("mapping_gap_reason")
            if isinstance(raw_reasons, list):
                venue_gap = "VENUE_SOURCE_REQUIRED: " + " / ".join(str(item) for item in raw_reasons)
            else:
                venue_gap = f"VENUE_SOURCE_REQUIRED: {raw_reasons}"
        rows.append({
            "canonical_card_id": f"wc2026_104_{index:03d}",
            "card_scope": "FULL_TOURNAMENT_CANONICAL",
            "card_kind": "GROUP_STAGE_MATCH",
            "source_view": "GROUP_STAGE_VIEW_72",
            "source_card_ref": f"{rel(source_path)}#{match_id}",
            "match_card_id": match_id,
            "group_stage_view_ref": f"{rel(GROUP_CARDS)}#{match_id}",
            "round": "GROUP_STAGE",
            "round_order": 1,
            "slot_number": index,
            "group": card.get("group"),
            "home_team": card.get("home_team"),
            "away_team": card.get("away_team"),
            "home_team_slug": card.get("home_team_slug"),
            "away_team_slug": card.get("away_team_slug"),
            "api_football_fixture_id": card.get("api_football_fixture_id"),
            "odds_fixture_id": card.get("odds_fixture_id") or (card.get("odds_binding") or {}).get("odds_fixture_id"),
            "venue_mapping_status": card.get("venue_mapping_status") or (card.get("venue_binding") or {}).get("venue_mapping_status"),
            "venue_gap_reason": venue_gap or (card.get("venue_binding") or {}).get("venue_gap_reason"),
            "schedule_source_status": "LOCAL_GROUP_STAGE_SOURCE",
            "team_source_status": "KNOWN_FROM_GROUP_STAGE_SOURCE",
            "knockout_team_generated": False,
            "venue_generated": False,
            **SAFETY,
        })
    return rows


def knockout_rows(start_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start_index
    for round_order, (round_name, count) in enumerate(KNOCKOUT_ROUNDS, start=2):
        for slot in range(1, count + 1):
            rows.append({
                "canonical_card_id": f"wc2026_104_{cursor:03d}",
                "card_scope": "FULL_TOURNAMENT_CANONICAL",
                "card_kind": "KNOCKOUT_SLOT",
                "source_view": "STRUCTURAL_TOURNAMENT_SLOT",
                "source_card_ref": None,
                "match_card_id": f"wc2026_{round_name.lower()}_{slot:02d}",
                "group_stage_view_ref": None,
                "round": round_name,
                "round_order": round_order,
                "slot_number": slot,
                "group": None,
                "home_team": None,
                "away_team": None,
                "home_team_slug": None,
                "away_team_slug": None,
                "api_football_fixture_id": None,
                "odds_fixture_id": None,
                "venue_mapping_status": "VENUE_SOURCE_REQUIRED",
                "venue_gap_reason": "KNOCKOUT_SLOT_WAITING_OFFICIAL_FIXTURE_SOURCE",
                "schedule_source_status": "STRUCTURAL_SLOT_ONLY_WAIT_OFFICIAL_FIXTURE",
                "team_source_status": "WAIT_QUALIFICATION_NO_TEAM_GENERATED",
                "knockout_team_generated": False,
                "venue_generated": False,
                **SAFETY,
            })
            cursor += 1
    return rows


def build() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    cards_obj = load_json(GROUP_CARDS)
    group_cards = cards_obj if isinstance(cards_obj, list) else []
    fixture_bridge_obj = load_json(FIXTURE_MAPPING_BRIDGE)
    fixture_bridge_cards = fixture_bridge_obj if isinstance(fixture_bridge_obj, list) else []
    source_cards = fixture_bridge_cards or group_cards
    source_path = FIXTURE_MAPPING_BRIDGE if fixture_bridge_cards else GROUP_CARDS
    group_stage_source_cards = [card for card in source_cards if isinstance(card, dict) and is_group_stage_source_card(card)]
    group_summary = load_json(GROUP_SUMMARY)

    rows = group_stage_rows(source_cards, source_path)
    rows.extend(knockout_rows(len(rows) + 1))

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
            "group_stage_source": rel(source_path),
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
