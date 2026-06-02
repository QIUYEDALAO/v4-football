#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "data/runtime/v3_worldcup/historical_market_baseline/20260602/v3_wc4a_historical_market_summary_v1.json"
OUT_DIR = ROOT / "data/v3_worldcup/perception_gap_blueprint"
OUT = OUT_DIR / "v3_worldcup_perception_gap_blueprint_20260602.json"
STATUS_DIR = ROOT / "data/runtime/status"
STATUS = STATUS_DIR / "v3_worldcup_perception_gap_blueprint_20260602.json"
CST = timezone(timedelta(hours=8))


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _rate(summary: dict[str, Any], key: str) -> float:
    try:
        return float(summary.get(key) or 0.0)
    except Exception:
        return 0.0


def build_blueprint(summary: dict[str, Any]) -> dict[str, Any]:
    total = int(summary.get("total_world_cup_finals_matches") or 0)
    draw_count = int(summary.get("draw_result_count") or 0)
    ht_draw_count = int(summary.get("ht_draw_count") or 0)
    upset_count = int(summary.get("underdog_upset_count") or 0)
    over_count = int(summary.get("over_2_5_count") or 0)
    btts_count = int(summary.get("btts_count") or 0)
    return {
        "generated_at": datetime.now(CST).isoformat(),
        "phase": "V3-WC4C",
        "status": "PERCEPTION_GAP_SCORING_BLUEPRINT_READY",
        "scope": "match-level structure only",
        "source": "WC4B historical market baseline",
        "historical_baseline_reference": {
            "total_world_cup_finals_matches": total,
            "years": summary.get("matches_by_year") or {"2014": 64, "2018": 64, "2022": 64},
            "qualifiers_in_baseline": False,
            "heavy_favorite_count": int(summary.get("heavy_favorite_count") or 0),
            "heavy_favorite_win_rate": _rate(summary, "heavy_favorite_win_rate"),
            "strong_favorite_count": int(summary.get("strong_favorite_count") or 0),
            "strong_favorite_win_rate": _rate(summary, "strong_favorite_win_rate"),
            "favorite_failed_count": int(summary.get("favorite_failed_count") or 0),
            "favorite_failed_rate": _rate(summary, "favorite_failed_rate"),
            "draw_result_count": draw_count,
            "ht_draw_count": ht_draw_count,
            "underdog_upset_count": upset_count,
            "over_2_5_count": over_count,
            "btts_count": btts_count,
        },
        "input_layers": {
            "historical_market_baseline": {
                "favorite_band": "schema: HEAVY_FAVORITE | STRONG_FAVORITE | BALANCED | UNDERDOG",
                "historical_favorite_win_rate": {
                    "heavy": _rate(summary, "heavy_favorite_win_rate"),
                    "strong": _rate(summary, "strong_favorite_win_rate"),
                },
                "historical_favorite_failed_rate": _rate(summary, "favorite_failed_rate"),
                "historical_draw_rate": round(draw_count / total, 3) if total else 0.0,
                "historical_ht_draw_rate": round(ht_draw_count / total, 3) if total else 0.0,
                "historical_upset_rate": round(upset_count / total, 3) if total else 0.0,
                "historical_over_2_5_rate": round(over_count / total, 3) if total else 0.0,
                "historical_btts_rate": round(btts_count / total, 3) if total else 0.0,
            },
            "current_match_market_layer": {
                "current_1x2_home": "schema:number|null",
                "current_1x2_draw": "schema:number|null",
                "current_1x2_away": "schema:number|null",
                "current_favorite_team": "schema:string|null",
                "current_favorite_odds": "schema:number|null",
                "current_favorite_band": "schema:string|null",
                "market_expectation_score": "schema:0-100|null",
                "public_heat_proxy": "schema:LOW|MEDIUM|HIGH|UNKNOWN",
                "api_prediction_home": "schema:number|null",
                "api_prediction_draw": "schema:number|null",
                "api_prediction_away": "schema:number|null",
            },
            "lineup_formation_value_delta_layer": {
                "home_starting_xi_value": "schema:number|null",
                "away_starting_xi_value": "schema:number|null",
                "home_expected_value_baseline": "schema:number|null",
                "away_expected_value_baseline": "schema:number|null",
                "home_value_delta": "schema:number|null",
                "away_value_delta": "schema:number|null",
                "home_formation": "schema:string|null",
                "away_formation": "schema:string|null",
                "formation_risk_flag": "schema:boolean|null",
                "core_absence_count": "schema:number|null",
                "goalkeeper_risk_flag": "schema:boolean|null",
                "defense_core_missing_flag": "schema:boolean|null",
                "striker_core_missing_flag": "schema:boolean|null",
            },
        },
        "output_tags": [
            "UNDERVALUED_WATCH",
            "OVERHYPED_RISK",
            "MARKET_FAIR",
            "LINEUP_WEAKENED",
            "LINEUP_STRONGER_THAN_EXPECTED",
            "DATA_INSUFFICIENT",
            "WATCH_ONLY",
        ],
        "next_required_inputs": [
            "current odds",
            "API prediction",
            "pre-match starting XI",
            "formation",
            "starting XI market value",
        ],
        "safety_guard": {
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
            "auto_bet_allowed": False,
            "official_final_squad_required": False,
            "no_api_call": True,
            "no_web_fetch": True,
            "match_conclusion_generated": False,
        },
    }


def main() -> int:
    summary = _load(SUMMARY)
    blueprint = build_blueprint(summary)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
    STATUS.write_text(
        json.dumps(
            {
                "generated_at": blueprint["generated_at"],
                "phase": blueprint["phase"],
                "status": blueprint["status"],
                "output": str(OUT),
                "safety_guard": blueprint["safety_guard"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "output": str(OUT), "status_json": str(STATUS)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
