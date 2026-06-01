#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_supplement_coverage_20260602.json"
RPT = ROOT / "data/runtime/v3_worldcup/supplement_reports/v3_worldcup_supplement_coverage_20260602.json"
CATS = {"caps_goals_minutes", "injuries", "friendly_form", "market_baseline", "club_form", "coach_profiles", "wc_history"}


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
    add(checks, "report_exists", RPT.exists(), str(RPT))
    r = _load(RPT)
    add(checks, "phase_v3_wc9", r.get("phase") == "V3-WC9", r.get("phase"))
    add(checks, "status_level_code_ready", r.get("status_level") == "CODE_READY", r.get("status_level"))
    add(checks, "blocker_none", r.get("blocker") == "NONE", r.get("blocker"))
    cov = r.get("coverage_by_category") or {}
    add(checks, "all_categories_present", set(cov.keys()) == CATS, list(cov.keys()))
    valid_status = {"PRESENT", "PARTIAL", "MISSING", "TEMPLATE_ONLY", "STALE", "NEED_REVIEW"}
    add(checks, "coverage_status_legal", all((v or {}).get("coverage_status") in valid_status for v in cov.values()), cov)
    if r.get("status") == "SUPPLEMENT_LAYER_READY_TEMPLATE_ONLY":
        add(checks, "template_only_consistent", all((v or {}).get("coverage_status") in {"TEMPLATE_ONLY", "MISSING"} for v in cov.values()), cov)
    g = r.get("safety_guard") or {}
    add(checks, "safety_guard_observation_only", g.get("observation_only") is True, g)
    add(checks, "safety_guard_no_v4_change", g.get("no_v4_changes") is True, g)
    add(checks, "safety_guard_no_override", g.get("supplement_does_not_override_baseline") is True, g)
    txt = json.dumps(r, ensure_ascii=False).lower()
    add(checks, "no_betting_recommendation_words", all(x not in txt for x in ["bet ready", "recommendation_ready", "auto_trade_ready", "auto bet", "locked pick", "推荐下注", "投注建议"]), "text_scan")
    blockers = [c["name"] for c in checks if not c["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
