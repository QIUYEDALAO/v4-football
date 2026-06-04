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

REQUIRED_MODULES = {
    "venue_stress_layer",
    "perception_gap_dryrun",
    "tactical_profile_layer",
    "closing_1x2_market_structure",
    "odds_snapshot_timeline",
    "odds_observation_delta",
    "final_26_squad_pack",
    "final_26_squad_profile",
    "wc10_war_room",
    "lineup_readiness_pending",
}
EXPECTED_SAFETY = {
    "observation_only": True,
    "betting_recommendation": False,
    "affects_v4": False,
    "no_starting_xi": True,
    "no_prediction": True,
}
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
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
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
