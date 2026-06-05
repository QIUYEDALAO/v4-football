#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_dashboard_104_read_model import DASHBOARD_READ_MODEL, build

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_dashboard_104_read_model_20260605.json"
APPROVED_DASHBOARD_UI_STAGE = "v2_football_quant/data/runtime/dashboard/v3_worldcup_wc10_war_room.html"

CANONICAL_SOURCE = "data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_cards_index_bridge.json"
SCHEDULE_INDEX = "data/manual_sources/v3_worldcup/war_room/v3_wc2026_schedule_index_104.json"
GROUP_VIEW = "data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json"
COVERAGE_SUMMARY = "data/manual_sources/v3_worldcup/war_room/v3_wc2026_104_coverage_gap_radar_summary.json"
ODDS_POLLING_CADENCE = "config/v3_worldcup_odds_polling_cadence.json"
EXPECTED_POLLING_WINDOWS = ["T-24h", "T-6h", "T-2h", "T-90m", "T-60m", "T-30m"]
EXPECTED_ODDS_FIELDS = ["first_seen_odds", "last_pre_kickoff_odds", "odds_observation_delta"]

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
}
DISALLOWED_PHRASES = [
    "fund flow",
    "money flow conclusion",
    "steam conclusion",
    "drift conclusion",
    "sharp move",
    "starting xi generated",
    "predicted xi",
    "confirmed lineup",
]


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
    payload = build()
    DASHBOARD_READ_MODEL.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_READ_MODEL.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    add(failures, DASHBOARD_READ_MODEL.exists(), "dashboard_read_model_missing", DASHBOARD_READ_MODEL)
    add(failures, payload.get("canonical_source") == CANONICAL_SOURCE, "canonical_source_unexpected", payload.get("canonical_source"))
    add(failures, payload.get("canonical_schedule_index") == SCHEDULE_INDEX, "schedule_index_unexpected", payload.get("canonical_schedule_index"))
    add(failures, payload.get("canonical_scope") == "FULL_TOURNAMENT_104_INDEX", "canonical_scope_unexpected", payload.get("canonical_scope"))
    add(failures, payload.get("canonical_card_count") == 104, "canonical_card_count_unexpected", payload.get("canonical_card_count"))
    add(failures, payload.get("group_stage_match_count") == 72, "group_stage_match_count_unexpected", payload.get("group_stage_match_count"))
    add(failures, payload.get("knockout_slot_count") == 32, "knockout_slot_count_unexpected", payload.get("knockout_slot_count"))
    add(failures, payload.get("full_tournament_match_data_complete") is False, "full_tournament_complete_unexpected", payload.get("full_tournament_match_data_complete"))

    group_view = payload.get("group_stage_view") if isinstance(payload.get("group_stage_view"), dict) else {}
    add(failures, group_view.get("source") == CANONICAL_SOURCE, "group_view_source_unexpected", group_view.get("source"))
    add(failures, group_view.get("source_filter") == "card_kind=GROUP_STAGE_MATCH", "group_view_source_filter_unexpected", group_view.get("source_filter"))
    add(failures, group_view.get("legacy_match_cards_source") == GROUP_VIEW, "group_view_legacy_source_unexpected", group_view.get("legacy_match_cards_source"))
    add(failures, group_view.get("scope") == "GROUP_STAGE_ONLY_72", "group_view_scope_unexpected", group_view.get("scope"))
    add(failures, group_view.get("match_count") == 72, "group_view_match_count_unexpected", group_view.get("match_count"))
    add(failures, group_view.get("is_subset_of_canonical") is True, "group_view_subset_unexpected", group_view)
    add(failures, group_view.get("do_not_treat_as_complete_source") is True, "group_view_complete_source_guard_missing", group_view)

    knockout = payload.get("knockout_slots") if isinstance(payload.get("knockout_slots"), dict) else {}
    add(failures, knockout.get("count") == 32, "knockout_count_unexpected", knockout.get("count"))
    add(failures, knockout.get("policy") == "STRUCTURAL_ONLY_NO_TEAM_GENERATED", "knockout_policy_unexpected", knockout.get("policy"))
    add(failures, knockout.get("display_mode") == "STRUCTURAL_SLOT_PLACEHOLDER", "knockout_display_mode_unexpected", knockout.get("display_mode"))
    add(failures, knockout.get("team_fields_empty") is True, "knockout_team_fields_not_empty", knockout)
    add(failures, knockout.get("fixture_fields_empty") is True, "knockout_fixture_fields_not_empty", knockout)
    add(failures, knockout.get("venue_fields_bound_from_wikipedia_snapshot") is True, "knockout_venue_not_bound_from_wikipedia", knockout)
    add(failures, knockout.get("venue_source_provenance") == "wikipedia_snapshot", "knockout_venue_source_provenance_unexpected", knockout)

    read_policy = payload.get("read_policy") if isinstance(payload.get("read_policy"), dict) else {}
    add(failures, read_policy.get("dashboard_primary_reader") == CANONICAL_SOURCE, "dashboard_primary_reader_unexpected", read_policy)
    add(failures, read_policy.get("group_stage_view_reader") == GROUP_VIEW, "group_stage_view_reader_unexpected", read_policy)
    add(failures, read_policy.get("do_not_merge_canonical_and_group_view") is True, "double_read_guard_missing", read_policy)
    add(failures, read_policy.get("duplicate_read_guard") == "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE", "duplicate_read_guard_unexpected", read_policy)

    coverage = payload.get("coverage_gap_summary") if isinstance(payload.get("coverage_gap_summary"), dict) else {}
    add(failures, coverage.get("source") == COVERAGE_SUMMARY, "coverage_summary_source_unexpected", coverage.get("source"))
    add(failures, (coverage.get("coverage_104") or {}).get("card_count") == 104, "coverage_104_count_unexpected", coverage.get("coverage_104"))
    add(failures, (coverage.get("group_72") or {}).get("card_count") == 72, "coverage_group_72_count_unexpected", coverage.get("group_72"))
    add(failures, (coverage.get("knockout_32") or {}).get("card_count") == 32, "coverage_knockout_32_count_unexpected", coverage.get("knockout_32"))
    add(failures, (coverage.get("knockout_32") or {}).get("structural_placeholder_count") == 32, "coverage_knockout_placeholder_unexpected", coverage.get("knockout_32"))
    add(failures, isinstance(coverage.get("gaps"), dict) and bool(coverage.get("gaps")), "coverage_gaps_missing", coverage.get("gaps"))

    odds_budget = payload.get("odds_polling_budget") if isinstance(payload.get("odds_polling_budget"), dict) else {}
    add(failures, odds_budget.get("source") == ODDS_POLLING_CADENCE, "odds_budget_source_unexpected", odds_budget.get("source"))
    add(failures, odds_budget.get("api_provider") == "api-football", "odds_budget_provider_unexpected", odds_budget.get("api_provider"))
    add(failures, odds_budget.get("quota_budget_per_day") == 7500, "odds_budget_quota_unexpected", odds_budget.get("quota_budget_per_day"))
    add(failures, isinstance(odds_budget.get("system_max_daily_requests"), int) and odds_budget.get("system_max_daily_requests") <= 1500, "odds_budget_system_max_exceeds_1500", odds_budget.get("system_max_daily_requests"))
    add(failures, isinstance(odds_budget.get("default_target_requests_per_day"), int) and odds_budget.get("default_target_requests_per_day") <= 600, "odds_budget_default_target_exceeds_600", odds_budget.get("default_target_requests_per_day"))
    add(failures, isinstance(odds_budget.get("hard_stop_at_requests_per_day"), int) and odds_budget.get("hard_stop_at_requests_per_day") <= 6000, "odds_budget_hard_stop_exceeds_6000", odds_budget.get("hard_stop_at_requests_per_day"))
    add(failures, odds_budget.get("canonical_total") == 104, "odds_budget_canonical_total_unexpected", odds_budget.get("canonical_total"))
    add(failures, odds_budget.get("group_stage_total") == 72, "odds_budget_group_total_unexpected", odds_budget.get("group_stage_total"))
    add(failures, odds_budget.get("knockout_reserved_total") == 32, "odds_budget_knockout_total_unexpected", odds_budget.get("knockout_reserved_total"))
    add(failures, odds_budget.get("polling_windows") == EXPECTED_POLLING_WINDOWS, "odds_budget_windows_unexpected", odds_budget.get("polling_windows"))
    add(failures, odds_budget.get("group_stage_six_window_requests") == 432, "odds_budget_group_six_window_unexpected", odds_budget.get("group_stage_six_window_requests"))
    add(failures, odds_budget.get("knockout_reserved_six_window_requests") == 192, "odds_budget_knockout_six_window_unexpected", odds_budget.get("knockout_reserved_six_window_requests"))
    add(failures, odds_budget.get("full_104_six_window_requests") == 624, "odds_budget_full_104_six_window_unexpected", odds_budget.get("full_104_six_window_requests"))
    add(failures, odds_budget.get("requires_batching_or_window_thinning_to_meet_default_target") is True, "odds_budget_default_target_guard_missing", odds_budget)
    add(failures, odds_budget.get("allowed_odds_observation_fields") == EXPECTED_ODDS_FIELDS, "odds_budget_allowed_fields_unexpected", odds_budget.get("allowed_odds_observation_fields"))
    add(failures, odds_budget.get("has_native_opening") is False, "odds_budget_native_opening_unexpected", odds_budget.get("has_native_opening"))
    add(failures, odds_budget.get("has_native_closing") is False, "odds_budget_native_closing_unexpected", odds_budget.get("has_native_closing"))
    add(failures, odds_budget.get("movement_requires_timeline") is True, "odds_budget_timeline_required_unexpected", odds_budget.get("movement_requires_timeline"))
    add(failures, odds_budget.get("no_money_flow_judgment") is True, "odds_budget_money_flow_guard_missing", odds_budget.get("no_money_flow_judgment"))
    add(failures, odds_budget.get("observation_only") is True, "odds_budget_observation_only_unexpected", odds_budget.get("observation_only"))
    add(failures, odds_budget.get("betting_recommendation") is False, "odds_budget_betting_recommendation_unexpected", odds_budget.get("betting_recommendation"))
    add(failures, odds_budget.get("affects_v4") is False, "odds_budget_affects_v4_unexpected", odds_budget.get("affects_v4"))

    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    for key, expected in {
        "observation_only": True,
        "no_starting_xi_generated": True,
        "no_prediction": True,
        "no_injury_judgment": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }.items():
        add(failures, safety.get(key) is expected, f"safety_{key}_unexpected", safety.get(key))

    keys = {key.lower() for key in walk_keys(payload)}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    combined = json.dumps(payload, ensure_ascii=False).lower()
    for phrase in DISALLOWED_PHRASES:
        add(failures, phrase not in combined, "disallowed_phrase", phrase)

    staged = staged_files()
    runtime_staged = [
        path for path in staged
        if path != APPROVED_DASHBOARD_UI_STAGE
        and re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)
    ]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    relevant_runtime = [path for path in tracked_runtime_hits() if "dashboard_104_read_model" in path]
    add(failures, not relevant_runtime, "runtime_dashboard_read_model_tracked", relevant_runtime)
    secrets = secret_hits([
        DASHBOARD_READ_MODEL,
        ROOT / "tools/build_v3_worldcup_dashboard_104_read_model.py",
        Path(__file__).resolve(),
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "dashboard_read_model": str(DASHBOARD_READ_MODEL.relative_to(ROOT)),
        "canonical_source": payload.get("canonical_source"),
        "canonical_card_count": payload.get("canonical_card_count"),
        "group_stage_match_count": payload.get("group_stage_match_count"),
        "knockout_slot_count": payload.get("knockout_slot_count"),
        "double_read_guard": read_policy.get("do_not_merge_canonical_and_group_view"),
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
