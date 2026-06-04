#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_104_coverage_gap_radar import COVERAGE_RADAR, COVERAGE_SUMMARY, build

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_104_coverage_gap_radar_20260605.json"
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
    radar, summary = build()
    COVERAGE_RADAR.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE_RADAR.write_text(json.dumps(radar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    COVERAGE_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    add(failures, COVERAGE_RADAR.exists(), "coverage_radar_missing", COVERAGE_RADAR)
    add(failures, COVERAGE_SUMMARY.exists(), "coverage_summary_missing", COVERAGE_SUMMARY)
    add(failures, len(radar) == 104, "coverage_card_count_unexpected", len(radar))

    group = [row for row in radar if row.get("scope_bucket") == "GROUP_72"]
    knockout = [row for row in radar if row.get("scope_bucket") == "KNOCKOUT_32"]
    add(failures, len(group) == 72, "group_72_count_unexpected", len(group))
    add(failures, len(knockout) == 32, "knockout_32_count_unexpected", len(knockout))
    add(failures, summary.get("coverage_104", {}).get("card_count") == 104, "summary_104_count_unexpected", summary.get("coverage_104"))
    add(failures, summary.get("group_72", {}).get("card_count") == 72, "summary_group_count_unexpected", summary.get("group_72"))
    add(failures, summary.get("knockout_32", {}).get("card_count") == 32, "summary_knockout_count_unexpected", summary.get("knockout_32"))

    add(failures, summary.get("group_72", {}).get("team_known_count") == 72, "group_team_known_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("fixture_id_mapped_count") == 72, "group_fixture_id_mapped_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("odds_fixture_id_mapped_count") == 72, "group_odds_fixture_id_mapped_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("final26_ready_card_count") == 72, "group_final26_ready_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("final26_gap_card_count") == 0, "group_final26_gap_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("lineup_wait_official_count") == 72, "group_lineup_wait_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("lineup_gap_card_count") == 0, "group_lineup_gap_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("venue_source_required_count") == 72, "group_venue_gap_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("war_room_registered_count") == 72, "group_war_room_count_unexpected", summary.get("group_72"))
    add(failures, summary.get("group_72", {}).get("dashboard_registered_count") == 72, "group_dashboard_count_unexpected", summary.get("group_72"))

    add(failures, summary.get("knockout_32", {}).get("structural_placeholder_count") == 32, "knockout_placeholder_count_unexpected", summary.get("knockout_32"))
    for key in ["team_generated_count", "fixture_id_generated_count", "odds_fixture_id_generated_count", "venue_generated_count"]:
        add(failures, summary.get("knockout_32", {}).get(key) == 0, f"knockout_{key}_unexpected", summary.get("knockout_32"))
    add(failures, summary.get("knockout_32", {}).get("war_room_registered_count") == 32, "knockout_war_room_count_unexpected", summary.get("knockout_32"))
    add(failures, summary.get("knockout_32", {}).get("dashboard_registered_count") == 32, "knockout_dashboard_count_unexpected", summary.get("knockout_32"))

    alias_rows = [row for row in group if row.get("team_slug_alias_applied") is True]
    add(failures, len(alias_rows) == 3, "team_slug_alias_applied_count_unexpected", len(alias_rows))
    add(failures, all(row.get("away_canonical_team_slug") == "cote_d_ivoire" or row.get("home_canonical_team_slug") == "cote_d_ivoire" for row in alias_rows), "team_slug_alias_target_unexpected", alias_rows)

    for row in group:
        cid = row.get("canonical_card_id")
        add(failures, row.get("team_coverage_status") == "KNOWN_FROM_GROUP_STAGE_SOURCE", "group_team_status_unexpected", cid)
        add(failures, row.get("venue_coverage_status") in {"UNMAPPED", "VENUE_SOURCE_REQUIRED"}, "group_venue_status_unexpected", cid)
        add(failures, row.get("fixture_id_coverage_status") == "MAPPED", "group_fixture_status_unexpected", cid)
        add(failures, row.get("odds_fixture_id_coverage_status") == "MAPPED", "group_odds_status_unexpected", cid)
        add(failures, row.get("final26_coverage_status") == "READY", "group_final26_status_unexpected", cid)
        add(failures, row.get("lineup_coverage_status") == "WAIT_OFFICIAL_LINEUP", "group_lineup_status_unexpected", cid)
        add(failures, "FINAL26_TEAM_GAP" not in row.get("gap_reasons", []), "group_final26_gap_reason_present", cid)
        add(failures, "LINEUP_STATUS_GAP" not in row.get("gap_reasons", []), "group_lineup_gap_reason_present", cid)
        add(failures, row.get("structural_placeholder") is False, "group_structural_placeholder_true", cid)
    for row in knockout:
        cid = row.get("canonical_card_id")
        add(failures, row.get("structural_placeholder") is True, "knockout_structural_placeholder_false", cid)
        add(failures, row.get("home_team") is None and row.get("away_team") is None, "knockout_team_generated", cid)
        add(failures, row.get("team_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_team_status_unexpected", cid)
        add(failures, row.get("fixture_id_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_fixture_status_unexpected", cid)
        add(failures, row.get("odds_fixture_id_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_odds_status_unexpected", cid)
        add(failures, row.get("venue_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_venue_status_unexpected", cid)
        add(failures, row.get("final26_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_final26_status_unexpected", cid)
        add(failures, row.get("lineup_coverage_status") == "STRUCTURAL_PLACEHOLDER", "knockout_lineup_status_unexpected", cid)

    for row in radar:
        cid = row.get("canonical_card_id")
        add(failures, row.get("observation_only") is True, "observation_only_unexpected", cid)
        add(failures, row.get("no_starting_xi_generated") is True, "no_starting_xi_generated_unexpected", cid)
        add(failures, row.get("no_prediction") is True, "no_prediction_unexpected", cid)
        add(failures, row.get("no_injury_judgment") is True, "no_injury_judgment_unexpected", cid)
        add(failures, row.get("betting_recommendation") is False, "betting_recommendation_true", cid)
        add(failures, row.get("affects_v4") is False, "affects_v4_true", cid)

    keys = {key.lower() for key in walk_keys({"radar": radar, "summary": summary})}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    combined = json.dumps({"radar": radar, "summary": summary}, ensure_ascii=False).lower()
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
    relevant_runtime = [path for path in tracked_runtime_hits() if "coverage_gap_radar" in path]
    add(failures, not relevant_runtime, "runtime_coverage_gap_radar_tracked", relevant_runtime)
    secrets = secret_hits([COVERAGE_RADAR, COVERAGE_SUMMARY, ROOT / "tools/build_v3_worldcup_104_coverage_gap_radar.py", Path(__file__).resolve()])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "coverage_104": summary.get("coverage_104"),
        "group_72": summary.get("group_72"),
        "knockout_32": summary.get("knockout_32"),
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
