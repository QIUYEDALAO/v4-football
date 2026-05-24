#!/usr/bin/env python3
"""Build V3/V4 dashboard markers from same-day formal scan outputs.

Inputs are the formal scout, formal brief, and scan_perf files for --date. This
never runs scan, never changes candidate grades, and never derives hit rates
from the brief.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
REPORTS = ROOT / "data/daily_reports"
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    blockers: list[str] = []
    warnings: list[str] = []
    scout = REPORTS / f"scout_v4_{args.date}.json"
    brief = REPORTS / f"v4_openclaw_brief_{args.date}.txt"
    scan_perf = REPORTS / f"scan_perf_v4_{args.date}.json"
    if not scout.exists(): blockers.append("scout_missing")
    if not brief.exists(): blockers.append("brief_missing")
    if not scan_perf.exists(): blockers.append("scan_perf_missing")
    result: dict[str, Any] = {}
    if not blockers:
        from v3v4_dashboard_brief_resolver import resolve as resolve_brief
        result = resolve_brief(args.date, write=args.mode == "apply")
        if result.get("blocker"):
            blockers.append("brief_resolver_blocker")
    perf = load(scan_perf, {})
    candidate_view = result.get("candidate_view") or load(STATUS / f"v3v4_dashboard_candidate_view_{args.date}.json", {})
    filtered_notes = []
    brief_text = brief.read_text(encoding="utf-8") if brief.exists() else ""
    scout_rows = load(scout, []) if scout.exists() else []
    if "Djurg" not in brief_text and not any("Djurg" in json.dumps(r, ensure_ascii=False) for r in scout_rows if isinstance(r, dict)):
        filtered_notes.append({"team":"Djurgardens/Djurgården","filtered_reason":f"not_present_in_{args.date}_formal_scout_or_brief; no manual insertion allowed"})
    out = {
        "schema_version":"v3v4_dashboard_marker_build_from_scan_outputs.v1",
        "phase":"V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX",
        "generated_at":datetime.now(TZ).isoformat(),
        "date":args.date,
        "mode":args.mode,
        "input_files":{
            "scout":str(scout.relative_to(ROOT)),
            "brief":str(brief.relative_to(ROOT)),
            "scan_perf":str(scan_perf.relative_to(ROOT)),
        },
        "input_sha256":{"scout":sha(scout),"brief":sha(brief),"scan_perf":sha(scan_perf)},
        "brief_resolution_created": args.mode == "apply" and (STATUS / f"v3v4_dashboard_brief_resolution_{args.date}.json").exists(),
        "candidate_view_created": args.mode == "apply" and (STATUS / f"v3v4_dashboard_candidate_view_{args.date}.json").exists(),
        "A": candidate_view.get("A_count"),
        "B": candidate_view.get("B_count"),
        "C_active": False,
        "SKIP": candidate_view.get("SKIP_count"),
        "formal_count": candidate_view.get("formal_recommendation_count"),
        "scan_total": candidate_view.get("scan_total"),
        "scan_perf_scouted_count": perf.get("scouted_count"),
        "scan_perf_forbidden_count": perf.get("forbidden_count"),
        "scan_ran": False,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "strategy_changed": False,
        "v4_candidate_numbers_changed": False,
        "brief_used_for_hit_rate": False,
        "v2_restored": False,
        "v33_active": False,
        "filtered_observation_notes": filtered_notes,
        "blockers": blockers,
        "warnings": warnings,
        "check_status": "BLOCKER" if blockers else "PASS",
    }
    status_path = STATUS / f"v3v4_dashboard_marker_build_from_scan_outputs_{args.date}.json"
    status_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.strict and blockers:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
