#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/manual_sources/v3_worldcup/war_room"
MASTER_INDEX = OUT_DIR / "v3_wc_war_room_master_index.json"
GAP_RADAR = OUT_DIR / "v3_wc_war_room_gap_radar.json"

FINAL26_BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
FINAL26_MANIFEST = FINAL26_BASE / "v3_wc2026_final_26_pack_manifest.json"
FINAL26_PROFILE = FINAL26_BASE / "v3_wc2026_final_26_squad_profile_observation.json"
LINEUP_READINESS = FINAL26_BASE / "v3_wc2026_lineup_readiness_team_status.json"

VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
TACTICAL_PROFILE = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
CLOSING_1X2 = ROOT / "data/v3_worldcup/closing_1x2_market_structure/v3_worldcup_closing_1x2_market_structure_20260604.json"
WC10_WAR_ROOM = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
MATCH_CARD_104_INDEX = OUT_DIR / "v3_wc2026_104_cards_index_bridge.json"
MATCH_CARD_104_SUMMARY = OUT_DIR / "v3_wc2026_104_cards_index_bridge_summary.json"
MATCH_CARD_72_VIEW = OUT_DIR / "v3_wc_match_cards.json"
DASHBOARD_104_READ_MODEL = OUT_DIR / "v3_wc2026_dashboard_104_read_model.json"
COVERAGE_GAP_RADAR = OUT_DIR / "v3_wc2026_104_coverage_gap_radar.json"
COVERAGE_GAP_RADAR_SUMMARY = OUT_DIR / "v3_wc2026_104_coverage_gap_radar_summary.json"

PERCEPTION_DRYRUN_CSV = ROOT / "data/runtime/v3_worldcup/perception_gap_dryrun/v3_wc4d_match_level_perception_gap_dryrun_20260603.csv"
PERCEPTION_DRYRUN_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_match_level_perception_gap_dryrun_20260603.json"
ODDS_TIMELINE_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_polling_cadence_20260604.json"
ODDS_LIVE_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json"
ODDS_MOVEMENT_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_movement_eligibility_20260604.json"

SAFETY = {
    "observation_only": True,
    "betting_recommendation": False,
    "affects_v4": False,
}
GLOBAL_SAFETY = {
    **SAFETY,
    "no_starting_xi": True,
    "no_prediction": True,
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def checker_status(path: Path) -> str:
    data = load_json(path)
    return str(data.get("conclusion") or "UNKNOWN") if isinstance(data, dict) else "UNKNOWN"


def source_exists(paths: list[Path]) -> bool:
    return all(path.exists() for path in paths)


def module(
    module_name: str,
    status: str,
    source_files: list[Path],
    checker: Path | None,
    data_status: str,
    next_action: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "module_name": module_name,
        "status": status,
        "source_files": [rel(path) for path in source_files],
        "source_files_exist": source_exists(source_files),
        "checker": rel(checker) if checker else None,
        "observation_only": True,
        "affects_v4": False,
        "betting_recommendation": False,
        "data_status": data_status,
        "next_action": next_action,
    }
    if extra:
        payload.update(extra)
    return payload


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    final26 = load_json(FINAL26_MANIFEST)
    final26_counts = final26.get("counts") if isinstance(final26, dict) and isinstance(final26.get("counts"), dict) else {}
    position_distribution = final26_counts.get("position_distribution") if isinstance(final26_counts.get("position_distribution"), dict) else {}

    venue = load_json(VENUE_STRESS)
    tactical = load_json(TACTICAL_PROFILE)
    closing = load_json(CLOSING_1X2)
    wc10 = load_json(WC10_WAR_ROOM)
    odds_live = load_json(ODDS_LIVE_STATUS)
    odds_movement = load_json(ODDS_MOVEMENT_STATUS)
    odds_timeline = load_json(ODDS_TIMELINE_STATUS)
    match_card_104 = load_json(MATCH_CARD_104_SUMMARY)
    dashboard_104 = load_json(DASHBOARD_104_READ_MODEL)
    coverage_104 = load_json(COVERAGE_GAP_RADAR_SUMMARY)

    live_coverage = odds_live.get("coverage") if isinstance(odds_live, dict) and isinstance(odds_live.get("coverage"), dict) else {}
    movement = odds_movement.get("movement_eligibility") if isinstance(odds_movement, dict) and isinstance(odds_movement.get("movement_eligibility"), dict) else {}
    availability = odds_timeline.get("availability_monitor") if isinstance(odds_timeline, dict) and isinstance(odds_timeline.get("availability_monitor"), dict) else {}

    modules = [
        module(
            "venue_stress_layer",
            "READY",
            [VENUE_STRESS],
            ROOT / "tools/check_v3_worldcup_venue_stress.py",
            f"{int(venue.get('venue_count') or 0)} venues; focus={int(venue.get('focus_venue_count') or 0)}",
            "Keep as venue observation layer until matchday weather feeds are available.",
        ),
        module(
            "perception_gap_dryrun",
            "DRYRUN_READY",
            [PERCEPTION_DRYRUN_CSV, PERCEPTION_DRYRUN_STATUS],
            ROOT / "tools/check_v3_worldcup_match_level_perception_gap_dryrun.py",
            f"sample_count={int((load_json(PERCEPTION_DRYRUN_STATUS).get('sample_count') if isinstance(load_json(PERCEPTION_DRYRUN_STATUS), dict) else 0) or 5)}",
            "Refresh only when new observation inputs are authorized.",
        ),
        module(
            "tactical_profile_layer",
            "READY",
            [TACTICAL_PROFILE],
            ROOT / "tools/check_v3_worldcup_tactical_profile_layer.py",
            (
                f"profiles={int(tactical.get('teams_profiled_count') or 0)}; "
                f"formation_samples={int(tactical.get('formation_matchup_samples_count') or 0)}"
            ),
            "Use as historical formation observation only.",
        ),
        module(
            "closing_1x2_market_structure",
            "READY",
            [CLOSING_1X2],
            ROOT / "tools/check_v3_worldcup_closing_1x2_market_structure.py",
            f"matches={int(closing.get('total_matches') or 0)}; closing_1x2_complete={bool(closing.get('closing_1x2_complete'))}",
            "Keep as historical closing structure baseline; no live movement conclusion.",
        ),
        module(
            "odds_snapshot_timeline",
            "LIVE_SNAPSHOT_FOUNDATION_READY",
            [ODDS_LIVE_STATUS, ODDS_TIMELINE_STATUS],
            ROOT / "tools/check_v3_worldcup_odds_polling_cadence.py",
            (
                f"requested={int(live_coverage.get('requested_count') or 0)}; "
                f"fixtures_with_odds={int(availability.get('fixtures_with_odds') or live_coverage.get('successful_fixture_count') or 0)}"
            ),
            "Continue manual snapshots only when authorized; timeline remains observation-only.",
        ),
        module(
            "odds_observation_delta",
            "ELIGIBILITY_READY_NO_CONCLUSION",
            [ODDS_MOVEMENT_STATUS],
            ROOT / "tools/check_v3_worldcup_odds_movement_eligibility.py",
            (
                f"snapshots={int(movement.get('snapshot_count') or 0)}; "
                f"changed_odds_count={int(movement.get('changed_odds_count') or 0)}; "
                f"eligibility_status={movement.get('eligibility_status') or 'UNKNOWN'}"
            ),
            "Observe odds_observation_delta only after additional snapshots; no money-flow judgment.",
        ),
        module(
            "final_26_squad_pack",
            "LOCKED",
            [FINAL26_MANIFEST],
            ROOT / "tools/check_v3_worldcup_final_26_pack_manifest.py",
            (
                f"teams={int(final26_counts.get('team_count') or 0)}; "
                f"players={int(final26_counts.get('total_players') or 0)}"
            ),
            "Use canonical final 26 artifacts as locked roster source.",
            {
                "team_count": int(final26_counts.get("team_count") or 0),
                "total_players": int(final26_counts.get("total_players") or 0),
                "coach_count": int(final26_counts.get("coach_count") or 0),
                "position_distribution": position_distribution,
            },
        ),
        module(
            "final_26_squad_profile",
            "READY",
            [FINAL26_PROFILE],
            ROOT / "tools/check_v3_worldcup_final_26_squad_profile_observation.py",
            "profile observation derived from final 26 canonical layer",
            "Expose roster profile summaries only.",
        ),
        module(
            "wc10_war_room",
            "READY",
            [WC10_WAR_ROOM],
            ROOT / "tools/check_v3_worldcup_wc10_war_room.py",
            (
                "final_26_nodes="
                f"{bool(isinstance(wc10, dict) and wc10.get('final_26_squad_observation'))}/"
                f"{bool(isinstance(wc10, dict) and wc10.get('final_26_squad_profile_observation'))}"
            ),
            "Use WC10 as current war room summary surface.",
        ),
        module(
            "lineup_readiness_pending",
            "PENDING_OFFICIAL_LINEUP",
            [LINEUP_READINESS],
            ROOT / "tools/check_v3_worldcup_lineup_readiness_schema.py",
            "starting_xi_status=NOT_AVAILABLE; matchday_lineup_status=WAIT_OFFICIAL_LINEUP",
            "Wait for official matchday lineup source before any lineup readiness update.",
        ),
        module(
            "coverage_gap_radar_104",
            "READY",
            [COVERAGE_GAP_RADAR, COVERAGE_GAP_RADAR_SUMMARY, MATCH_CARD_104_INDEX],
            ROOT / "tools/check_v3_worldcup_104_coverage_gap_radar.py",
            (
                f"coverage_cards={int((coverage_104.get('coverage_104') or {}).get('card_count') or 0)}; "
                f"group_view={int((coverage_104.get('group_72') or {}).get('card_count') or 0)}; "
                f"knockout_slots={int((coverage_104.get('knockout_32') or {}).get('card_count') or 0)}"
            ),
            "Expose 104 coverage and gap summary to War Room and dashboard read model.",
            {
                "coverage_radar": rel(COVERAGE_GAP_RADAR),
                "coverage_summary": rel(COVERAGE_GAP_RADAR_SUMMARY),
                "coverage_104": coverage_104.get("coverage_104") if isinstance(coverage_104, dict) else {},
                "group_72": coverage_104.get("group_72") if isinstance(coverage_104, dict) else {},
                "knockout_32": coverage_104.get("knockout_32") if isinstance(coverage_104, dict) else {},
                "gap_summary": coverage_104.get("gaps") if isinstance(coverage_104, dict) else {},
            },
        ),
        module(
            "match_card_104_canonical_index",
            "READY",
            [MATCH_CARD_104_INDEX, MATCH_CARD_104_SUMMARY, MATCH_CARD_72_VIEW],
            ROOT / "tools/check_v3_worldcup_104_cards_index_bridge.py",
            (
                f"canonical_cards={int(match_card_104.get('canonical_card_count') or 0)}; "
                f"group_view={int(match_card_104.get('group_stage_match_count') or 0)}; "
                f"knockout_slots={int(match_card_104.get('knockout_slot_count') or 0)}"
            ),
            "Read the 104 canonical index as the full tournament source; use the 72-card file only as group-stage view.",
            {
                "canonical_source": rel(MATCH_CARD_104_INDEX),
                "group_stage_view": rel(MATCH_CARD_72_VIEW),
                "expected_total_cards": 104,
                "canonical_card_count": int(match_card_104.get("canonical_card_count") or 0),
                "group_stage_view_count": 72,
                "knockout_slot_count": int(match_card_104.get("knockout_slot_count") or 0),
                "full_tournament_match_data_complete": False,
                "knockout_slot_policy": "STRUCTURAL_ONLY_NO_TEAM_GENERATED",
                "double_read_guard": "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE",
            },
        ),
        module(
            "dashboard_104_read_model",
            "READY",
            [DASHBOARD_104_READ_MODEL, MATCH_CARD_104_INDEX, MATCH_CARD_72_VIEW],
            ROOT / "tools/check_v3_worldcup_dashboard_104_read_model.py",
            (
                f"dashboard_canonical_cards={int(dashboard_104.get('canonical_card_count') or 0)}; "
                f"group_view={int(dashboard_104.get('group_stage_match_count') or 0)}; "
                f"knockout_slots={int(dashboard_104.get('knockout_slot_count') or 0)}"
            ),
            "Use the dashboard read model as the V3 UI/API read surface for the 104 canonical schedule.",
            {
                "dashboard_read_model": rel(DASHBOARD_104_READ_MODEL),
                "canonical_source": rel(MATCH_CARD_104_INDEX),
                "group_stage_view": rel(MATCH_CARD_72_VIEW),
                "expected_total_cards": 104,
                "canonical_card_count": int(dashboard_104.get("canonical_card_count") or 0),
                "group_stage_view_count": 72,
                "knockout_slot_count": int(dashboard_104.get("knockout_slot_count") or 0),
                "knockout_slot_policy": "STRUCTURAL_ONLY_NO_TEAM_GENERATED",
                "double_read_guard": "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE",
            },
        ),
    ]

    master_index = {
        "pack_name": "V3_WC_WAR_ROOM_MASTER_INDEX_PACK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "module_count": len(modules),
        "modules": modules,
        "global_safety": GLOBAL_SAFETY,
        "wc10_summary": {
            "source": rel(WC10_WAR_ROOM),
            "status": wc10.get("status") if isinstance(wc10, dict) else "UNKNOWN",
            "final_26_squad_observation_present": bool(isinstance(wc10, dict) and wc10.get("final_26_squad_observation")),
            "final_26_squad_profile_observation_present": bool(isinstance(wc10, dict) and wc10.get("final_26_squad_profile_observation")),
        },
        "checker_status": {
            "venue_stress_layer": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_venue_stress_20260603.json"),
            "perception_gap_dryrun": checker_status(PERCEPTION_DRYRUN_STATUS),
            "tactical_profile_layer": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_tactical_profile_layer_20260604.json"),
            "closing_1x2_market_structure": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_closing_1x2_market_structure_20260604.json"),
            "odds_snapshot_timeline": checker_status(ODDS_TIMELINE_STATUS),
            "odds_observation_delta": checker_status(ODDS_MOVEMENT_STATUS),
            "final_26_squad_pack": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_final_26_pack_manifest_20260604.json"),
            "final_26_squad_profile": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_final_26_squad_profile_observation_20260604.json"),
            "wc10_war_room": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_wc10_war_room_20260602.json"),
            "lineup_readiness_pending": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_lineup_readiness_schema_20260604.json"),
            "match_card_104_canonical_index": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_104_cards_index_bridge_20260605.json"),
            "dashboard_104_read_model": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_dashboard_104_read_model_20260605.json"),
            "coverage_gap_radar_104": checker_status(ROOT / "data/runtime/status/check_v3_worldcup_104_coverage_gap_radar_20260605.json"),
        },
    }

    odds_available_fixture_count = int(availability.get("fixtures_with_odds") or live_coverage.get("successful_fixture_count") or 0)
    gap_radar = {
        "pack_name": "V3_WC_WAR_ROOM_MASTER_INDEX_PACK",
        "generated_at": master_index["generated_at"],
        "source_master_index": rel(MASTER_INDEX),
        "missing_starting_xi": True,
        "missing_official_matchday_lineup": True,
        "missing_native_opening_odds": True,
        "missing_native_closing_odds": True,
        "missing_odds_movement_conclusion": True,
        "missing_injury_suspension_official_feed": True,
        "odds_available_fixture_count": odds_available_fixture_count,
        "coverage_104": coverage_104.get("coverage_104") if isinstance(coverage_104, dict) else {},
        "group_72": coverage_104.get("group_72") if isinstance(coverage_104, dict) else {},
        "knockout_32": coverage_104.get("knockout_32") if isinstance(coverage_104, dict) else {},
        "coverage_gap_summary": coverage_104.get("gaps") if isinstance(coverage_104, dict) else {},
        "final_26_ready": int(final26_counts.get("total_players") or 0) == 1248,
        "venue_stress_ready": VENUE_STRESS.exists(),
        "tactical_profile_ready": TACTICAL_PROFILE.exists(),
        "next_data_needed": [
            "official matchday lineup",
            "later odds snapshots",
            "official injury/suspension source if available",
        ],
        "safety": {
            **GLOBAL_SAFETY,
            "no_money_flow_judgment": True,
            "has_native_opening": False,
            "has_native_closing": False,
            "movement_requires_timeline": True,
        },
    }
    return master_index, gap_radar


def main() -> int:
    master_index, gap_radar = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MASTER_INDEX.write_text(json.dumps(master_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    GAP_RADAR.write_text(json.dumps(gap_radar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "master_index": rel(MASTER_INDEX),
        "gap_radar": rel(GAP_RADAR),
        "module_count": master_index["module_count"],
        "odds_available_fixture_count": gap_radar["odds_available_fixture_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
