#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_fixture_mapping_bridge import BRIDGE, BRIDGE_SUMMARY, build

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_fixture_mapping_bridge_20260605.json"

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


def main() -> int:
    bridge, summary = build()
    BRIDGE.parent.mkdir(parents=True, exist_ok=True)
    BRIDGE.write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    BRIDGE_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[str] = []
    add(failures, BRIDGE.exists(), "bridge_missing", BRIDGE)
    add(failures, BRIDGE_SUMMARY.exists(), "bridge_summary_missing", BRIDGE_SUMMARY)
    add(failures, len(bridge) == 72, "bridge_count_unexpected", len(bridge))
    add(failures, summary.get("match_count") == 72, "summary_match_count_unexpected", summary.get("match_count"))
    add(failures, summary.get("bridge_count") == 72, "summary_bridge_count_unexpected", summary.get("bridge_count"))
    ids = [row.get("match_card_id") for row in bridge]
    add(failures, len(ids) == len(set(ids)), "duplicate_match_card_id", len(ids) - len(set(ids)))
    add(failures, duplicate_count([row.get("api_football_fixture_id") for row in bridge]) == 0, "duplicate_api_football_fixture_id")
    add(failures, duplicate_count([row.get("odds_fixture_id") for row in bridge]) == 0, "duplicate_odds_fixture_id")

    for row in bridge:
        match_id = row.get("match_card_id")
        add(failures, row.get("fixture_mapping_status") in {"MAPPED", "UNMAPPED"}, "fixture_mapping_status_missing", match_id)
        add(failures, row.get("venue_mapping_status") in {"MAPPED", "UNMAPPED"}, "venue_mapping_status_missing", match_id)
        if row.get("fixture_mapping_status") == "MAPPED":
            add(failures, bool(row.get("api_football_fixture_id")), "mapped_fixture_id_missing", match_id)
            add(failures, bool(row.get("fixture_source")), "mapped_fixture_source_missing", match_id)
            add(failures, row.get("fixture_mapping_confidence") not in {"", None, "NONE"}, "mapped_fixture_confidence_missing", match_id)
        else:
            add(failures, bool(row.get("mapping_gap_reason")), "unmapped_fixture_gap_reason_missing", match_id)
        if row.get("venue_mapping_status") == "MAPPED":
            add(failures, row.get("venue_name") != "VENUE_NOT_MAPPED", "mapped_venue_name_missing", match_id)
            add(failures, bool(row.get("venue_source")), "mapped_venue_source_missing", match_id)
            add(failures, row.get("venue_mapping_confidence") not in {"", None, "NONE"}, "mapped_venue_confidence_missing", match_id)
        else:
            add(failures, bool(row.get("mapping_gap_reason")), "unmapped_venue_gap_reason_missing", match_id)
        add(failures, row.get("observation_only") is True, "observation_only_unexpected", match_id)
        add(failures, row.get("no_prediction") is True, "no_prediction_unexpected", match_id)
        add(failures, row.get("betting_recommendation") is False, "betting_recommendation_true", match_id)
        add(failures, row.get("affects_v4") is False, "affects_v4_true", match_id)

    add(failures, summary.get("fixture_id_mapped_count") == 72, "fixture_id_mapped_count_unexpected", summary.get("fixture_id_mapped_count"))
    add(failures, summary.get("odds_fixture_id_mapped_count") == 72, "odds_fixture_id_mapped_count_unexpected", summary.get("odds_fixture_id_mapped_count"))
    add(failures, summary.get("venue_mapped_count") == 0, "venue_mapped_count_unexpected", summary.get("venue_mapped_count"))
    add(failures, summary.get("conflict_count") == 0, "conflict_count_unexpected", summary.get("conflict_count"))
    add(failures, summary.get("duplicate_fixture_id_count") == 0, "duplicate_fixture_id_count_unexpected", summary.get("duplicate_fixture_id_count"))
    add(failures, summary.get("safety", {}).get("observation_only") is True, "summary_observation_only_unexpected")
    add(failures, summary.get("safety", {}).get("no_prediction") is True, "summary_no_prediction_unexpected")
    add(failures, summary.get("safety", {}).get("betting_recommendation") is False, "summary_betting_recommendation_true")
    add(failures, summary.get("safety", {}).get("affects_v4") is False, "summary_affects_v4_true")

    keys = {key.lower() for key in walk_keys({"bridge": bridge, "summary": summary})}
    add(failures, not (keys & DISALLOWED_KEYS), "disallowed_generated_keys", sorted(keys & DISALLOWED_KEYS))
    combined = json.dumps({"bridge": bridge, "summary": summary}, ensure_ascii=False).lower()
    for phrase in DISALLOWED_PHRASES:
        add(failures, phrase not in combined, "disallowed_phrase", phrase)

    staged = staged_files()
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    secrets = secret_hits([
        BRIDGE,
        BRIDGE_SUMMARY,
        ROOT / "tools/build_v3_worldcup_fixture_mapping_bridge.py",
        Path(__file__).resolve(),
        ROOT / "docs/V3_WC_MATCH_CARD_PACK_PHASE_3_FIXTURE_MAPPING_BRIDGE_20260604.md",
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "bridge_count": len(bridge),
        "fixture_id_mapped_count": summary.get("fixture_id_mapped_count"),
        "odds_fixture_id_mapped_count": summary.get("odds_fixture_id_mapped_count"),
        "venue_mapped_count": summary.get("venue_mapped_count"),
        "fixture_unmapped_count": summary.get("fixture_unmapped_count"),
        "venue_unmapped_count": summary.get("venue_unmapped_count"),
        "conflict_count": summary.get("conflict_count"),
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
