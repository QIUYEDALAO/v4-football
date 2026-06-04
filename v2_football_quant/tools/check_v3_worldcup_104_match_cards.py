#!/usr/bin/env python3
"""
V3 WC 2026 — 104 Full Tournament Match Card Checker
====================================================
Validates that the Wikipedia-sourced 104 card pack meets all requirements:
  - 104 total cards
  - 72 group stage
  - 32 knockout stage
  - match_id wc_001-wc_104 unique
  - no OBSERVATION/PREDICTION/BETTING_ONLY safety fields preserved
  - venue missing only marked PARSE_REQUIRED (never guessed)
  - no betting output
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATCH_CARDS = ROOT / "data/manual_sources/v3_worldcup/war_room/v3_wc_match_cards.json"
MATCH_SUMMARY = ROOT / "data/manual_sources/v3_worldcup/war_room/v3_wc_match_card_summary.json"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_104_match_cards_20260605.json"

EXPECTED_TOTAL = 104
EXPECTED_GROUP = 72
EXPECTED_KO = 32
EXPECTED_MATCH_IDS = set(range(1, 105))
EXPECTED_GROUPS = {f"Group {l}" for l in "ABCDEFGHIJKL"}
EXPECTED_KO_ROUNDS = {"round_of_32", "round_of_16", "quarter_finals", "semi_finals", "third_place", "final"}

SAFETY_FIELDS = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}

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


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


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


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    failures: list[str] = []

    # Load
    cards_raw = MATCH_CARDS.read_text(encoding="utf-8") if MATCH_CARDS.exists() else ""
    summary_raw = MATCH_SUMMARY.read_text(encoding="utf-8") if MATCH_SUMMARY.exists() else ""
    cards: list[dict[str, Any]] = json.loads(cards_raw) if cards_raw else []
    summary: dict[str, Any] = json.loads(summary_raw) if summary_raw else {}

    # === 1. File existence ===
    add(failures, MATCH_CARDS.exists(), "file_match_cards_missing")
    add(failures, MATCH_SUMMARY.exists(), "file_summary_missing")

    # === 2. Total count ===
    total = len(cards)
    add(failures, total == EXPECTED_TOTAL, f"total_count_not_{EXPECTED_TOTAL}", total)

    # === 3. Group vs KO counts ===
    group_count = sum(1 for c in cards if str(c.get("round_label", "")).startswith("Group "))
    ko_count = total - group_count
    add(failures, group_count == EXPECTED_GROUP, f"group_count_not_{EXPECTED_GROUP}", group_count)
    add(failures, ko_count == EXPECTED_KO, f"ko_count_not_{EXPECTED_KO}", ko_count)

    # === 4. Match ID 1-104 unique & contiguous ===
    wiki_mids = {}
    mids_set = set()
    for i, c in enumerate(cards):
        mid = c.get("wiki_match_number") or c.get("match_id", f"pos_{i}")
        if mid in wiki_mids:
            failures.append(f"duplicate_match_id:{mid}")
        wiki_mids[mid] = i
        mids_set.add(mid if isinstance(mid, int) else None)

    integer_mids = {m for m in mids_set if isinstance(m, int)}
    add(failures, len(integer_mids) == EXPECTED_TOTAL, f"unique_match_ids_not_{EXPECTED_TOTAL}", len(integer_mids))
    gaps = sorted(EXPECTED_MATCH_IDS - integer_mids)
    add(failures, not gaps, "match_id_gaps", gaps)
    if integer_mids:
        add(failures, min(integer_mids) == 1, "match_id_min_not_1", min(integer_mids))
        add(failures, max(integer_mids) == 104, "match_id_max_not_104", max(integer_mids))

    # === 5. Stage breakdown ===
    stage_counts = {}
    for c in cards:
        label = c.get("round_label", "UNKNOWN")
        stage_counts[label] = stage_counts.get(label, 0) + 1

    # Groups
    groups_found = {k for k in stage_counts if k.startswith("Group ")}
    missing_groups = EXPECTED_GROUPS - groups_found
    add(failures, not missing_groups, "missing_groups", sorted(missing_groups))
    for g in EXPECTED_GROUPS:
        add(failures, stage_counts.get(g, 0) == 6, f"group_{g}_count_not_6", stage_counts.get(g, 0))

    # KO rounds
    ko_found = {k for k in stage_counts if not k.startswith("Group ")}
    missing_ko = EXPECTED_KO_ROUNDS - ko_found
    add(failures, not missing_ko, "missing_ko_rounds", sorted(missing_ko))
    expected_ko_counts = {"round_of_32": 16, "round_of_16": 8, "quarter_finals": 4,
                          "semi_finals": 2, "third_place": 1, "final": 1}
    for label, expected in expected_ko_counts.items():
        add(failures, stage_counts.get(label, 0) == expected, f"ko_{label}_count_not_{expected}", stage_counts.get(label, 0))

    # === 6. Field completeness ===
    for i, c in enumerate(cards):
        mid_display = c.get("wiki_match_number", c.get("match_id", f"idx_{i}"))

        # Required fields
        for fld in ["home_team", "away_team", "home_team_slug", "away_team_slug",
                     "round_label", "venue", "kickoff_status"]:
            add(failures, bool(c.get(fld)), f"card_{fld}_missing", f"{mid_display}")

        # Venue not guessed
        venue = c.get("venue", "")
        add(failures, venue != "VENUE_NOT_MAPPED", f"venue_guessed", f"{mid_display}={venue}")

        # No placeholder teams
        home = c.get("home_team", "")
        away = c.get("away_team", "")
        for side, team in [("home", home), ("away", away)]:
            if "PLACEHOLDER" in team:
                failures.append(f"team_placeholder:{mid_display}_{side}={team}")

    # === 7. Safety fields ===
    for i, c in enumerate(cards):
        mid_display = c.get("wiki_match_number", c.get("match_id", f"idx_{i}"))
        for key, expected_val in SAFETY_FIELDS.items():
            actual = c.get(key)
            if actual is None:
                failures.append(f"safety_{key}_missing:{mid_display}")
            elif actual != expected_val:
                failures.append(f"safety_{key}_wrong:{mid_display}={actual}")

    # === 8. No disallowed keys ===
    all_keys = set(walk_keys(cards))
    disallowed_found = all_keys & DISALLOWED_KEYS
    add(failures, not disallowed_found, "disallowed_keys_found", sorted(disallowed_found))

    # === 9. Venue missing count ===
    venue_missing = [c.get("wiki_match_number") for c in cards if c.get("venue") == "PARSE_REQUIRED"]
    venue_missing_count = len(venue_missing)
    add(failures, venue_missing_count == 7, "venue_missing_count_not_7", venue_missing_count)
    # These specific matches are known to be missing venue
    expected_venue_missing = {6, 27, 40, 51, 64, 85, 96}
    actual_venue_missing = set(venue_missing)
    add(failures, actual_venue_missing == expected_venue_missing,
        "venue_missing_ids_mismatch", f"got={sorted(actual_venue_missing)}_expected={sorted(expected_venue_missing)}")

    # === 10. Summary validation ===
    add(failures, summary.get("match_count") == total, "summary_match_count_mismatch", summary.get("match_count"))
    add(failures, summary.get("group_match_count") == group_count, "summary_group_count_mismatch", summary.get("group_match_count"))
    add(failures, summary.get("knockout_match_count") == ko_count, "summary_ko_count_mismatch", summary.get("knockout_match_count"))
    add(failures, summary.get("expected_total") == EXPECTED_TOTAL, "summary_expected_total_mismatch")
    add(failures, summary.get("expected_group") == EXPECTED_GROUP, "summary_expected_group_mismatch")
    add(failures, summary.get("expected_knockout") == EXPECTED_KO, "summary_expected_ko_mismatch")
    add(failures, not summary.get("match_id_gaps"), "summary_match_id_gaps", summary.get("match_id_gaps"))
    add(failures, summary.get("venue_missing_count") == venue_missing_count, "summary_venue_missing_count_mismatch")

    # === 11. No runtime/v4 staged ===
    staged = staged_files()
    runtime_staged = [
        path for path in staged
        if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)
    ]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)

    # === OUTPUT ===
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "scope": "FULL_TOURNAMENT_104",
        "match_count": total,
        "group_match_count": group_count,
        "knockout_match_count": ko_count,
        "venue_missing_count": venue_missing_count,
        "venue_missing_match_ids": sorted(venue_missing),
        "stage_breakdown": stage_counts,
        "safety": SAFETY_FIELDS,
    }

    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
