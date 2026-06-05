#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WAR_ROOM = ROOT / "data/manual_sources/v3_worldcup/war_room"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_live_data_readiness_guard_20260605.json"

COVERAGE_RADAR = WAR_ROOM / "v3_wc2026_104_coverage_gap_radar.json"
COVERAGE_SUMMARY = WAR_ROOM / "v3_wc2026_104_coverage_gap_radar_summary.json"
DASHBOARD_READ_MODEL = WAR_ROOM / "v3_wc2026_dashboard_104_read_model.json"
WAR_ROOM_GAP_RADAR = WAR_ROOM / "v3_wc_war_room_gap_radar.json"
WAR_ROOM_MASTER_INDEX = WAR_ROOM / "v3_wc_war_room_master_index.json"
ODDS_MOVEMENT_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_movement_eligibility_20260604.json"
ODDS_LIVE_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json"

APPROVED_DASHBOARD_UI_STAGE = "v2_football_quant/data/runtime/dashboard/v3_worldcup_wc10_war_room.html"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]

DISALLOWED_KEYS = {
    "starting_xi_players",
    "predicted_lineup",
    "confirmed_lineup",
    "official_starting_xi",
    "injury_status",
    "suspension_status",
    "recommended_pick",
    "recommendation_output",
    "betting_signal",
    "fund_flow_signal",
    "steam_signal",
    "drift_signal",
    "sharp_signal",
    "movement_conclusion",
    "odds_movement_conclusion",
}

DISALLOWED_PHRASES = [
    "fund flow conclusion",
    "money flow conclusion",
    "steam conclusion",
    "drift conclusion",
    "sharp move conclusion",
    "starting xi generated",
    "predicted xi generated",
    "confirmed lineup generated",
    "movement conclusion generated",
    "odds movement conclusion generated",
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def tracked_runtime_hits() -> list[str]:
    result = git(["ls-files", "data/runtime", "runtime", "logs", "cache", "tmp"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def walk_keys(obj: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.append(str(key))
            keys.extend(walk_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(walk_keys(item))
    return keys


def main() -> int:
    coverage = load_json(COVERAGE_RADAR)
    summary = load_json(COVERAGE_SUMMARY)
    dashboard = load_json(DASHBOARD_READ_MODEL)
    gap_radar = load_json(WAR_ROOM_GAP_RADAR)
    master = load_json(WAR_ROOM_MASTER_INDEX)
    odds_movement = load_json(ODDS_MOVEMENT_STATUS)
    odds_live = load_json(ODDS_LIVE_STATUS)

    failures: list[str] = []
    for path in [
        COVERAGE_RADAR,
        COVERAGE_SUMMARY,
        DASHBOARD_READ_MODEL,
        WAR_ROOM_GAP_RADAR,
        WAR_ROOM_MASTER_INDEX,
        ODDS_MOVEMENT_STATUS,
        ODDS_LIVE_STATUS,
    ]:
        add(failures, path.exists(), "required_file_missing", str(path.relative_to(ROOT)))

    group = [row for row in coverage if isinstance(row, dict) and row.get("scope_bucket") == "GROUP_72"]
    knockout = [row for row in coverage if isinstance(row, dict) and row.get("scope_bucket") == "KNOCKOUT_32"]
    add(failures, len(group) == 72, "group_72_count_unexpected", len(group))
    add(failures, len(knockout) == 32, "knockout_32_count_unexpected", len(knockout))

    for row in group:
        cid = row.get("canonical_card_id")
        add(failures, row.get("lineup_coverage_status") == "WAIT_OFFICIAL_LINEUP", "group_lineup_not_wait_official", cid)
        add(failures, row.get("final26_coverage_status") == "READY", "group_final26_not_ready", cid)
        add(failures, row.get("structural_placeholder") is False, "group_structural_placeholder_true", cid)

    for row in knockout:
        cid = row.get("canonical_card_id")
        add(failures, row.get("structural_placeholder") is True, "knockout_not_structural_placeholder", cid)
        add(failures, row.get("home_team") is None and row.get("away_team") is None, "knockout_real_team_generated", cid)
        add(failures, row.get("team_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_team_status_unexpected", cid)
        add(failures, row.get("fixture_id_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_fixture_status_unexpected", cid)
        add(failures, row.get("odds_fixture_id_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_odds_status_unexpected", cid)
        add(failures, row.get("final26_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_final26_status_unexpected", cid)
        add(failures, row.get("lineup_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_lineup_status_unexpected", cid)

    summary_group = summary.get("group_72") if isinstance(summary.get("group_72"), dict) else {}
    summary_knockout = summary.get("knockout_32") if isinstance(summary.get("knockout_32"), dict) else {}
    summary_gaps = summary.get("gaps") if isinstance(summary.get("gaps"), dict) else {}
    add(failures, summary_group.get("lineup_wait_official_count") == 72, "summary_group_lineup_wait_unexpected", summary_group)
    add(failures, summary_group.get("lineup_gap_card_count") == 0, "summary_group_lineup_gap_unexpected", summary_group)
    add(failures, summary_group.get("venue_source_required_count") == 0, "summary_group_venue_source_required_unexpected", summary_group)
    add(failures, summary_knockout.get("structural_placeholder_count") == 32, "summary_knockout_placeholder_unexpected", summary_knockout)
    for key in ["team_generated_count", "fixture_id_generated_count", "odds_fixture_id_generated_count"]:
        add(failures, summary_knockout.get(key) == 0, f"summary_knockout_{key}_unexpected", summary_knockout)
    add(failures, summary_gaps.get("official_lineup_required") == 72, "summary_official_lineup_required_unexpected", summary_gaps)
    add(failures, summary_gaps.get("knockout_structural_placeholder") == 32, "summary_knockout_gap_unexpected", summary_gaps)
    add(failures, summary_gaps.get("native_opening_closing_missing") is True, "summary_native_opening_closing_missing_unexpected", summary_gaps)
    add(failures, summary_gaps.get("odds_movement_conclusion_missing") is True, "summary_odds_conclusion_gap_unexpected", summary_gaps)

    dashboard_gap = dashboard.get("coverage_gap_summary") if isinstance(dashboard.get("coverage_gap_summary"), dict) else {}
    dashboard_knockout = dashboard.get("knockout_slots") if isinstance(dashboard.get("knockout_slots"), dict) else {}
    add(failures, (dashboard_gap.get("group_72") or {}).get("lineup_wait_official_count") == 72, "dashboard_lineup_wait_missing", dashboard_gap)
    add(failures, (dashboard_gap.get("gaps") or {}).get("native_opening_closing_missing") is True, "dashboard_native_gap_missing", dashboard_gap)
    add(failures, (dashboard_gap.get("gaps") or {}).get("odds_movement_conclusion_missing") is True, "dashboard_odds_conclusion_gap_missing", dashboard_gap)
    add(failures, dashboard_knockout.get("policy") == "STRUCTURAL_ONLY_NO_TEAM_GENERATED", "dashboard_knockout_policy_unexpected", dashboard_knockout)
    add(failures, dashboard_knockout.get("team_fields_empty") is True, "dashboard_knockout_team_fields_not_empty", dashboard_knockout)
    add(failures, dashboard_knockout.get("fixture_fields_empty") is True, "dashboard_knockout_fixture_fields_not_empty", dashboard_knockout)

    add(failures, gap_radar.get("missing_official_matchday_lineup") is True, "war_room_missing_official_lineup_flag_unexpected", gap_radar)
    add(failures, gap_radar.get("missing_native_opening_odds") is True, "war_room_missing_native_opening_flag_unexpected", gap_radar)
    add(failures, gap_radar.get("missing_native_closing_odds") is True, "war_room_missing_native_closing_flag_unexpected", gap_radar)
    add(failures, gap_radar.get("missing_odds_movement_conclusion") is True, "war_room_missing_odds_conclusion_flag_unexpected", gap_radar)
    add(failures, (gap_radar.get("knockout_32") or {}).get("structural_placeholder_count") == 32, "war_room_knockout_placeholder_unexpected", gap_radar.get("knockout_32"))

    modules = master.get("modules") if isinstance(master.get("modules"), list) else []
    lineup_module = next((m for m in modules if isinstance(m, dict) and m.get("module_name") == "lineup_readiness_pending"), {})
    add(failures, "WAIT_OFFICIAL_LINEUP" in str(lineup_module), "master_lineup_wait_not_visible", lineup_module)

    movement = odds_movement.get("movement_eligibility") if isinstance(odds_movement.get("movement_eligibility"), dict) else {}
    add(failures, movement.get("has_native_opening") is False, "movement_native_opening_true", movement)
    add(failures, movement.get("has_native_closing") is False, "movement_native_closing_true", movement)
    add(failures, movement.get("movement_requires_timeline") is True, "movement_requires_timeline_unexpected", movement)
    add(failures, movement.get("no_money_flow_judgment") is True, "movement_money_flow_guard_missing", movement)
    add(failures, movement.get("delta_label") == "odds_observation_delta", "movement_delta_label_unexpected", movement)
    add(
        failures,
        movement.get("eligibility_status") in {
            "NOT_ELIGIBLE_SINGLE_SNAPSHOT",
            "ELIGIBLE_MULTIPLE_SNAPSHOTS_NO_CHANGE",
            "ELIGIBLE_MULTIPLE_SNAPSHOTS_WITH_CHANGE",
        },
        "movement_eligibility_status_unexpected",
        movement,
    )
    live_coverage = odds_live.get("coverage") if isinstance(odds_live.get("coverage"), dict) else odds_live
    add(failures, live_coverage.get("has_native_opening") is False, "live_native_opening_true", live_coverage)
    add(failures, live_coverage.get("has_native_closing") is False, "live_native_closing_true", live_coverage)
    add(failures, live_coverage.get("movement_requires_timeline") is True, "live_movement_requires_timeline_unexpected", live_coverage)

    combined = {
        "coverage": coverage,
        "summary": summary,
        "dashboard": dashboard,
        "gap_radar": gap_radar,
        "master": master,
        "odds_movement": odds_movement,
        "odds_live": odds_live,
    }
    keys = {key.lower() for key in walk_keys(combined)}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    text = json.dumps(combined, ensure_ascii=False).lower()
    for phrase in DISALLOWED_PHRASES:
        add(failures, phrase not in text, "disallowed_generated_phrase", phrase)

    staged = staged_files()
    runtime_staged = [
        path for path in staged
        if path != APPROVED_DASHBOARD_UI_STAGE
        and re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)
    ]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    relevant_runtime = [path for path in tracked_runtime_hits() if "live_data_readiness_guard" in path]
    add(failures, not relevant_runtime, "runtime_live_data_readiness_guard_tracked", relevant_runtime)
    secrets = secret_hits([Path(__file__).resolve(), DASHBOARD_READ_MODEL, WAR_ROOM_GAP_RADAR, COVERAGE_SUMMARY])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "guards": {
            "official_lineup_guard": "WAIT_OFFICIAL_LINEUP_ONLY_UNTIL_OFFICIAL_SOURCE",
            "knockout_guard": "STRUCTURAL_PLACEHOLDER_ONLY_NO_REAL_TEAM_GENERATED",
            "odds_guard": "NO_MOVEMENT_CONCLUSION_WITHOUT_NATIVE_OPENING_CLOSING",
        },
        "group_72_lineup_wait_official": summary_group.get("lineup_wait_official_count"),
        "knockout_32_structural_placeholder": summary_knockout.get("structural_placeholder_count"),
        "native_opening_closing_missing": summary_gaps.get("native_opening_closing_missing"),
        "odds_movement_conclusion_missing": summary_gaps.get("odds_movement_conclusion_missing"),
        "runtime_staged": runtime_staged,
        "v4_staged": v4_staged,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
