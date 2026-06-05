#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_fixture_mapping_bridge_20260605.json"
WAR_ROOM = ROOT / "data/manual_sources/v3_worldcup/war_room"
CANONICAL_104 = WAR_ROOM / "v3_wc2026_104_cards_index_bridge.json"
CANONICAL_104_SUMMARY = WAR_ROOM / "v3_wc2026_104_cards_index_bridge_summary.json"
GROUP_STAGE_VIEW = WAR_ROOM / "v3_wc_match_cards.json"
LEGACY_FIXTURE_BRIDGE = WAR_ROOM / "v3_wc2026_fixture_mapping_bridge.json"
LEGACY_FIXTURE_BRIDGE_SUMMARY = WAR_ROOM / "v3_wc2026_fixture_mapping_bridge_summary.json"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
DISALLOWED_KEYS = {
    "starting_xi_players",
    "predicted_xi",
    "injury_status",
    "suspension_status",
    "recommended_pick",
    "betting_signal",
    "fund_flow_signal",
    "steam_signal",
    "drift_signal",
    "sharp_signal",
}
DISALLOWED_PHRASES = [
    "fund flow",
    "steam",
    "drift",
    "sharp move",
    "starting xi generated",
    "predicted xi",
    "injury judgment",
]


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = git(["diff", "--cached", "--name-only"])
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


def duplicate_count(values: list[Any]) -> int:
    real = [str(value) for value in values if value not in {None, ""}]
    return len(real) - len(set(real))


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [] if path.suffix == ".json" else {}


def main() -> int:
    canonical = load_json(CANONICAL_104)
    canonical_summary = load_json(CANONICAL_104_SUMMARY)
    group_view = load_json(GROUP_STAGE_VIEW)
    legacy_bridge = load_json(LEGACY_FIXTURE_BRIDGE)
    legacy_summary = load_json(LEGACY_FIXTURE_BRIDGE_SUMMARY)
    canonical_rows = canonical if isinstance(canonical, list) else []
    group_view_rows = group_view if isinstance(group_view, list) else []
    legacy_rows = legacy_bridge if isinstance(legacy_bridge, list) else []
    group_rows = [row for row in canonical_rows if isinstance(row, dict) and row.get("card_kind") == "GROUP_STAGE_MATCH"]
    knockout_rows = [row for row in canonical_rows if isinstance(row, dict) and row.get("card_kind") == "KNOCKOUT_SLOT"]
    old_group_view_rows = [row for row in group_view_rows if isinstance(row, dict) and row.get("group") != "KNOCKOUT"]

    failures: list[str] = []
    add(failures, CANONICAL_104.exists(), "canonical_104_missing", CANONICAL_104)
    add(failures, CANONICAL_104_SUMMARY.exists(), "canonical_104_summary_missing", CANONICAL_104_SUMMARY)
    add(failures, GROUP_STAGE_VIEW.exists(), "group_stage_view_missing", GROUP_STAGE_VIEW)
    add(failures, LEGACY_FIXTURE_BRIDGE.exists(), "legacy_fixture_bridge_missing", LEGACY_FIXTURE_BRIDGE)
    add(failures, LEGACY_FIXTURE_BRIDGE_SUMMARY.exists(), "legacy_fixture_bridge_summary_missing", LEGACY_FIXTURE_BRIDGE_SUMMARY)

    add(failures, len(canonical_rows) == 104, "canonical_total_unexpected", len(canonical_rows))
    add(failures, len(group_rows) == 72, "group_stage_total_unexpected", len(group_rows))
    add(failures, len(knockout_rows) == 32, "knockout_total_unexpected", len(knockout_rows))
    add(failures, len(old_group_view_rows) == 72, "old_group_stage_view_total_unexpected", len(old_group_view_rows))
    add(failures, len(legacy_rows) in {72, 104}, "legacy_bridge_count_unexpected", len(legacy_rows))

    add(failures, canonical_summary.get("canonical_card_count") == 104, "summary_canonical_count_unexpected", canonical_summary.get("canonical_card_count"))
    add(failures, canonical_summary.get("group_stage_match_count") == 72, "summary_group_count_unexpected", canonical_summary.get("group_stage_match_count"))
    add(failures, canonical_summary.get("knockout_slot_count") == 32, "summary_knockout_count_unexpected", canonical_summary.get("knockout_slot_count"))
    add(failures, canonical_summary.get("full_tournament_canonical_source") is True, "summary_canonical_source_flag_unexpected", canonical_summary.get("full_tournament_canonical_source"))
    add(failures, canonical_summary.get("group_stage_view_preserved") is True, "summary_group_view_preserved_unexpected", canonical_summary.get("group_stage_view_preserved"))

    ids = [row.get("canonical_card_id") for row in canonical_rows]
    add(failures, len(ids) == len(set(ids)), "duplicate_match_card_id", len(ids) - len(set(ids)))
    add(failures, duplicate_count([row.get("api_football_fixture_id") for row in group_rows]) == 0, "duplicate_group_api_football_fixture_id")
    add(failures, duplicate_count([row.get("odds_fixture_id") for row in group_rows]) == 0, "duplicate_group_odds_fixture_id")

    group_fixture_mapped = sum(1 for row in group_rows if row.get("api_football_fixture_id"))
    group_odds_mapped = sum(1 for row in group_rows if row.get("odds_fixture_id"))
    add(failures, group_fixture_mapped == 72, "group_fixture_id_mapped_unexpected", group_fixture_mapped)
    add(failures, group_odds_mapped == 72, "group_odds_fixture_id_mapped_unexpected", group_odds_mapped)

    for row in group_rows:
        match_id = row.get("canonical_card_id")
        add(failures, row.get("card_scope") == "FULL_TOURNAMENT_CANONICAL", "group_card_scope_unexpected", match_id)
        add(failures, row.get("source_view") == "GROUP_STAGE_VIEW_72", "group_source_view_unexpected", match_id)
        add(failures, row.get("team_source_status") == "KNOWN_FROM_GROUP_STAGE_SOURCE", "group_team_source_status_unexpected", match_id)
        add(failures, row.get("schedule_source_status") == "LOCAL_GROUP_STAGE_SOURCE", "group_schedule_source_status_unexpected", match_id)
        add(failures, bool(row.get("api_football_fixture_id")), "group_fixture_id_missing", match_id)
        add(failures, bool(row.get("odds_fixture_id")), "group_odds_fixture_id_missing", match_id)
        add(failures, row.get("knockout_team_generated") is False, "group_knockout_team_generated_true", match_id)
        add(failures, row.get("venue_mapping_status") == "MAPPED", "group_venue_mapping_status_unexpected", match_id)
        add(failures, row.get("observation_only") is True, "observation_only_unexpected", match_id)
        add(failures, row.get("no_prediction") is True, "no_prediction_unexpected", match_id)
        add(failures, row.get("betting_recommendation") is False, "betting_recommendation_true", match_id)
        add(failures, row.get("affects_v4") is False, "affects_v4_true", match_id)

    for row in knockout_rows:
        match_id = row.get("canonical_card_id")
        add(failures, row.get("source_view") == "STRUCTURAL_TOURNAMENT_SLOT", "knockout_source_view_unexpected", match_id)
        add(failures, row.get("team_source_status") == "WAIT_QUALIFICATION_NO_TEAM_GENERATED", "knockout_team_source_status_unexpected", match_id)
        add(failures, row.get("schedule_source_status") == "STRUCTURAL_SLOT_ONLY_WAIT_OFFICIAL_FIXTURE", "knockout_schedule_source_status_unexpected", match_id)
        add(failures, row.get("home_team") is None and row.get("away_team") is None, "knockout_real_team_generated", match_id)
        add(failures, row.get("api_football_fixture_id") is None, "knockout_fixture_id_should_be_null", match_id)
        add(failures, row.get("odds_fixture_id") is None, "knockout_odds_fixture_id_should_be_null", match_id)
        add(failures, row.get("knockout_team_generated") is False, "knockout_team_generated_true", match_id)
        add(failures, row.get("venue_mapping_status") == "MAPPED", "knockout_venue_mapping_status_unexpected", match_id)
        add(failures, row.get("observation_only") is True, "knockout_observation_only_unexpected", match_id)
        add(failures, row.get("no_prediction") is True, "knockout_no_prediction_unexpected", match_id)
        add(failures, row.get("betting_recommendation") is False, "knockout_betting_recommendation_true", match_id)
        add(failures, row.get("affects_v4") is False, "knockout_affects_v4_true", match_id)

    safety = canonical_summary.get("safety", {}) if isinstance(canonical_summary.get("safety"), dict) else {}
    add(failures, safety.get("observation_only") is True, "summary_observation_only_unexpected")
    add(failures, safety.get("no_prediction") is True, "summary_no_prediction_unexpected")
    add(failures, safety.get("betting_recommendation") is False, "summary_betting_recommendation_true")
    add(failures, safety.get("affects_v4") is False, "summary_affects_v4_true")

    keys = {key.lower() for key in walk_keys({"canonical": canonical_rows, "summary": canonical_summary, "legacy_summary": legacy_summary})}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    combined = json.dumps({"canonical": canonical_rows, "summary": canonical_summary, "legacy_summary": legacy_summary}, ensure_ascii=False).lower()
    for phrase in DISALLOWED_PHRASES:
        add(failures, phrase not in combined, "disallowed_phrase", phrase)

    staged = staged_files()
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    secrets = secret_hits([
        CANONICAL_104,
        CANONICAL_104_SUMMARY,
        GROUP_STAGE_VIEW,
        LEGACY_FIXTURE_BRIDGE_SUMMARY,
        ROOT / "tools/build_v3_worldcup_fixture_mapping_bridge.py",
        Path(__file__).resolve(),
        ROOT / "docs/V3_WC_MATCH_CARD_PACK_PHASE_3_FIXTURE_MAPPING_BRIDGE_20260604.md",
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "canonical_total": len(canonical_rows),
        "group_stage_total": len(group_rows),
        "group_fixture_id_mapped_count": group_fixture_mapped,
        "group_odds_fixture_id_mapped_count": group_odds_mapped,
        "knockout_total": len(knockout_rows),
        "knockout_fixture_status": "STRUCTURAL_PLACEHOLDER",
        "knockout_odds_status": "STRUCTURAL_PLACEHOLDER",
        "legacy_group_stage_view_count": len(old_group_view_rows),
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
