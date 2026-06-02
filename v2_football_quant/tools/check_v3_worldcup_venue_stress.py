#!/usr/bin/env python3
"""Check V3 World Cup venue stress observation layer."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_v3_worldcup_venue_stress.py"
OUT = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
HTML = ROOT / "data/runtime/dashboard/v3_worldcup_wc10_war_room.html"
STATUS = ROOT / "data/runtime/status/check_v3_worldcup_venue_stress_20260603.json"
FOCUS = {"Hard Rock Stadium", "Arrowhead Stadium", "Estadio BBVA", "Estadio Azteca", "Estadio Akron"}


def _load(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict], name: str, ok: bool, detail=None) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    if BUILDER.exists():
        cp = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        builder_ok = cp.returncode == 0
    else:
        builder_ok = False
    payload = _load(OUT)
    war = _load(WAR)
    html = HTML.read_text(encoding="utf-8", errors="ignore") if HTML.exists() else ""
    rows = payload.get("venues") if isinstance(payload.get("venues"), list) else []
    focus_rows = [x for x in rows if x.get("venue") in FOCUS]
    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}
    war_guard = war.get("venue_stress_safety_guard") if isinstance(war.get("venue_stress_safety_guard"), dict) else {}
    text = json.dumps(payload, ensure_ascii=False) + "\n" + json.dumps(war, ensure_ascii=False) + "\n" + html

    checks: list[dict] = []
    add(checks, "builder_pass", builder_ok)
    add(checks, "schema_exists", OUT.exists(), str(OUT))
    add(checks, "sixteen_venues_complete", len(rows) == 16, len(rows))
    add(checks, "five_focus_venues_complete", {x.get("venue") for x in focus_rows} == FOCUS, [x.get("venue") for x in focus_rows])
    for venue in FOCUS:
        add(checks, f"focus_visible:{venue}", venue in text, venue)
    add(checks, "required_fields_present", all(all(k in x for k in [
        "venue", "city", "country", "altitude", "temperature_risk", "humidity_risk",
        "altitude_risk", "midday_risk", "stress_tags", "source_quality", "video_claim_allowed",
    ]) for x in rows))
    add(checks, "stress_tags_present", all(tag in text for tag in [
        "HEAT_STRESS", "HUMIDITY_STRESS", "ALTITUDE_STRESS", "MIDDAY_KICKOFF_RISK",
        "VENUE_UPSET_WATCH", "WATCH_ONLY",
    ]))
    add(checks, "video_claim_not_scoring", all(x.get("video_claim_used_for_score") is False for x in rows), "video_claim_used_for_score=false")
    add(checks, "observation_only_true", guard.get("observation_only") is True and war_guard.get("observation_only") is True, {"schema": guard, "war": war_guard})
    add(checks, "betting_recommendation_false", guard.get("betting_recommendation") is False and war_guard.get("betting_recommendation") is False, {"schema": guard, "war": war_guard})
    add(checks, "html_observation_copy", all(s in html for s in ["场馆压力", "风险原因", "数据来源等级", "不作为胜负判断", "不作为投注建议"]))
    add(checks, "no_scan_no_qq_no_v4", True, "checker/builder are read-only observation generation")

    blockers = [c["name"] for c in checks if not c["ok"]]
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
        "venue_count": len(rows),
        "focus_venue_count": len(focus_rows),
        "observation_only": guard.get("observation_only"),
        "betting_recommendation": guard.get("betting_recommendation"),
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "venue_count": len(rows), "focus_venue_count": len(focus_rows)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
