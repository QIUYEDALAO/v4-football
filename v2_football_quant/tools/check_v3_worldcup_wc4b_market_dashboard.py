#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_wc4b_market_dashboard_20260602.json"
BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
HTML = ROOT / "data/runtime/dashboard/v3_worldcup_wc10_war_room.html"


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
    payload = _load(WAR)
    add(checks, "market_status_ready", payload.get("historical_market_baseline_status") == "READY", payload.get("historical_market_baseline_status"))
    summary = payload.get("historical_market_baseline_summary") if isinstance(payload.get("historical_market_baseline_summary"), dict) else {}
    counts = payload.get("historical_market_baseline_counts") if isinstance(payload.get("historical_market_baseline_counts"), dict) else {}
    rates = payload.get("historical_market_baseline_key_rates") if isinstance(payload.get("historical_market_baseline_key_rates"), dict) else {}
    quality = payload.get("historical_market_baseline_data_quality") if isinstance(payload.get("historical_market_baseline_data_quality"), dict) else {}
    years = payload.get("historical_market_baseline_years") if isinstance(payload.get("historical_market_baseline_years"), list) else []
    add(checks, "matches_192", int(summary.get("total_world_cup_finals_matches") or 0) == 192, summary)
    add(checks, "years_2014_2018_2022", {x.get("year") for x in years} == {2014, 2018, 2022}, years)
    add(checks, "qualifiers_not_included", quality.get("qualifiers_in_baseline") is False, quality)
    add(checks, "heavy_rate_719", round(float(rates.get("heavy_favorite_win_rate") or 0), 3) == 0.719, rates)
    add(checks, "strong_rate_605", round(float(rates.get("strong_favorite_win_rate") or 0), 3) == 0.605, rates)
    add(checks, "failed_rate_422", round(float(rates.get("favorite_failed_rate") or 0), 3) == 0.422, rates)
    add(checks, "underdog_43", int(counts.get("underdog_upset_count") or 0) == 43, counts)
    add(checks, "ht_draw_95", int(counts.get("ht_draw_count") or 0) == 95, counts)
    add(checks, "candidate_review_still_present", bool(payload.get("candidate_review_status")), payload.get("candidate_review_status"))
    html = HTML.read_text(encoding="utf-8", errors="ignore") if HTML.exists() else ""
    low = html.lower()
    add(checks, "html_has_market_block", "historical market baseline" in low and "世界杯历史市场基准" in html, "html")
    add(checks, "html_has_perception_gap", "perception gap" in low, "html")
    add(checks, "html_has_safety_text", "不是投注建议" in html and "不影响 v4" in low, "html")
    sanitized_html = (
        html.replace("不是投注建议", "")
        .replace("不输出投注建议", "")
        .replace("任何 watchlist 都不是推荐下注", "")
    )
    add(checks, "html_no_betting_advice", "推荐下注" not in sanitized_html and "下注建议" not in sanitized_html and "投注建议" not in sanitized_html, "html")
    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api_call", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_web_fetch", "http://" not in src and "https://" not in src)
    add(checks, "no_v4_mutation", "default_rules =" not in src and "ab_ratio_min_pct" not in src)
    blockers = [x["name"] for x in checks if not x["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
