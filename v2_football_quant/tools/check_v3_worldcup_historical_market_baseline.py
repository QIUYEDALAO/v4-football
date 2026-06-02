#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_historical_market_baseline_20260602.json"
BUILDER = ROOT / "tools/build_v3_worldcup_historical_market_baseline.py"
BASE = ROOT / "data/runtime/v3_worldcup/historical_market_baseline/20260602"
CSV = BASE / "v3_wc4a_historical_market_baseline_v1.csv"
JSON = BASE / "v3_wc4a_historical_market_baseline_v1.json"
SUMMARY = BASE / "v3_wc4a_historical_market_summary_v1.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _rate_between(v: Any, lo: float, hi: float) -> bool:
    try:
        x = float(v)
    except Exception:
        return False
    return lo <= x <= hi


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "baseline_csv_exists", CSV.exists(), str(CSV))
    add(checks, "baseline_json_exists", JSON.exists(), str(JSON))
    add(checks, "summary_json_exists", SUMMARY.exists(), str(SUMMARY))
    s = _load(SUMMARY)
    add(checks, "total_192", int(s.get("total_world_cup_finals_matches") or 0) == 192, s.get("total_world_cup_finals_matches"))
    years = s.get("matches_by_year") if isinstance(s.get("matches_by_year"), dict) else {}
    add(checks, "year_2014_64", int(years.get("2014") or 0) == 64, years)
    add(checks, "year_2018_64", int(years.get("2018") or 0) == 64, years)
    add(checks, "year_2022_64", int(years.get("2022") or 0) == 64, years)
    text = CSV.read_text(encoding="utf-8", errors="ignore") if CSV.exists() else ""
    add(checks, "qualifiers_not_in_baseline", "QUALIFIERS_ONLY" not in text, "QUALIFIERS_ONLY absent")
    add(checks, "favorite_bands_generated", text.count("FAVORITE") >= 192, "favorite labels present")
    add(checks, "heavy_count_57", int(s.get("heavy_favorite_count") or 0) == 57, s.get("heavy_favorite_count"))
    add(checks, "heavy_rate_719", _rate_between(s.get("heavy_favorite_win_rate"), 0.718, 0.720), s.get("heavy_favorite_win_rate"))
    add(checks, "strong_count_38", int(s.get("strong_favorite_count") or 0) == 38, s.get("strong_favorite_count"))
    add(checks, "strong_rate_605", _rate_between(s.get("strong_favorite_win_rate"), 0.604, 0.606), s.get("strong_favorite_win_rate"))
    add(checks, "favorite_failed_count_81", int(s.get("favorite_failed_count") or 0) == 81, s.get("favorite_failed_count"))
    add(checks, "favorite_failed_rate_422", _rate_between(s.get("favorite_failed_rate"), 0.421, 0.423), s.get("favorite_failed_rate"))
    add(checks, "underdog_upset_43", int(s.get("underdog_upset_count") or 0) == 43, s.get("underdog_upset_count"))
    add(checks, "draw_38", int(s.get("draw_result_count") or 0) == 38, s.get("draw_result_count"))
    add(checks, "ht_draw_95", int(s.get("ht_draw_count") or 0) == 95, s.get("ht_draw_count"))
    add(checks, "over_2_5_99", int(s.get("over_2_5_count") or 0) == 99, s.get("over_2_5_count"))
    add(checks, "btts_96", int(s.get("btts_count") or 0) == 96, s.get("btts_count"))
    add(checks, "match_coverage_128_192", s.get("thestatsapi_match_id_coverage") == "128/192", s.get("thestatsapi_match_id_coverage"))
    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api_call", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_web_fetch", "http://" not in src and "https://" not in src)
    add(checks, "no_v4_mutation", "default_rules =" not in src and "ab_ratio_min_pct" not in src)
    add(checks, "no_official_final_squad_write", "official_final_squad" not in src.replace("no_official_final_squad_write", ""))
    add(checks, "no_betting_wording", "推荐下注" not in text and "投注建议" not in text, "clean")
    blockers = [x["name"] for x in checks if not x["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
