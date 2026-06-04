#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_104_cards_index_bridge import (
    CARDS_INDEX_BRIDGE_104,
    CARDS_INDEX_SUMMARY_104,
    GROUP_CARDS,
    GROUP_STAGE_COUNT,
    KNOCKOUT_SLOT_COUNT,
    SCHEDULE_INDEX_104,
    TOTAL_EXPECTED_COUNT,
    build,
)

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_104_cards_index_bridge_20260605.json"

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
    schedule_index, rows, summary = build()
    SCHEDULE_INDEX_104.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_INDEX_104.write_text(json.dumps(schedule_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CARDS_INDEX_BRIDGE_104.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CARDS_INDEX_SUMMARY_104.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    add(failures, SCHEDULE_INDEX_104.exists(), "schedule_index_104_missing", SCHEDULE_INDEX_104)
    add(failures, CARDS_INDEX_BRIDGE_104.exists(), "cards_index_104_missing", CARDS_INDEX_BRIDGE_104)
    add(failures, CARDS_INDEX_SUMMARY_104.exists(), "cards_index_104_summary_missing", CARDS_INDEX_SUMMARY_104)
    add(failures, len(rows) == TOTAL_EXPECTED_COUNT, "canonical_card_count_unexpected", len(rows))
    add(failures, summary.get("canonical_card_count") == TOTAL_EXPECTED_COUNT, "summary_canonical_count_unexpected", summary.get("canonical_card_count"))
    add(failures, summary.get("group_stage_match_count") == GROUP_STAGE_COUNT, "summary_group_stage_count_unexpected", summary.get("group_stage_match_count"))
    add(failures, summary.get("knockout_slot_count") == KNOCKOUT_SLOT_COUNT, "summary_knockout_slot_count_unexpected", summary.get("knockout_slot_count"))
    add(failures, schedule_index.get("canonical_source") == str(CARDS_INDEX_BRIDGE_104.relative_to(ROOT)), "canonical_source_unexpected", schedule_index.get("canonical_source"))
    add(failures, schedule_index.get("full_tournament_canonical_source") is True, "canonical_source_not_marked_full_tournament")
    add(failures, schedule_index.get("group_stage_view") == str(GROUP_CARDS.relative_to(ROOT)), "group_stage_view_unexpected", schedule_index.get("group_stage_view"))
    add(failures, schedule_index.get("group_stage_view_scope") == "GROUP_STAGE_ONLY_72", "group_stage_scope_unexpected", schedule_index.get("group_stage_view_scope"))
    read_policy = schedule_index.get("dashboard_index_read_policy") if isinstance(schedule_index.get("dashboard_index_read_policy"), dict) else {}
    add(failures, read_policy.get("do_not_merge_canonical_and_group_view") is True, "double_read_guard_missing", read_policy)
    add(failures, read_policy.get("group_view_is_subset_of_canonical") is True, "group_view_subset_missing", read_policy)

    ids = [str(item.get("canonical_card_id")) for item in rows if isinstance(item, dict)]
    add(failures, len(ids) == len(set(ids)), "duplicate_canonical_card_id", len(ids) - len(set(ids)))
    group_rows = [item for item in rows if item.get("card_kind") == "GROUP_STAGE_MATCH"]
    knockout_rows = [item for item in rows if item.get("card_kind") == "KNOCKOUT_SLOT"]
    add(failures, len(group_rows) == GROUP_STAGE_COUNT, "group_row_count_unexpected", len(group_rows))
    add(failures, len(knockout_rows) == KNOCKOUT_SLOT_COUNT, "knockout_row_count_unexpected", len(knockout_rows))
    for item in group_rows:
        add(failures, bool(item.get("source_card_ref")), "group_source_card_ref_missing", item.get("canonical_card_id"))
        add(failures, bool(item.get("home_team")) and bool(item.get("away_team")), "group_team_missing", item.get("canonical_card_id"))
        add(failures, item.get("knockout_team_generated") is False, "group_knockout_team_generated_true", item.get("canonical_card_id"))
    for item in knockout_rows:
        cid = item.get("canonical_card_id")
        add(failures, item.get("home_team") is None and item.get("away_team") is None, "knockout_team_generated", cid)
        add(failures, item.get("home_team_slug") is None and item.get("away_team_slug") is None, "knockout_team_slug_generated", cid)
        add(failures, item.get("api_football_fixture_id") is None, "knockout_fixture_id_generated", cid)
        add(failures, item.get("odds_fixture_id") is None, "knockout_odds_fixture_id_generated", cid)
        add(failures, item.get("team_source_status") == "WAIT_QUALIFICATION_NO_TEAM_GENERATED", "knockout_team_status_unexpected", cid)
        add(failures, item.get("venue_generated") is False, "knockout_venue_generated_true", cid)
        add(failures, item.get("knockout_team_generated") is False, "knockout_team_generated_true", cid)

    for item in rows:
        cid = item.get("canonical_card_id")
        add(failures, item.get("observation_only") is True, "observation_only_unexpected", cid)
        add(failures, item.get("no_starting_xi_generated") is True, "no_starting_xi_generated_unexpected", cid)
        add(failures, item.get("no_prediction") is True, "no_prediction_unexpected", cid)
        add(failures, item.get("no_injury_judgment") is True, "no_injury_judgment_unexpected", cid)
        add(failures, item.get("betting_recommendation") is False, "betting_recommendation_true", cid)
        add(failures, item.get("affects_v4") is False, "affects_v4_true", cid)

    keys = {key.lower() for key in walk_keys({"schedule_index": schedule_index, "rows": rows, "summary": summary})}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    combined = json.dumps({"schedule_index": schedule_index, "rows": rows, "summary": summary}, ensure_ascii=False).lower()
    for phrase in DISALLOWED_PHRASES:
        add(failures, phrase not in combined, "disallowed_phrase", phrase)

    staged = staged_files()
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    relevant_runtime = [path for path in tracked_runtime_hits() if "104_cards" in path or "schedule_index_104" in path]
    add(failures, not relevant_runtime, "runtime_104_index_output_tracked", relevant_runtime)
    secrets = secret_hits([
        SCHEDULE_INDEX_104,
        CARDS_INDEX_BRIDGE_104,
        CARDS_INDEX_SUMMARY_104,
        ROOT / "tools/build_v3_worldcup_104_cards_index_bridge.py",
        Path(__file__).resolve(),
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "canonical_source": str(CARDS_INDEX_BRIDGE_104.relative_to(ROOT)),
        "canonical_card_count": len(rows),
        "group_stage_match_count": len(group_rows),
        "knockout_slot_count": len(knockout_rows),
        "full_tournament_canonical_source": schedule_index.get("full_tournament_canonical_source"),
        "full_tournament_match_data_complete": schedule_index.get("full_tournament_match_data_complete"),
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
