#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_v3_worldcup_closing_1x2_market_structure.py"
WAR_ROOM_BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
OUT_JSON = ROOT / "data/v3_worldcup/closing_1x2_market_structure/v3_worldcup_closing_1x2_market_structure_20260604.json"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_closing_1x2_market_structure_20260604.json"

DISABLED_TAGS = {
    "FAVORITE_STEAM",
    "FAVORITE_DRIFT",
    "LATE_SHARP_MOVE",
    "AH_LINE_MOVEMENT",
    "OU_LINE_MOVEMENT",
    "FUND_FLOW_SIGNAL",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _approx(value: Any, expected: float) -> bool:
    try:
        return round(float(value), 1) == expected
    except Exception:
        return False


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    war_run = subprocess.run([sys.executable, str(WAR_ROOM_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _add(checks, "war_room_builder_runs", war_run.returncode == 0, war_run.stderr or war_run.stdout[-500:])

    payload = _load(OUT_JSON)
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}
    disabled = set(payload.get("disabled_tags") or [])
    records_text = json.dumps(records, ensure_ascii=False)
    active_tags = {tag for row in records if isinstance(row, dict) for tag in row.get("observation_tags", [])}
    band_rates = payload.get("favorite_failed_rate_by_band") if isinstance(payload.get("favorite_failed_rate_by_band"), dict) else {}

    _add(checks, "output_exists", OUT_JSON.exists(), str(OUT_JSON))
    _add(checks, "status_ready", payload.get("status") == "CLOSING_1X2_MARKET_STRUCTURE_READY", payload.get("status"))
    _add(checks, "matches_192", int(payload.get("total_matches") or len(records)) == 192, payload.get("total_matches"))
    _add(checks, "by_year_64_each", payload.get("by_year") == {"2014": 64, "2018": 64, "2022": 64}, payload.get("by_year"))
    _add(checks, "closing_1x2_complete", payload.get("closing_1x2_complete") is True, payload.get("closing_1x2_complete"))
    _add(checks, "favorite_failed_rate_42_2", _approx(payload.get("favorite_failed_rate"), 42.2), payload.get("favorite_failed_rate"))
    _add(checks, "heavy_failed_28_1", _approx(band_rates.get("HEAVY"), 28.1), band_rates)
    _add(checks, "strong_failed_41_2", _approx(band_rates.get("STRONG"), 41.2), band_rates)
    _add(checks, "moderate_failed_55_2", _approx(band_rates.get("MODERATE"), 55.2), band_rates)
    _add(checks, "disabled_tags_listed", disabled == DISABLED_TAGS, sorted(disabled))
    _add(checks, "disabled_tags_not_active", not (active_tags & DISABLED_TAGS), sorted(active_tags & DISABLED_TAGS))
    _add(checks, "disabled_analysis_flags", guard.get("no_opening_odds") is True and guard.get("no_steam_drift") is True and guard.get("no_fund_flow") is True, guard)
    _add(checks, "no_disabled_signal_text_in_records", all(tag not in records_text for tag in DISABLED_TAGS), "record_scan")
    _add(checks, "records_observation_only", all(r.get("observation_only") is True for r in records), "records")
    _add(checks, "records_no_betting", all(r.get("betting_recommendation") is False for r in records), "records")
    _add(checks, "records_no_v4", all(r.get("affects_v4_grade") is False for r in records), "records")
    _add(checks, "guard_observation_only", guard.get("observation_only") is True, guard)
    _add(checks, "guard_no_betting", guard.get("betting_recommendation") is False, guard)
    _add(checks, "guard_no_v4", guard.get("affects_v4_grade") is False and guard.get("no_v4_changes") is True, guard)
    _add(checks, "guard_scoring_unchanged", guard.get("scoring_changed") is False, guard)

    war = _load(WAR)
    war_guard = war.get("closing_1x2_safety_guard") if isinstance(war.get("closing_1x2_safety_guard"), dict) else {}
    _add(checks, "war_room_ready", war.get("closing_1x2_status") == "CLOSING_1X2_MARKET_STRUCTURE_READY", war.get("closing_1x2_status"))
    _add(checks, "war_room_matches_192", int(war.get("closing_1x2_match_count") or 0) == 192, war.get("closing_1x2_match_count"))
    _add(checks, "war_room_favorite_failed_rate", _approx(war.get("closing_1x2_favorite_failed_rate"), 42.2), war.get("closing_1x2_favorite_failed_rate"))
    _add(checks, "war_room_disabled_tags", set(war.get("closing_1x2_disabled_tags") or []) == DISABLED_TAGS, war.get("closing_1x2_disabled_tags"))
    _add(checks, "war_room_no_betting", war_guard.get("betting_recommendation") is False, war_guard)
    _add(checks, "war_room_no_v4", war_guard.get("affects_v4_grade") is False, war_guard)

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
