#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_v3_worldcup_tactical_profile_layer.py"
WAR_ROOM_BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
OUT_JSON = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_tactical_profile_layer_20260604.json"

ALLOWED_TAGS = {
    "LOW_BLOCK_WATCH",
    "COUNTER_ATTACK_WATCH",
    "OPEN_GAME_WATCH",
    "HIGH_PRESS_FATIGUE_WATCH",
    "MIDFIELD_CONGESTION_WATCH",
    "FORMATION_DATA_INSUFFICIENT",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    war_run = subprocess.run([sys.executable, str(WAR_ROOM_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _add(checks, "war_room_builder_runs", war_run.returncode == 0, war_run.stderr or war_run.stdout[-500:])
    payload = _load(OUT_JSON)
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), list) else []
    matchups = payload.get("formation_matchups") if isinstance(payload.get("formation_matchups"), list) else []
    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}

    _add(checks, "output_exists", OUT_JSON.exists(), str(OUT_JSON))
    _add(checks, "status_ready", payload.get("status") == "TACTICAL_PROFILE_LAYER_READY", payload.get("status"))
    _add(checks, "profiles_48", int(payload.get("teams_profiled_count") or len(profiles)) == 48, payload.get("teams_profiled_count"))
    _add(checks, "profiles_unique_48", len({p.get("team") for p in profiles}) == 48, len({p.get("team") for p in profiles}))
    _add(checks, "real_formation_samples_24", int(payload.get("teams_with_real_formation_samples") or 0) == 24, payload.get("teams_with_real_formation_samples"))
    _add(checks, "insufficient_24", int(payload.get("teams_formation_data_insufficient") or 0) == 24, payload.get("teams_formation_data_insufficient"))
    _add(checks, "matchups_72", int(payload.get("formation_matchup_samples_count") or len(matchups)) == 72, payload.get("formation_matchup_samples_count"))
    _add(checks, "unique_formations_14", int(payload.get("unique_formations_count") or 0) == 14, payload.get("unique_formations_count"))
    _add(checks, "tags_allowed", all(set(p.get("tactical_tags") or []) <= ALLOWED_TAGS for p in profiles), [p.get("tactical_tags") for p in profiles[:5]])
    _add(checks, "all_profiles_observation_only", all(p.get("observation_only") is True and p.get("no_scoring") is True for p in profiles), "profiles")
    _add(checks, "all_profiles_no_betting", all(p.get("betting_recommendation") is False for p in profiles), "profiles")
    _add(checks, "all_profiles_no_v4", all(p.get("affects_v4_grade") is False for p in profiles), "profiles")
    _add(checks, "all_profiles_scoring_unchanged", all(p.get("scoring_changed") is False for p in profiles), "profiles")
    _add(checks, "all_matchups_observation_only", all(m.get("observation_only") is True and m.get("no_scoring") is True for m in matchups), "matchups")
    _add(checks, "guard_observation_only", guard.get("observation_only") is True and guard.get("no_scoring") is True, guard)
    _add(checks, "guard_no_betting", guard.get("betting_recommendation") is False, guard)
    _add(checks, "guard_no_v4", guard.get("affects_v4_grade") is False and guard.get("no_v4_changes") is True, guard)
    _add(checks, "guard_scoring_unchanged", guard.get("scoring_changed") is False, guard)

    war = _load(WAR)
    war_guard = war.get("tactical_profile_safety_guard") if isinstance(war.get("tactical_profile_safety_guard"), dict) else {}
    _add(checks, "war_room_layer_ready", war.get("tactical_profile_status") == "TACTICAL_PROFILE_LAYER_READY", war.get("tactical_profile_status"))
    _add(checks, "war_room_profiles_48", int(war.get("tactical_profile_team_count") or 0) == 48, war.get("tactical_profile_team_count"))
    _add(checks, "war_room_matchups_72", int(war.get("tactical_profile_matchup_count") or 0) == 72, war.get("tactical_profile_matchup_count"))
    _add(checks, "war_room_unique_formations_14", int(war.get("tactical_profile_unique_formations_count") or 0) == 14, war.get("tactical_profile_unique_formations_count"))
    _add(checks, "war_room_no_scoring", war_guard.get("no_scoring") is True and war_guard.get("scoring_changed") is False, war_guard)
    _add(checks, "war_room_no_betting", war_guard.get("betting_recommendation") is False, war_guard)

    blockers = [c["name"] for c in checks if not c["ok"]]
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
    }
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(STATUS_OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
