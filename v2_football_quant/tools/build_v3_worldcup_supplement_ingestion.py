#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.v3_worldcup_supplement_schema import SUPPLEMENT_SCHEMA, summarize_coverage
except ImportError:
    from v3_worldcup_supplement_schema import SUPPLEMENT_SCHEMA, summarize_coverage

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/v3_worldcup"
SUPP = V3 / "supplements"
TPL = SUPP / "templates"
OUT_DIR = ROOT / "data/runtime/v3_worldcup/supplement_reports"
ROSTERS = V3 / "rosters/worldcup_rosters_20260526.json"
WAR_ROOM = V3 / "war_room/v3_worldcup_wc10_war_room_20260602.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def main() -> int:
    roster_meta = (_load(ROSTERS).get("meta") or {})
    teams_total = int(roster_meta.get("total_teams") or 46)
    players_total = int(roster_meta.get("total_players") or 1375)

    categories = list(SUPPLEMENT_SCHEMA.keys())
    coverage_by_category: dict[str, Any] = {}
    template_only_categories: list[str] = []
    missing_categories: list[str] = []
    stale_categories: list[str] = []
    supplement_files_found: list[str] = []
    supplement_files_missing: list[str] = []

    for c in categories:
        real_path = SUPP / f"{c}.json"
        tpl_path = TPL / f"{c}_template.json"
        payload = {}
        if real_path.exists():
            payload = _load(real_path)
            supplement_files_found.append(str(real_path))
        elif tpl_path.exists():
            payload = _load(tpl_path)
            supplement_files_found.append(str(tpl_path))
        else:
            supplement_files_missing.append(str(real_path))
        s = summarize_coverage(c, payload)
        coverage_by_category[c] = s
        if s["coverage_status"] == "TEMPLATE_ONLY":
            template_only_categories.append(c)
        elif s["coverage_status"] == "MISSING":
            missing_categories.append(c)
        elif s["coverage_status"] == "STALE":
            stale_categories.append(c)

    only_templates = len(template_only_categories) + len(missing_categories) == len(categories)
    status = "SUPPLEMENT_LAYER_READY_TEMPLATE_ONLY" if only_templates else "SUPPLEMENT_LAYER_PARTIAL_READY_WITH_WARN_ONLY"
    warn_only_items = [f"{c.upper()}_TEMPLATE_ONLY" for c in template_only_categories] + [f"{c.upper()}_MISSING" for c in missing_categories]
    war = _load(WAR_ROOM)
    coverage_by_team = {
        "status": "TEMPLATE_ONLY_OR_MISSING",
        "note": "Team-level supplement aggregation pending real supplement files.",
        "teams_reference_count": int(war.get("teams_total") or teams_total),
    }

    report = {
        "generated_at": datetime.now().isoformat(),
        "phase": "V3-WC9",
        "status": status,
        "status_level": "CODE_READY",
        "blocker": "NONE",
        "warn_only_items": warn_only_items,
        "teams_total": teams_total,
        "players_total": players_total,
        "supplement_files_found": supplement_files_found,
        "supplement_files_missing": supplement_files_missing,
        "coverage_by_category": coverage_by_category,
        "coverage_by_team": coverage_by_team,
        "missing_categories": missing_categories,
        "stale_categories": stale_categories,
        "template_only_categories": template_only_categories,
        "readiness_delta": {
            "war_room_status_before": war.get("status") or "WAR_ROOM_READY_WITH_WARN_ONLY",
            "war_room_status_after": "WAR_ROOM_READY_WITH_WARN_ONLY",
            "note": "Supplement layer added; no production readiness conclusion without real supplement data.",
        },
        "perception_gap_enrichment_status": "PENDING_REAL_SUPPLEMENTS",
        "policy_note": "Supplement ingestion is observation-only and does not modify V3 roster baseline or V4 logic.",
        "safety_guard": {
            "observation_only": True,
            "no_betting_recommendations": True,
            "no_stake": True,
            "no_qq_push": True,
            "no_pending_write": True,
            "no_v4_changes": True,
            "no_default_rules_change": True,
            "no_ab_thresholds_change": True,
            "no_live_bet_change": True,
            "no_cron_change": True,
            "supplement_does_not_modify_roster": True,
            "supplement_does_not_override_baseline": True,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "v3_worldcup_supplement_coverage_20260602.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "coverage_report": str(out), "phase": "V3-WC9"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
