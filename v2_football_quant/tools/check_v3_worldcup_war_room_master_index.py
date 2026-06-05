#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_war_room_master_index import GAP_RADAR, MASTER_INDEX, build

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_war_room_master_index_20260604.json"
APPROVED_DASHBOARD_UI_STAGE = "v2_football_quant/data/runtime/dashboard/v3_worldcup_wc10_war_room.html"

REQUIRED_MODULES = {
    "venue_stress_layer",
    "perception_gap_dryrun",
    "tactical_profile_layer",
    "closing_1x2_market_structure",
    "odds_snapshot_timeline",
    "odds_observation_delta",
    "odds_polling_budget_plan",
    "final_26_squad_pack",
    "final_26_squad_profile",
    "wc10_war_room",
    "lineup_readiness_pending",
    "coverage_gap_radar_104",
    "match_card_104_canonical_index",
    "dashboard_104_read_model",
}
EXPECTED_SAFETY = {
    "observation_only": True,
    "betting_recommendation": False,
    "affects_v4": False,
    "no_starting_xi": True,
    "no_prediction": True,
}
EXPECTED_POLLING_WINDOWS = ["T-24h", "T-6h", "T-2h", "T-90m", "T-60m", "T-30m"]
EXPECTED_ODDS_FIELDS = ["first_seen_odds", "last_pre_kickoff_odds", "odds_observation_delta"]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
DISALLOWED_KEYS = {
    "starting_xi_players",
    "predicted_xi",
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
}
DISALLOWED_PHRASES = [
    "starting xi generated",
    "predicted xi",
    "confirmed lineup",
    "injury judgment",
    "suspension judgment",
    "money flow conclusion",
    "fund flow conclusion",
    "steam conclusion",
    "drift conclusion",
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


def staged_v4_hits(paths: list[str]) -> list[str]:
    return [path for path in paths if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]


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
    master, gap = build()
    MASTER_INDEX.parent.mkdir(parents=True, exist_ok=True)
    MASTER_INDEX.write_text(json.dumps(master, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    GAP_RADAR.write_text(json.dumps(gap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    add(failures, MASTER_INDEX.exists(), "master_index_missing", MASTER_INDEX)
    add(failures, GAP_RADAR.exists(), "gap_radar_missing", GAP_RADAR)

    modules = master.get("modules") if isinstance(master.get("modules"), list) else []
    names = {item.get("module_name") for item in modules if isinstance(item, dict)}
    add(failures, int(master.get("module_count") or 0) >= 10, "module_count_too_low", master.get("module_count"))
    add(failures, REQUIRED_MODULES.issubset(names), "required_modules_missing", sorted(REQUIRED_MODULES - names))

    final_module = next((item for item in modules if isinstance(item, dict) and item.get("module_name") == "final_26_squad_pack"), {})
    add(failures, final_module.get("status") == "LOCKED", "final_26_squad_pack_not_locked", final_module.get("status"))
    add(failures, final_module.get("total_players") == 1248, "final_26_total_players_unexpected", final_module.get("total_players"))
    coverage_module = next((item for item in modules if isinstance(item, dict) and item.get("module_name") == "coverage_gap_radar_104"), {})
    add(failures, coverage_module.get("coverage_radar") == "data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_coverage_gap_radar.json", "coverage_radar_source_unexpected", coverage_module.get("coverage_radar"))
    add(failures, coverage_module.get("coverage_summary") == "data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_coverage_gap_radar_summary.json", "coverage_summary_source_unexpected", coverage_module.get("coverage_summary"))
    add(failures, (coverage_module.get("coverage_104") or {}).get("card_count") == 104, "coverage_104_count_unexpected", coverage_module.get("coverage_104"))
    add(failures, (coverage_module.get("group_72") or {}).get("card_count") == 72, "coverage_group_72_count_unexpected", coverage_module.get("group_72"))
    add(failures, (coverage_module.get("knockout_32") or {}).get("card_count") == 32, "coverage_knockout_32_count_unexpected", coverage_module.get("knockout_32"))
    add(failures, (coverage_module.get("knockout_32") or {}).get("structural_placeholder_count") == 32, "coverage_knockout_placeholder_unexpected", coverage_module.get("knockout_32"))
    match_card_module = next((item for item in modules if isinstance(item, dict) and item.get("module_name") == "match_card_104_canonical_index"), {})
    add(failures, match_card_module.get("canonical_source") == "data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_cards_index_bridge.json", "match_card_104_canonical_source_unexpected", match_card_module.get("canonical_source"))
    add(failures, match_card_module.get("group_stage_view") == "data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json", "match_card_group_view_unexpected", match_card_module.get("group_stage_view"))
    add(failures, match_card_module.get("expected_total_cards") == 104, "match_card_expected_total_unexpected", match_card_module.get("expected_total_cards"))
    add(failures, match_card_module.get("canonical_card_count") == 104, "match_card_canonical_count_unexpected", match_card_module.get("canonical_card_count"))
    add(failures, match_card_module.get("group_stage_view_count") == 72, "match_card_group_view_count_unexpected", match_card_module.get("group_stage_view_count"))
    add(failures, match_card_module.get("knockout_slot_count") == 32, "match_card_knockout_slot_count_unexpected", match_card_module.get("knockout_slot_count"))
    add(failures, match_card_module.get("full_tournament_match_data_complete") is False, "match_card_full_tournament_complete_unexpected", match_card_module.get("full_tournament_match_data_complete"))
    add(failures, match_card_module.get("knockout_slot_policy") == "STRUCTURAL_ONLY_NO_TEAM_GENERATED", "match_card_knockout_slot_policy_unexpected", match_card_module.get("knockout_slot_policy"))
    add(failures, match_card_module.get("double_read_guard") == "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE", "match_card_double_read_guard_missing", match_card_module.get("double_read_guard"))
    dashboard_module = next((item for item in modules if isinstance(item, dict) and item.get("module_name") == "dashboard_104_read_model"), {})
    add(failures, dashboard_module.get("dashboard_read_model") == "data/manual_sources/v3_worldcup/war_room/v3_wc2026_dashboard_104_read_model.json", "dashboard_104_read_model_unexpected", dashboard_module.get("dashboard_read_model"))
    add(failures, dashboard_module.get("canonical_source") == "data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_cards_index_bridge.json", "dashboard_104_canonical_source_unexpected", dashboard_module.get("canonical_source"))
    add(failures, dashboard_module.get("canonical_card_count") == 104, "dashboard_104_canonical_count_unexpected", dashboard_module.get("canonical_card_count"))
    add(failures, dashboard_module.get("group_stage_view_count") == 72, "dashboard_group_view_count_unexpected", dashboard_module.get("group_stage_view_count"))
    add(failures, dashboard_module.get("knockout_slot_count") == 32, "dashboard_knockout_slot_count_unexpected", dashboard_module.get("knockout_slot_count"))
    add(failures, dashboard_module.get("knockout_slot_policy") == "STRUCTURAL_ONLY_NO_TEAM_GENERATED", "dashboard_knockout_slot_policy_unexpected", dashboard_module.get("knockout_slot_policy"))
    add(failures, dashboard_module.get("double_read_guard") == "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE", "dashboard_double_read_guard_missing", dashboard_module.get("double_read_guard"))

    odds_budget_module = next((item for item in modules if isinstance(item, dict) and item.get("module_name") == "odds_polling_budget_plan"), {})
    odds_budget = odds_budget_module.get("odds_polling_budget") if isinstance(odds_budget_module.get("odds_polling_budget"), dict) else {}
    add(failures, odds_budget_module.get("status") == "READY_NO_LIVE_API", "odds_budget_module_status_unexpected", odds_budget_module.get("status"))
    add(failures, odds_budget.get("source") == "config/v3_worldcup_odds_polling_cadence.json", "odds_budget_source_unexpected", odds_budget.get("source"))
    add(failures, odds_budget.get("api_provider") == "api-football", "odds_budget_provider_unexpected", odds_budget.get("api_provider"))
    add(failures, odds_budget.get("quota_budget_per_day") == 7500, "odds_budget_quota_unexpected", odds_budget.get("quota_budget_per_day"))
    add(failures, isinstance(odds_budget.get("system_max_daily_requests"), int) and odds_budget.get("system_max_daily_requests") <= 1500, "odds_budget_system_max_exceeds_1500", odds_budget.get("system_max_daily_requests"))
    add(failures, isinstance(odds_budget.get("default_target_requests_per_day"), int) and odds_budget.get("default_target_requests_per_day") <= 600, "odds_budget_default_target_exceeds_600", odds_budget.get("default_target_requests_per_day"))
    add(failures, isinstance(odds_budget.get("hard_stop_at_requests_per_day"), int) and odds_budget.get("hard_stop_at_requests_per_day") <= 6000, "odds_budget_hard_stop_exceeds_6000", odds_budget.get("hard_stop_at_requests_per_day"))
    add(failures, odds_budget.get("canonical_total") == 104, "odds_budget_canonical_total_unexpected", odds_budget.get("canonical_total"))
    add(failures, odds_budget.get("group_stage_total") == 72, "odds_budget_group_total_unexpected", odds_budget.get("group_stage_total"))
    add(failures, odds_budget.get("knockout_reserved_total") == 32, "odds_budget_knockout_total_unexpected", odds_budget.get("knockout_reserved_total"))
    add(failures, odds_budget.get("polling_windows") == EXPECTED_POLLING_WINDOWS, "odds_budget_windows_unexpected", odds_budget.get("polling_windows"))
    add(failures, odds_budget.get("allowed_odds_observation_fields") == EXPECTED_ODDS_FIELDS, "odds_budget_allowed_fields_unexpected", odds_budget.get("allowed_odds_observation_fields"))
    add(failures, odds_budget.get("has_native_opening") is False, "odds_budget_native_opening_unexpected", odds_budget.get("has_native_opening"))
    add(failures, odds_budget.get("has_native_closing") is False, "odds_budget_native_closing_unexpected", odds_budget.get("has_native_closing"))
    add(failures, odds_budget.get("movement_requires_timeline") is True, "odds_budget_timeline_required_unexpected", odds_budget.get("movement_requires_timeline"))
    add(failures, odds_budget.get("no_money_flow_judgment") is True, "odds_budget_money_flow_guard_missing", odds_budget.get("no_money_flow_judgment"))
    add(failures, odds_budget.get("observation_only") is True, "odds_budget_observation_only_unexpected", odds_budget.get("observation_only"))
    add(failures, odds_budget.get("betting_recommendation") is False, "odds_budget_betting_recommendation_unexpected", odds_budget.get("betting_recommendation"))
    add(failures, odds_budget.get("affects_v4") is False, "odds_budget_affects_v4_unexpected", odds_budget.get("affects_v4"))

    for key, expected in EXPECTED_SAFETY.items():
        add(failures, master.get("global_safety", {}).get(key) is expected, f"global_safety_{key}_unexpected", master.get("global_safety", {}).get(key))
    for item in modules:
        if not isinstance(item, dict):
            failures.append("module_entry_not_dict")
            continue
        add(failures, item.get("observation_only") is True, "module_observation_only_unexpected", item.get("module_name"))
        add(failures, item.get("betting_recommendation") is False, "module_betting_recommendation_true", item.get("module_name"))
        add(failures, item.get("affects_v4") is False, "module_affects_v4_true", item.get("module_name"))

    add(failures, gap.get("missing_starting_xi") is True, "gap_missing_starting_xi_unexpected", gap.get("missing_starting_xi"))
    add(failures, (gap.get("coverage_104") or {}).get("card_count") == 104, "gap_coverage_104_count_unexpected", gap.get("coverage_104"))
    add(failures, (gap.get("group_72") or {}).get("card_count") == 72, "gap_group_72_count_unexpected", gap.get("group_72"))
    add(failures, (gap.get("knockout_32") or {}).get("card_count") == 32, "gap_knockout_32_count_unexpected", gap.get("knockout_32"))
    add(failures, isinstance(gap.get("coverage_gap_summary"), dict) and bool(gap.get("coverage_gap_summary")), "gap_coverage_gap_summary_missing", gap.get("coverage_gap_summary"))
    gap_odds_budget = gap.get("odds_polling_budget") if isinstance(gap.get("odds_polling_budget"), dict) else {}
    add(failures, gap_odds_budget.get("source") == "config/v3_worldcup_odds_polling_cadence.json", "gap_odds_budget_source_unexpected", gap_odds_budget.get("source"))
    add(failures, gap_odds_budget.get("default_target_requests_per_day") == 600, "gap_odds_budget_default_target_unexpected", gap_odds_budget.get("default_target_requests_per_day"))
    add(failures, gap_odds_budget.get("hard_stop_at_requests_per_day") == 6000, "gap_odds_budget_hard_stop_unexpected", gap_odds_budget.get("hard_stop_at_requests_per_day"))
    add(failures, gap_odds_budget.get("polling_windows") == EXPECTED_POLLING_WINDOWS, "gap_odds_budget_windows_unexpected", gap_odds_budget.get("polling_windows"))
    add(failures, gap_odds_budget.get("allowed_odds_observation_fields") == EXPECTED_ODDS_FIELDS, "gap_odds_budget_allowed_fields_unexpected", gap_odds_budget.get("allowed_odds_observation_fields"))
    for flag in [
        "missing_official_matchday_lineup",
        "missing_native_opening_odds",
        "missing_native_closing_odds",
        "missing_odds_movement_conclusion",
        "missing_injury_suspension_official_feed",
        "final_26_ready",
        "venue_stress_ready",
        "tactical_profile_ready",
    ]:
        add(failures, gap.get(flag) is True, f"gap_{flag}_unexpected", gap.get(flag))

    keys = {key.lower() for key in walk_keys({"master": master, "gap": gap})}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    combined_text = json.dumps({"master": master, "gap": gap}, ensure_ascii=False).lower()
    for phrase in DISALLOWED_PHRASES:
        add(failures, phrase not in combined_text, "disallowed_judgment_phrase", phrase)

    staged = staged_files()
    runtime_staged = [
        path for path in staged
        if path != APPROVED_DASHBOARD_UI_STAGE
        and re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)
    ]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    v4_staged = staged_v4_hits(staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    relevant_runtime_tracked = [path for path in tracked_runtime_hits() if "v3_worldcup/war_room" in path or "war_room_master_index" in path]
    add(failures, not relevant_runtime_tracked, "runtime_war_room_output_tracked", relevant_runtime_tracked)

    secret_files = [
        MASTER_INDEX,
        GAP_RADAR,
        ROOT / "tools/build_v3_worldcup_war_room_master_index.py",
        Path(__file__).resolve(),
        ROOT / "docs/V3_WC_WAR_ROOM_MASTER_INDEX_PACK_PHASE_1_20260604.md",
    ]
    secrets = secret_hits(secret_files)
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "module_count": master.get("module_count"),
        "registered_modules": sorted(names),
        "odds_available_fixture_count": gap.get("odds_available_fixture_count"),
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
