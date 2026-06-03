#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_v3_worldcup_match_level_perception_gap_dryrun.py"
WAR_ROOM_BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
CSV_OUT = ROOT / "data/runtime/v3_worldcup/perception_gap_dryrun/v3_wc4d_match_level_perception_gap_dryrun_20260603.csv"
MD_OUT = ROOT / "data/runtime/v3_worldcup/perception_gap_dryrun/V3_WC4D_MATCH_LEVEL_PERCEPTION_GAP_DRYRUN_20260603.md"
STATUS_OUT = ROOT / "data/runtime/v3_worldcup/perception_gap_dryrun/v3_wc4d_match_level_perception_gap_dryrun_status_20260603.json"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
STATUS_CHECK_OUT = ROOT / "data/runtime/status/check_v3_worldcup_match_level_perception_gap_dryrun_20260603.json"

REQUIRED_FIELDS = {
    "match",
    "venue",
    "market_gap_tag",
    "venue_stress_tag",
    "squad_data_quality",
    "perception_gap_tag",
    "data_insufficient_reason",
    "observation_only",
    "betting_recommendation",
    "affects_v4_grade",
    "scoring_changed",
}


def _add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    war_run = subprocess.run([sys.executable, str(WAR_ROOM_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _add(checks, "war_room_builder_runs", war_run.returncode == 0, war_run.stderr or war_run.stdout[-500:])
    _add(checks, "csv_exists", CSV_OUT.exists(), str(CSV_OUT))
    _add(checks, "md_exists", MD_OUT.exists(), str(MD_OUT))
    _add(checks, "status_exists", STATUS_OUT.exists(), str(STATUS_OUT))

    rows = list(csv.DictReader(CSV_OUT.open(encoding="utf-8"))) if CSV_OUT.exists() else []
    status = _load_json(STATUS_OUT)
    _add(checks, "sample_count_5", len(rows) == 5, len(rows))
    _add(checks, "required_fields_present", bool(rows) and REQUIRED_FIELDS.issubset(rows[0].keys()), sorted(REQUIRED_FIELDS - set(rows[0].keys())) if rows else "no_rows")
    _add(checks, "covers_high_heat_or_humidity", any("HEAT_STRESS" in r.get("venue_stress_tag", "") or "HUMIDITY_STRESS" in r.get("venue_stress_tag", "") for r in rows))
    _add(checks, "covers_altitude", any("ALTITUDE_STRESS" in r.get("venue_stress_tag", "") for r in rows))
    _add(checks, "covers_ordinary_low_pressure", any(r.get("venue_stress_tag") == "WATCH_ONLY" for r in rows))
    _add(checks, "covers_popular_strong_team", any(r.get("sample_id") == "WC4D-POPULAR-001" and r.get("popular_strong_team") == "England" for r in rows))
    _add(checks, "covers_mixed_pressure", any("HUMIDITY_STRESS" in r.get("venue_stress_tag", "") and "ALTITUDE_STRESS" in r.get("venue_stress_tag", "") for r in rows))
    _add(
        checks,
        "missing_odds_xg_have_reason",
        all(
            (
                r.get("odds_available") != "false"
                or r.get("xg_available") != "false"
                or (
                    "current_market_or_api_odds_cache_missing" in r.get("data_insufficient_reason", "")
                    and "api_prediction_or_xg_cache_missing" in r.get("data_insufficient_reason", "")
                )
            )
            for r in rows
        ),
    )
    _add(checks, "observation_only_true", all(r.get("observation_only") == "true" for r in rows), [r.get("observation_only") for r in rows])
    _add(checks, "betting_recommendation_false", all(r.get("betting_recommendation") == "false" for r in rows), [r.get("betting_recommendation") for r in rows])
    _add(checks, "affects_v4_grade_false", all(r.get("affects_v4_grade") == "false" for r in rows), [r.get("affects_v4_grade") for r in rows])
    _add(checks, "scoring_changed_false", all(r.get("scoring_changed") == "false" for r in rows) and status.get("scoring_changed") is False, status)

    md = MD_OUT.read_text(encoding="utf-8", errors="ignore") if MD_OUT.exists() else ""
    for phrase in ["mode: DRY_RUN", "observation_only: true", "betting_recommendation: false", "scoring_changed: false", "recommendation_output: false"]:
        _add(checks, f"md_has_{phrase}", phrase in md, phrase)
    for banned in ["推荐下注", "下注推荐", "买入", "重仓", "稳胆"]:
        _add(checks, f"md_no_{banned}", banned not in md, banned)

    war = _load_json(WAR)
    samples = war.get("match_level_perception_gap_dryrun_samples") if isinstance(war.get("match_level_perception_gap_dryrun_samples"), list) else []
    guard = war.get("match_level_perception_gap_dryrun_safety_guard") if isinstance(war.get("match_level_perception_gap_dryrun_safety_guard"), dict) else {}
    _add(checks, "war_room_layer_present", war.get("match_level_perception_gap_dryrun_status") in {"DRY_RUN_READY", "DRY_RUN_MISSING_WARN_ONLY"}, war.get("match_level_perception_gap_dryrun_status"))
    _add(checks, "war_room_samples_5", len(samples) == 5, len(samples))
    _add(checks, "war_room_observation_only", guard.get("observation_only") is True, guard)
    _add(checks, "war_room_no_betting", guard.get("betting_recommendation") is False, guard)
    _add(checks, "war_room_no_v4", guard.get("affects_v4_grade") is False, guard)
    _add(checks, "war_room_scoring_unchanged", guard.get("scoring_changed") is False, guard)

    blockers = [c["name"] for c in checks if not c["ok"]]
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
    }
    STATUS_CHECK_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(STATUS_CHECK_OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
