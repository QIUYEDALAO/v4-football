#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/manual_sources/v3_worldcup/war_room"

SCHEDULE_INDEX_104 = OUT_DIR / "v3_wc2026_schedule_index_104.json"
CANONICAL_104 = OUT_DIR / "v3_wc2026_104_cards_index_bridge.json"
CANONICAL_104_SUMMARY = OUT_DIR / "v3_wc2026_104_cards_index_bridge_summary.json"
GROUP_VIEW_72 = OUT_DIR / "v3_wc_match_cards.json"
GROUP_VIEW_72_SUMMARY = OUT_DIR / "v3_wc_match_card_summary.json"
MASTER_INDEX = OUT_DIR / "v3_wc_war_room_master_index.json"
DASHBOARD_READ_MODEL = OUT_DIR / "v3_wc2026_dashboard_104_read_model.json"
COVERAGE_GAP_RADAR = OUT_DIR / "v3_wc2026_104_coverage_gap_radar.json"
COVERAGE_GAP_RADAR_SUMMARY = OUT_DIR / "v3_wc2026_104_coverage_gap_radar_summary.json"

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
        return [] if path == CANONICAL_104 or path == GROUP_VIEW_72 else {}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def build() -> dict[str, Any]:
    schedule_index = load_json(SCHEDULE_INDEX_104)
    canonical_rows = load_json(CANONICAL_104)
    canonical_summary = load_json(CANONICAL_104_SUMMARY)
    group_rows = load_json(GROUP_VIEW_72)
    group_summary = load_json(GROUP_VIEW_72_SUMMARY)
    master_index = load_json(MASTER_INDEX)
    coverage_summary = load_json(COVERAGE_GAP_RADAR_SUMMARY)

    rows = canonical_rows if isinstance(canonical_rows, list) else []
    group_cards = group_rows if isinstance(group_rows, list) else []
    group_stage_rows = [item for item in rows if isinstance(item, dict) and item.get("card_kind") == "GROUP_STAGE_MATCH"]
    knockout_rows = [item for item in rows if isinstance(item, dict) and item.get("card_kind") == "KNOCKOUT_SLOT"]

    read_policy = schedule_index.get("dashboard_index_read_policy") if isinstance(schedule_index, dict) and isinstance(schedule_index.get("dashboard_index_read_policy"), dict) else {}
    knockout_rounds: dict[str, int] = {}
    for item in knockout_rows:
        round_name = str(item.get("round") or "UNKNOWN")
        knockout_rounds[round_name] = knockout_rounds.get(round_name, 0) + 1

    return {
        "pack_name": "V3_WC_2026_DASHBOARD_104_READ_MODEL_PACK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "dashboard_read_model": "V3_WC_2026_DASHBOARD_104_READ_MODEL",
        "canonical_source": rel(CANONICAL_104),
        "canonical_schedule_index": rel(SCHEDULE_INDEX_104),
        "canonical_scope": "FULL_TOURNAMENT_104_INDEX",
        "canonical_card_count": len(rows),
        "group_stage_match_count": len(group_stage_rows),
        "knockout_slot_count": len(knockout_rows),
        "full_tournament_match_data_complete": False,
        "group_stage_view": {
            "source": rel(CANONICAL_104),
            "source_filter": "card_kind=GROUP_STAGE_MATCH",
            "legacy_match_cards_source": rel(GROUP_VIEW_72),
            "summary": rel(GROUP_VIEW_72_SUMMARY),
            "scope": "GROUP_STAGE_ONLY_72",
            "match_count": len(group_stage_rows),
            "is_subset_of_canonical": True,
            "do_not_treat_as_complete_source": True,
        },
        "knockout_slots": {
            "count": len(knockout_rows),
            "policy": "STRUCTURAL_ONLY_NO_TEAM_GENERATED",
            "round_counts": knockout_rounds,
            "display_mode": "STRUCTURAL_SLOT_PLACEHOLDER",
            "team_fields_empty": all(not item.get("home_team") and not item.get("away_team") for item in knockout_rows),
            "fixture_fields_empty": all(not item.get("api_football_fixture_id") and not item.get("odds_fixture_id") for item in knockout_rows),
            "venue_fields_not_generated": all(item.get("venue_generated") is False for item in knockout_rows),
        },
        "read_policy": {
            "dashboard_primary_reader": read_policy.get("canonical_reader") or rel(CANONICAL_104),
            "group_stage_view_reader": read_policy.get("group_stage_view_reader") or rel(GROUP_VIEW_72),
            "do_not_merge_canonical_and_group_view": True,
            "group_view_is_subset_of_canonical": True,
            "duplicate_read_guard": "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE",
        },
        "source_summaries": {
            "canonical_summary": rel(CANONICAL_104_SUMMARY),
            "canonical_summary_card_count": canonical_summary.get("canonical_card_count") if isinstance(canonical_summary, dict) else None,
            "group_summary_match_count": group_summary.get("match_count") if isinstance(group_summary, dict) else None,
            "war_room_master_index": rel(MASTER_INDEX),
            "war_room_module_count": master_index.get("module_count") if isinstance(master_index, dict) else None,
            "coverage_gap_radar": rel(COVERAGE_GAP_RADAR),
            "coverage_gap_summary": rel(COVERAGE_GAP_RADAR_SUMMARY),
        },
        "coverage_gap_summary": {
            "source": rel(COVERAGE_GAP_RADAR_SUMMARY),
            "coverage_104": coverage_summary.get("coverage_104") if isinstance(coverage_summary, dict) else {},
            "group_72": coverage_summary.get("group_72") if isinstance(coverage_summary, dict) else {},
            "knockout_32": coverage_summary.get("knockout_32") if isinstance(coverage_summary, dict) else {},
            "gaps": coverage_summary.get("gaps") if isinstance(coverage_summary, dict) else {},
        },
        "safety": SAFETY,
    }


def main() -> int:
    payload = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_READ_MODEL.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dashboard_read_model": rel(DASHBOARD_READ_MODEL),
        "canonical_source": payload["canonical_source"],
        "canonical_card_count": payload["canonical_card_count"],
        "group_stage_match_count": payload["group_stage_match_count"],
        "knockout_slot_count": payload["knockout_slot_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
