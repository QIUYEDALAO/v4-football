#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260604"
SOURCE_DIR = ROOT / "data/manual_sources/v3_worldcup/odds/football_data/v3_wc_closing_1x2_source_pack"
SOURCE_CSV = SOURCE_DIR / "v3_wc_closing_1x2_market_structure.csv"
SOURCE_SUMMARY = SOURCE_DIR / "v3_wc_closing_1x2_market_structure_summary.json"
SOURCE_REPORT = SOURCE_DIR / "V3_WC_CLOSING_1X2_MARKET_STRUCTURE_REPORT.md"

OUT_DIR = ROOT / "data/v3_worldcup/closing_1x2_market_structure"
STATUS_DIR = ROOT / "data/runtime/status"
OUT_JSON = OUT_DIR / f"v3_worldcup_closing_1x2_market_structure_{RUN_DATE}.json"
STATUS_JSON = STATUS_DIR / f"v3_worldcup_closing_1x2_market_structure_{RUN_DATE}.json"

ALLOWED_TAGS = [
    "CLOSING_FAVORITE_HEAVY",
    "CLOSING_FAVORITE_STRONG",
    "CLOSING_FAVORITE_MODERATE",
    "FAVORITE_FAILURE_BASELINE",
    "BOOKMAKER_SPREAD_WIDE",
    "MARKET_SPLIT_WATCH",
    "DRAW_TRAP_WATCH",
    "UNDERDOG_UPSET_PROFILE",
    "MARKET_DATA_LIMITED_NO_OPENING",
]

DISABLED_TAGS = [
    "FAVORITE_STEAM",
    "FAVORITE_DRIFT",
    "LATE_SHARP_MOVE",
    "AH_LINE_MOVEMENT",
    "OU_LINE_MOVEMENT",
    "FUND_FLOW_SIGNAL",
]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return obj


def _to_float(value: Any) -> float:
    try:
        return float(str(value or "0"))
    except Exception:
        return 0.0


def _to_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _tags(row: dict[str, str]) -> list[str]:
    tags = ["MARKET_DATA_LIMITED_NO_OPENING"]
    band = str(row.get("favorite_band") or "").upper()
    if band == "HEAVY":
        tags.append("CLOSING_FAVORITE_HEAVY")
    elif band == "STRONG":
        tags.append("CLOSING_FAVORITE_STRONG")
    elif band == "MODERATE":
        tags.append("CLOSING_FAVORITE_MODERATE")
    if _to_bool(row.get("favorite_failed")):
        tags.append("FAVORITE_FAILURE_BASELINE")
    if _to_bool(row.get("draw_result")):
        tags.append("DRAW_TRAP_WATCH")
    if _to_bool(row.get("underdog_upset")):
        tags.append("UNDERDOG_UPSET_PROFILE")
    if _to_float(row.get("bookmaker_spread")) > 1.0:
        tags.append("BOOKMAKER_SPREAD_WIDE")
    if _to_bool(row.get("market_split_watch")):
        tags.append("MARKET_SPLIT_WATCH")
    return tags


def _favorite_failed_rate_by_band(rows: list[dict[str, str]], band: str) -> float:
    selected = [row for row in rows if str(row.get("favorite_band") or "").upper() == band]
    if not selected:
        return 0.0
    failed = sum(1 for row in selected if _to_bool(row.get("favorite_failed")))
    return round(failed / len(selected) * 100, 1)


def build_payload() -> dict[str, Any]:
    rows = _read_rows(SOURCE_CSV)
    summary = _load_json(SOURCE_SUMMARY)
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "year": int(row.get("year") or 0),
                "match": f"{row.get('home', '')} vs {row.get('away', '')}",
                "home": row.get("home") or "",
                "away": row.get("away") or "",
                "date": row.get("date") or "",
                "favorite_side": row.get("favorite_side") or "",
                "favorite_closing_odds": _to_float(row.get("favorite_closing")),
                "favorite_band": row.get("favorite_band") or "",
                "favorite_win": _to_bool(row.get("favorite_win")),
                "favorite_failed": _to_bool(row.get("favorite_failed")),
                "draw_result": _to_bool(row.get("draw_result")),
                "underdog_upset": _to_bool(row.get("underdog_upset")),
                "bookmaker_spread": _to_float(row.get("bookmaker_spread")),
                "max_avg_gap": _to_float(row.get("max_avg_gap")),
                "market_split_watch": _to_bool(row.get("market_split_watch")),
                "observation_tags": _tags(row),
                "observation_only": True,
                "betting_recommendation": False,
                "affects_v4_grade": False,
                "scoring_changed": False,
                "no_opening_odds": True,
                "no_steam_drift": True,
                "no_fund_flow": True,
            }
        )

    band_failed_rates = {
        "HEAVY": _favorite_failed_rate_by_band(rows, "HEAVY"),
        "STRONG": _favorite_failed_rate_by_band(rows, "STRONG"),
        "MODERATE": _favorite_failed_rate_by_band(rows, "MODERATE"),
    }
    payload = {
        "schema_version": "v3_worldcup_closing_1x2_market_structure.v1",
        "phase": "V3-WC4H",
        "status": "CLOSING_1X2_MARKET_STRUCTURE_READY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_files": {
            "market_structure_csv": str(SOURCE_CSV),
            "summary_json": str(SOURCE_SUMMARY),
            "source_report": str(SOURCE_REPORT),
        },
        "total_matches": len(records),
        "by_year": summary.get("by_year") if isinstance(summary.get("by_year"), dict) else {},
        "closing_1x2_complete": all(
            row.get("h_avg") and row.get("d_avg") and row.get("a_avg") and row.get("h_max") and row.get("d_max") and row.get("a_max")
            for row in rows
        ),
        "favorite_win_rate": float(summary.get("favorite_win_rate") or 0),
        "favorite_failed_rate": float(summary.get("favorite_failed_rate") or 0),
        "draw_rate": float(summary.get("draw_rate") or 0),
        "underdog_upset_rate": float(summary.get("underdog_upset_rate") or 0),
        "favorite_failed_rate_by_band": band_failed_rates,
        "allowed_observation_tags": ALLOWED_TAGS,
        "disabled_tags": DISABLED_TAGS,
        "excluded_analysis": summary.get("excluded_analysis") if isinstance(summary.get("excluded_analysis"), list) else [],
        "records": records,
        "safety_guard": {
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
            "scoring_changed": False,
            "no_opening_odds": True,
            "no_steam_drift": True,
            "no_fund_flow": True,
            "no_v4_changes": True,
        },
    }
    return payload


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_JSON.write_text(
        json.dumps(
            {
                "generated_at_utc": payload["generated_at_utc"],
                "status": payload["status"],
                "total_matches": payload["total_matches"],
                "closing_1x2_complete": payload["closing_1x2_complete"],
                "favorite_failed_rate": payload["favorite_failed_rate"],
                "favorite_failed_rate_by_band": payload["favorite_failed_rate_by_band"],
                "disabled_tags": payload["disabled_tags"],
                "safety_guard": payload["safety_guard"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "output": str(OUT_JSON), "status_json": str(STATUS_JSON)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
