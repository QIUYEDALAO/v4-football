#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_v3_worldcup_perception_gap_blueprint.py"
OUT = ROOT / "data/v3_worldcup/perception_gap_blueprint/v3_worldcup_perception_gap_blueprint_20260602.json"
STATUS = ROOT / "data/runtime/status/check_v3_worldcup_perception_gap_blueprint_20260602.json"

LAYER_KEYS = {
    "historical_market_baseline": [
        "favorite_band",
        "historical_favorite_win_rate",
        "historical_favorite_failed_rate",
        "historical_draw_rate",
        "historical_ht_draw_rate",
        "historical_upset_rate",
        "historical_over_2_5_rate",
        "historical_btts_rate",
    ],
    "current_match_market_layer": [
        "current_1x2_home",
        "current_1x2_draw",
        "current_1x2_away",
        "current_favorite_team",
        "current_favorite_odds",
        "current_favorite_band",
        "market_expectation_score",
        "public_heat_proxy",
        "api_prediction_home",
        "api_prediction_draw",
        "api_prediction_away",
    ],
    "lineup_formation_value_delta_layer": [
        "home_starting_xi_value",
        "away_starting_xi_value",
        "home_expected_value_baseline",
        "away_expected_value_baseline",
        "home_value_delta",
        "away_value_delta",
        "home_formation",
        "away_formation",
        "formation_risk_flag",
        "core_absence_count",
        "goalkeeper_risk_flag",
        "defense_core_missing_flag",
        "striker_core_missing_flag",
    ],
}

TAGS = {
    "UNDERVALUED_WATCH",
    "OVERHYPED_RISK",
    "MARKET_FAIR",
    "LINEUP_WEAKENED",
    "LINEUP_STRONGER_THAN_EXPECTED",
    "DATA_INSUFFICIENT",
    "WATCH_ONLY",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "blueprint_file_exists", OUT.exists(), str(OUT))
    payload = _load(OUT)
    layers = payload.get("input_layers") if isinstance(payload.get("input_layers"), dict) else {}
    for layer, keys in LAYER_KEYS.items():
        obj = layers.get(layer) if isinstance(layers.get(layer), dict) else {}
        add(checks, f"layer_present:{layer}", bool(obj), list(obj.keys()))
        add(checks, f"layer_fields:{layer}", all(k in obj for k in keys), [k for k in keys if k not in obj])
    tags = set(payload.get("output_tags") or [])
    add(checks, "output_tags_complete", tags == TAGS, sorted(tags))
    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}
    add(checks, "observation_only_true", guard.get("observation_only") is True, guard)
    add(checks, "betting_recommendation_false", guard.get("betting_recommendation") is False, guard)
    add(checks, "affects_v4_grade_false", guard.get("affects_v4_grade") is False, guard)
    add(checks, "auto_bet_allowed_false", guard.get("auto_bet_allowed") is False, guard)
    add(checks, "official_final_squad_required_false", guard.get("official_final_squad_required") is False, guard)
    hist = payload.get("historical_baseline_reference") if isinstance(payload.get("historical_baseline_reference"), dict) else {}
    add(checks, "historical_total_192", int(hist.get("total_world_cup_finals_matches") or 0) == 192, hist)
    add(checks, "historical_rates_referenced", all([
        round(float(hist.get("favorite_failed_rate") or 0), 3) == 0.422,
        round(float(hist.get("heavy_favorite_win_rate") or 0), 3) == 0.719,
        round(float(hist.get("strong_favorite_win_rate") or 0), 3) == 0.605,
    ]), hist)
    add(checks, "current_layer_schema_only", "schema:" in json.dumps(layers.get("current_match_market_layer", {}), ensure_ascii=False), "")
    add(checks, "lineup_layer_schema_only", "schema:" in json.dumps(layers.get("lineup_formation_value_delta_layer", {}), ensure_ascii=False), "")
    text = json.dumps(payload, ensure_ascii=False).lower()
    for allowed in ["betting_recommendation", "auto_bet_allowed"]:
        text = text.replace(allowed, "")
    banned = ["推荐下注", "下注建议", "投注建议", "wager", "locked pick", "recommendation_ready", "auto trade"]
    add(checks, "no_forbidden_words", all(x not in text for x in banned), banned)
    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api_call", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_web_fetch", "http://" not in src and "https://" not in src)
    add(checks, "no_official_final_squad_write", "official_final_squad" not in src.replace("official_final_squad_required", ""))
    add(checks, "no_v4_mutation", all(x not in src for x in ["default_rules =", "ab_ratio_min_pct", "v4_outside57_scanner", "scan_and_brief"]))
    blockers = [x["name"] for x in checks if not x["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    STATUS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(STATUS)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
