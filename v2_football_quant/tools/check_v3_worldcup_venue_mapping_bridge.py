#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_venue_mapping_bridge import MANUAL_TEMPLATE, VENUE_BRIDGE, VENUE_SUMMARY, build, write_template

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_venue_mapping_bridge_20260605.json"

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
    "starting xi generated",
    "predicted xi",
    "injury judgment",
    "fund flow",
    "steam",
    "drift",
    "sharp move",
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


def template_row_count() -> int:
    if not MANUAL_TEMPLATE.exists():
        return 0
    with MANUAL_TEMPLATE.open("r", encoding="utf-8", newline="") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def main() -> int:
    bridge, summary, template_rows = build()
    VENUE_BRIDGE.parent.mkdir(parents=True, exist_ok=True)
    VENUE_BRIDGE.write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VENUE_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_template(template_rows)

    failures: list[str] = []
    add(failures, VENUE_BRIDGE.exists(), "venue_bridge_missing", VENUE_BRIDGE)
    add(failures, VENUE_SUMMARY.exists(), "venue_summary_missing", VENUE_SUMMARY)
    add(failures, summary.get("match_count") == 72, "match_count_unexpected", summary.get("match_count"))
    add(failures, len(bridge) == 72, "bridge_count_unexpected", len(bridge))
    ids = [row.get("match_card_id") for row in bridge]
    add(failures, len(ids) == len(set(ids)), "duplicate_match_card_id", len(ids) - len(set(ids)))

    for row in bridge:
        match_id = row.get("match_card_id")
        add(failures, row.get("venue_mapping_status") in {"MAPPED", "UNMAPPED"}, "venue_mapping_status_missing", match_id)
        if row.get("venue_mapping_status") == "MAPPED":
            for key in ["venue_name", "venue_slug", "venue_source", "venue_mapping_confidence", "venue_stress_ref"]:
                add(failures, row.get(key) not in {"", None, "NONE"}, f"mapped_{key}_missing", match_id)
            add(failures, row.get("manual_mapping_required") is False, "mapped_manual_required_true", match_id)
        else:
            add(failures, bool(row.get("venue_gap_reason")), "unmapped_venue_gap_reason_missing", match_id)
            add(failures, row.get("manual_mapping_required") is True, "unmapped_manual_required_false", match_id)
        add(failures, row.get("observation_only") is True, "observation_only_unexpected", match_id)
        add(failures, row.get("no_prediction") is True, "no_prediction_unexpected", match_id)
        add(failures, row.get("betting_recommendation") is False, "betting_recommendation_true", match_id)
        add(failures, row.get("affects_v4") is False, "affects_v4_true", match_id)

    add(failures, summary.get("venue_source_found") is False, "venue_source_found_unexpected", summary.get("venue_source_found"))
    add(failures, summary.get("venue_mapped_count") == 0, "venue_mapped_count_unexpected", summary.get("venue_mapped_count"))
    add(failures, summary.get("venue_unmapped_count") == 72, "venue_unmapped_count_unexpected", summary.get("venue_unmapped_count"))
    add(failures, summary.get("manual_mapping_required_count") == 72, "manual_mapping_required_count_unexpected", summary.get("manual_mapping_required_count"))
    add(failures, summary.get("conflict_count") == 0, "conflict_count_unexpected", summary.get("conflict_count"))
    add(failures, summary.get("duplicate_mapping_count") == 0, "duplicate_mapping_count_unexpected", summary.get("duplicate_mapping_count"))
    add(failures, MANUAL_TEMPLATE.exists(), "manual_template_missing", MANUAL_TEMPLATE)
    add(failures, template_row_count() == 72, "manual_template_row_count_unexpected", template_row_count())
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
        VENUE_BRIDGE,
        VENUE_SUMMARY,
        MANUAL_TEMPLATE,
        ROOT / "tools/build_v3_worldcup_venue_mapping_bridge.py",
        Path(__file__).resolve(),
        ROOT / "docs/V3_WC_MATCH_CARD_PACK_PHASE_4_VENUE_MAPPING_BRIDGE_20260604.md",
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "match_count": len(bridge),
        "venue_mapped_count": summary.get("venue_mapped_count"),
        "venue_unmapped_count": summary.get("venue_unmapped_count"),
        "manual_mapping_required_count": summary.get("manual_mapping_required_count"),
        "venue_source_found": summary.get("venue_source_found"),
        "manual_template_rows": template_row_count(),
        "conflict_count": summary.get("conflict_count"),
        "duplicate_mapping_count": summary.get("duplicate_mapping_count"),
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
