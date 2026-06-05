#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_matchday_brief_simulation import OUT_JSON, OUT_MD, OUT_SUMMARY, TIMEPOINTS, build

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_matchday_brief_simulation_20260605.json"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
DISALLOWED_TEXT = [
    "steam",
    "drift",
    "fund_flow",
    "fund flow",
    "money flow",
    "sharp move",
    "predicted xi",
    "starting_xi_players",
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


def main() -> int:
    sim, summary, md = build()
    OUT_JSON.write_text(json.dumps(sim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")

    failures: list[str] = []
    for path in [OUT_JSON, OUT_MD, OUT_SUMMARY]:
        add(failures, path.exists(), "required_file_missing", str(path.relative_to(ROOT)))
    add(failures, sim.get("simulation_mode") == "LOCAL_MOCK_ODDS_ONLY", "simulation_mode_unexpected", sim.get("simulation_mode"))
    add(failures, sim.get("live_api_called") is False, "live_api_called_true")
    add(failures, sim.get("timepoints") == TIMEPOINTS, "timepoints_unexpected", sim.get("timepoints"))
    add(failures, len(sim.get("mock_odds_timeline") or []) == 4, "mock_timeline_count_unexpected", len(sim.get("mock_odds_timeline") or []))
    add(failures, summary.get("timepoint_count") == 4, "summary_timepoint_count_unexpected", summary.get("timepoint_count"))
    card = sim.get("brief_card") if isinstance(sim.get("brief_card"), dict) else {}
    add(failures, card.get("card_kind") == "GROUP_STAGE_MATCH", "sample_not_group_stage", card.get("card_kind"))
    add(failures, card.get("lineup_status") == "WAIT_OFFICIAL_LINEUP", "lineup_status_unexpected", card.get("lineup_status"))
    add(failures, "WAIT_OFFICIAL_LINEUP" in card.get("data_gaps", []), "lineup_gap_missing", card.get("data_gaps"))
    odds = card.get("odds_status") if isinstance(card.get("odds_status"), dict) else {}
    for key in ["first_seen_odds", "last_pre_kickoff_odds", "odds_observation_delta"]:
        add(failures, key in odds.get("allowed_fields", []), f"allowed_odds_field_missing_{key}", odds.get("allowed_fields"))
    add(failures, odds.get("mock_odds_used") is True, "mock_odds_used_false")
    add(failures, odds.get("has_native_opening") is False, "native_opening_true")
    add(failures, odds.get("has_native_closing") is False, "native_closing_true")
    add(failures, odds.get("no_money_flow_judgment") is True, "money_flow_guard_missing")
    for row in sim.get("mock_odds_timeline") or []:
        add(failures, row.get("timepoint") in TIMEPOINTS, "mock_timepoint_unexpected", row)
        add(failures, "first_seen_odds" in row, "mock_first_seen_missing", row)
        add(failures, "last_pre_kickoff_odds" in row, "mock_last_pre_missing", row)
        add(failures, "odds_observation_delta" in row, "mock_delta_missing", row)

    for key, expected in {
        "observation_only": True,
        "no_starting_xi_generated": True,
        "no_prediction": True,
        "no_injury_judgment": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }.items():
        add(failures, sim.get(key) is expected, f"safety_{key}_unexpected", sim.get(key))
        add(failures, (summary.get("safety") or {}).get(key) is expected, f"summary_safety_{key}_unexpected", (summary.get("safety") or {}).get(key))

    combined = json.dumps({"sim": sim, "summary": summary}, ensure_ascii=False).lower() + "\n" + md.lower()
    for phrase in DISALLOWED_TEXT:
        add(failures, phrase not in combined, "disallowed_text", phrase)

    staged = staged_files()
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    secrets = secret_hits([OUT_JSON, OUT_MD, OUT_SUMMARY, Path(__file__).resolve(), ROOT / "tools/build_v3_worldcup_matchday_brief_simulation.py"])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "sample_match": sim.get("sample_match"),
        "brief_output": str(OUT_MD.relative_to(ROOT)),
        "simulation_json": str(OUT_JSON.relative_to(ROOT)),
        "timepoints": sim.get("timepoints"),
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
