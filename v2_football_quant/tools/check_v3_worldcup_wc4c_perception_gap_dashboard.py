#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
HTML = ROOT / "data/runtime/dashboard/v3_worldcup_wc10_war_room.html"
OUT = ROOT / "data/runtime/status/check_v3_worldcup_wc4c_perception_gap_dashboard_20260602.json"

TAGS = [
    "UNDERVALUED_WATCH",
    "OVERHYPED_RISK",
    "MARKET_FAIR",
    "LINEUP_WEAKENED",
    "LINEUP_STRONGER_THAN_EXPECTED",
    "DATA_INSUFFICIENT",
    "WATCH_ONLY",
]

LAYERS = [
    "historical_market_baseline",
    "current_match_market_layer",
    "lineup_formation_value_delta_layer",
]


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
    add(checks, "model_has_blueprint_status", bool(payload.get("perception_gap_blueprint_status")), payload.get("perception_gap_blueprint_status"))
    layers = payload.get("perception_gap_input_layers") if isinstance(payload.get("perception_gap_input_layers"), dict) else {}
    add(checks, "model_has_three_layers", all(k in layers for k in LAYERS), list(layers.keys()))
    tags = payload.get("perception_gap_output_tags") if isinstance(payload.get("perception_gap_output_tags"), list) else []
    add(checks, "model_has_7_tags", set(tags) == set(TAGS), tags)
    guard = payload.get("perception_gap_safety_guard") if isinstance(payload.get("perception_gap_safety_guard"), dict) else {}
    add(checks, "guard_observation_only", guard.get("observation_only") is True, guard)
    add(checks, "guard_no_betting", guard.get("betting_recommendation") is False, guard)
    add(checks, "guard_no_v4_grade_impact", guard.get("affects_v4_grade") is False, guard)
    add(checks, "wc4b_baseline_still_present", bool(payload.get("historical_market_baseline_status")), payload.get("historical_market_baseline_status"))
    add(checks, "wc5e_candidate_review_still_present", bool(payload.get("candidate_review_status")), payload.get("candidate_review_status"))
    html = HTML.read_text(encoding="utf-8", errors="ignore") if HTML.exists() else ""
    low = html.lower()
    add(checks, "html_has_blueprint_block", "perception gap 评分蓝图" in low, "html")
    add(checks, "html_has_three_layers", all(x in html for x in ["历史市场基准层", "当前市场 / API prediction 层", "首发 / 阵型 / 身价差值层"]), "html")
    add(checks, "html_has_7_tags", all(x in html for x in TAGS), "html")
    add(checks, "html_has_observation_safety", "这是观察层，不是投注建议" in html, "html")
    add(checks, "html_has_no_v4_impact", "不影响 V4 A/B/C/SKIP" in html, "html")
    sanitized = (
        html.replace("不是投注建议", "")
        .replace("不输出投注建议", "")
        .replace("任何 watchlist 都不是推荐下注", "")
    )
    add(checks, "html_no_betting_recommendation", all(x not in sanitized for x in ["推荐下注", "下注建议", "投注建议", "locked pick"]), "html")
    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api_call", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_web_fetch", "http://" not in src and "https://" not in src)
    blockers = [x["name"] for x in checks if not x["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
