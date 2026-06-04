#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/manual_sources/v3_worldcup/war_room"

CANONICAL_104 = OUT_DIR / "v3_wc2026_104_cards_index_bridge.json"
DASHBOARD_READ_MODEL = OUT_DIR / "v3_wc2026_dashboard_104_read_model.json"
MASTER_INDEX = OUT_DIR / "v3_wc_war_room_master_index.json"
FINAL26_TEAMS = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_final_26_teams.json"
LINEUP_READINESS = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_lineup_readiness_team_status.json"

COVERAGE_RADAR = OUT_DIR / "v3_wc2026_104_coverage_gap_radar.json"
COVERAGE_SUMMARY = OUT_DIR / "v3_wc2026_104_coverage_gap_radar_summary.json"

SAFETY = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}

TEAM_SLUG_ALIASES = {
    "cote_divoire": "cote_d_ivoire",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [] if path in {CANONICAL_104, FINAL26_TEAMS} else {}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def team_slugs_from_final26() -> set[str]:
    teams = load_json(FINAL26_TEAMS)
    if not isinstance(teams, list):
        return set()
    return {str(item.get("team_slug") or "").strip() for item in teams if isinstance(item, dict) and item.get("is_final_26") is True}


def lineup_team_status() -> dict[str, dict[str, Any]]:
    payload = load_json(LINEUP_READINESS)
    rows = payload.get("teams") if isinstance(payload, dict) and isinstance(payload.get("teams"), list) else []
    return {str(item.get("team_slug") or "").strip(): item for item in rows if isinstance(item, dict)}


def _both_present(row: dict[str, Any], left: str, right: str) -> bool:
    return bool(row.get(left)) and bool(row.get(right))


def canonical_team_slug(slug: Any) -> str:
    raw = str(slug or "").strip()
    return TEAM_SLUG_ALIASES.get(raw, raw)


def _lineup_status(row: dict[str, Any], lineup_by_slug: dict[str, dict[str, Any]]) -> str:
    slugs = [canonical_team_slug(row.get("home_team_slug")), canonical_team_slug(row.get("away_team_slug"))]
    if not all(slugs):
        return "STRUCTURAL_PLACEHOLDER"
    statuses = {lineup_by_slug.get(slug, {}).get("matchday_lineup_status") for slug in slugs}
    if statuses == {"WAIT_OFFICIAL_LINEUP"}:
        return "WAIT_OFFICIAL_LINEUP"
    return "LINEUP_STATUS_GAP"


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(CANONICAL_104)
    cards = rows if isinstance(rows, list) else []
    final26_slugs = team_slugs_from_final26()
    lineup_by_slug = lineup_team_status()

    radar: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    gap_reasons: Counter[str] = Counter()

    for row in cards:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("card_kind") or "UNKNOWN")
        is_group = kind == "GROUP_STAGE_MATCH"
        is_knockout = kind == "KNOCKOUT_SLOT"
        home_slug = str(row.get("home_team_slug") or "")
        away_slug = str(row.get("away_team_slug") or "")
        home_canonical_slug = canonical_team_slug(home_slug)
        away_canonical_slug = canonical_team_slug(away_slug)
        fixture_present = bool(row.get("api_football_fixture_id"))
        odds_fixture_present = bool(row.get("odds_fixture_id"))
        teams_known = _both_present(row, "home_team", "away_team") and bool(home_slug) and bool(away_slug)
        final26_ready = bool(home_canonical_slug in final26_slugs and away_canonical_slug in final26_slugs)

        if is_group:
            team_status = "KNOWN_FROM_GROUP_STAGE_SOURCE" if teams_known else "TEAM_GAP"
            venue_status = str(row.get("venue_mapping_status") or "VENUE_SOURCE_REQUIRED")
            fixture_status = "MAPPED" if fixture_present else "FIXTURE_ID_GAP"
            odds_status = "MAPPED" if odds_fixture_present else "ODDS_FIXTURE_ID_GAP"
            final26_status = "READY" if final26_ready else "FINAL26_TEAM_GAP"
            lineup_status = _lineup_status(row, lineup_by_slug)
            structural_placeholder = False
        else:
            team_status = "STRUCTURAL_PLACEHOLDER"
            venue_status = "STRUCTURAL_PLACEHOLDER"
            fixture_status = "STRUCTURAL_PLACEHOLDER"
            odds_status = "STRUCTURAL_PLACEHOLDER"
            final26_status = "STRUCTURAL_PLACEHOLDER"
            lineup_status = "STRUCTURAL_PLACEHOLDER"
            structural_placeholder = True

        gaps: list[str] = []
        if is_group and venue_status not in {"MAPPED", "READY"}:
            gaps.append(str(row.get("venue_gap_reason") or "VENUE_SOURCE_REQUIRED"))
        if is_group and lineup_status != "WAIT_OFFICIAL_LINEUP":
            gaps.append("LINEUP_STATUS_GAP")
        if is_group and not fixture_present:
            gaps.append("FIXTURE_ID_GAP")
        if is_group and not odds_fixture_present:
            gaps.append("ODDS_FIXTURE_ID_GAP")
        if is_group and not final26_ready:
            gaps.append("FINAL26_TEAM_GAP")
        if is_knockout:
            gaps.append("KNOCKOUT_STRUCTURAL_PLACEHOLDER_WAIT_OFFICIAL_TEAMS")
            gaps.append("KNOCKOUT_STRUCTURAL_PLACEHOLDER_WAIT_OFFICIAL_FIXTURE")

        item = {
            "canonical_card_id": row.get("canonical_card_id"),
            "match_card_id": row.get("match_card_id"),
            "scope_bucket": "GROUP_72" if is_group else "KNOCKOUT_32" if is_knockout else "UNKNOWN",
            "card_kind": kind,
            "round": row.get("round"),
            "group": row.get("group"),
            "home_team": row.get("home_team") if is_group else None,
            "away_team": row.get("away_team") if is_group else None,
            "home_team_slug": home_slug if is_group else None,
            "away_team_slug": away_slug if is_group else None,
            "home_canonical_team_slug": home_canonical_slug if is_group else None,
            "away_canonical_team_slug": away_canonical_slug if is_group else None,
            "team_slug_alias_applied": bool(is_group and (home_slug != home_canonical_slug or away_slug != away_canonical_slug)),
            "team_coverage_status": team_status,
            "venue_coverage_status": venue_status,
            "fixture_id_coverage_status": fixture_status,
            "odds_fixture_id_coverage_status": odds_status,
            "final26_coverage_status": final26_status,
            "lineup_coverage_status": lineup_status,
            "war_room_coverage_status": "REGISTERED_IN_104_CHAIN",
            "dashboard_coverage_status": "REGISTERED_IN_DASHBOARD_104_READ_MODEL",
            "structural_placeholder": structural_placeholder,
            "gap_reasons": gaps,
            **SAFETY,
        }
        radar.append(item)

        prefix = "group_72" if is_group else "knockout_32" if is_knockout else "unknown"
        counters[f"{prefix}_count"] += 1
        for field, status in [
            ("team", team_status),
            ("venue", venue_status),
            ("fixture_id", fixture_status),
            ("odds_fixture_id", odds_status),
            ("final26", final26_status),
            ("lineup", lineup_status),
            ("war_room", item["war_room_coverage_status"]),
            ("dashboard", item["dashboard_coverage_status"]),
        ]:
            counters[f"{prefix}_{field}_{status}"] += 1
            counters[f"all_{field}_{status}"] += 1
        for reason in gaps:
            gap_reasons[reason] += 1

    summary = {
        "pack_name": "V3_WC_2026_104_COVERAGE_GAP_RADAR_PACK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "canonical_source": rel(CANONICAL_104),
        "coverage_radar": rel(COVERAGE_RADAR),
        "coverage_summary": rel(COVERAGE_SUMMARY),
        "coverage_104": {
            "card_count": len(radar),
            "team_known_count": counters.get("group_72_team_KNOWN_FROM_GROUP_STAGE_SOURCE", 0),
            "team_structural_placeholder_count": counters.get("knockout_32_team_STRUCTURAL_PLACEHOLDER", 0),
            "fixture_id_mapped_count": counters.get("group_72_fixture_id_MAPPED", 0),
            "odds_fixture_id_mapped_count": counters.get("group_72_odds_fixture_id_MAPPED", 0),
            "venue_mapped_count": counters.get("group_72_venue_MAPPED", 0),
            "final26_ready_group_card_count": counters.get("group_72_final26_READY", 0),
            "lineup_wait_official_count": counters.get("group_72_lineup_WAIT_OFFICIAL_LINEUP", 0),
            "war_room_registered_count": counters.get("all_war_room_REGISTERED_IN_104_CHAIN", 0),
            "dashboard_registered_count": counters.get("all_dashboard_REGISTERED_IN_DASHBOARD_104_READ_MODEL", 0),
        },
        "group_72": {
            "card_count": counters.get("group_72_count", 0),
            "team_known_count": counters.get("group_72_team_KNOWN_FROM_GROUP_STAGE_SOURCE", 0),
            "venue_mapped_count": counters.get("group_72_venue_MAPPED", 0),
            "venue_source_required_count": counters.get("group_72_venue_UNMAPPED", 0) + counters.get("group_72_venue_VENUE_SOURCE_REQUIRED", 0),
            "fixture_id_mapped_count": counters.get("group_72_fixture_id_MAPPED", 0),
            "odds_fixture_id_mapped_count": counters.get("group_72_odds_fixture_id_MAPPED", 0),
            "final26_ready_card_count": counters.get("group_72_final26_READY", 0),
            "final26_gap_card_count": counters.get("group_72_final26_FINAL26_TEAM_GAP", 0),
            "lineup_wait_official_count": counters.get("group_72_lineup_WAIT_OFFICIAL_LINEUP", 0),
            "lineup_gap_card_count": counters.get("group_72_lineup_LINEUP_STATUS_GAP", 0),
            "war_room_registered_count": counters.get("group_72_war_room_REGISTERED_IN_104_CHAIN", 0),
            "dashboard_registered_count": counters.get("group_72_dashboard_REGISTERED_IN_DASHBOARD_104_READ_MODEL", 0),
        },
        "knockout_32": {
            "card_count": counters.get("knockout_32_count", 0),
            "structural_placeholder_count": counters.get("knockout_32_team_STRUCTURAL_PLACEHOLDER", 0),
            "team_generated_count": 0,
            "fixture_id_generated_count": 0,
            "odds_fixture_id_generated_count": 0,
            "venue_generated_count": 0,
            "final26_status": "STRUCTURAL_PLACEHOLDER",
            "lineup_status": "STRUCTURAL_PLACEHOLDER",
            "war_room_registered_count": counters.get("knockout_32_war_room_REGISTERED_IN_104_CHAIN", 0),
            "dashboard_registered_count": counters.get("knockout_32_dashboard_REGISTERED_IN_DASHBOARD_104_READ_MODEL", 0),
        },
        "gaps": {
            "reason_distribution": dict(sorted(gap_reasons.items())),
            "venue_source_required": counters.get("group_72_venue_UNMAPPED", 0) + counters.get("group_72_venue_VENUE_SOURCE_REQUIRED", 0),
            "official_lineup_required": counters.get("group_72_lineup_WAIT_OFFICIAL_LINEUP", 0),
            "knockout_structural_placeholder": counters.get("knockout_32_count", 0),
            "native_opening_closing_missing": True,
            "odds_movement_conclusion_missing": True,
        },
        "field_coverage": dict(sorted(counters.items())),
        "safety": SAFETY,
    }
    return radar, summary


def main() -> int:
    radar, summary = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_RADAR.write_text(json.dumps(radar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    COVERAGE_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "coverage_radar": rel(COVERAGE_RADAR),
        "coverage_summary": rel(COVERAGE_SUMMARY),
        "card_count": summary["coverage_104"]["card_count"],
        "group_72": summary["group_72"]["card_count"],
        "knockout_32": summary["knockout_32"]["card_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
