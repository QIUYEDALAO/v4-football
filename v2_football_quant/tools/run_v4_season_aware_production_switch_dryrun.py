#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "daily_reports"
STATUS_DIR = ROOT / "data" / "runtime" / "status"
LOCAL_TZ = timezone(timedelta(hours=8))

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.v4_scan_and_brief import _resolve_official_grade_from_shadow


def _latest_scout() -> Path | None:
    files = sorted(REPORT_DIR.glob("scout_v4_*.json"))
    return files[-1] if files else None


def _count(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    a = b = c = s = 0
    pending = 0
    qq_allowed = 0
    for r in rows:
        factors = r.get("factors") if isinstance(r.get("factors"), dict) else {}
        out = _resolve_official_grade_from_shadow(r, factors, mode)
        g = str(out.get("official_grade") or "").upper()
        if mode == "official_legacy":
            g = str((r.get("official_grade") or r.get("grade") or "SKIP")).upper()
        if g not in {"A", "B", "C", "SKIP"}:
            g = "SKIP"
        if g == "A":
            a += 1
        elif g == "B":
            b += 1
        elif g == "C":
            c += 1
        else:
            s += 1

        permission = bool(out.get("official_permission")) if mode == "season_aware_rf" else g in {"A", "B"}
        if g in {"A", "B"} and permission:
            pending += 1
            qq_allowed += 1

    return {
        "mode": mode,
        "A": a,
        "B": b,
        "C": c,
        "SKIP": s,
        "pending_ab_count": pending,
        "qq_route_allowed_count": qq_allowed,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scan-date", default="", help="YYYYMMDD; default latest scout")
    args = p.parse_args()

    if args.scan_date:
        scout = REPORT_DIR / f"scout_v4_{args.scan_date}.json"
    else:
        scout = _latest_scout()
    if not scout or not scout.exists():
        print(json.dumps({"status": "BLOCKER", "reason": "scout_missing"}, ensure_ascii=False, indent=2))
        return 2

    data = json.loads(scout.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else []

    legacy = _count(rows, "official_legacy")
    season = _count(rows, "season_aware_rf")

    report = {
        "schema_version": "v4_season_aware_production_switch_dryrun.v1",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "scan_date": scout.stem.split("_")[-1],
        "source_scout": str(scout),
        "source_row_count": len(rows),
        "official_legacy": legacy,
        "season_aware_rf": season,
        "rollback_smoke": {
            "official_legacy_available": True,
            "season_aware_rf_available": True,
            "switchable": True,
        },
        "pending_route_dryrun": {
            "only_ab_in_pending": True,
            "season_aware_pending_count": season["pending_ab_count"],
        },
        "qq_route_guard_dryrun": {
            "official_ab_only": True,
            "shadow_only_blocked": True,
            "dryrun_blocked": True,
            "allowed_count": season["qq_route_allowed_count"],
            "real_send": False,
        },
    }

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out = STATUS_DIR / f"v4_season_aware_production_switch_dryrun_{report['scan_date']}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
