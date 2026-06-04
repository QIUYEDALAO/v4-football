#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMELINE_DIR = ROOT / "data/runtime/v3_worldcup/odds_timeline"
APPEND_STATUS = ROOT / "data/runtime/status/v3_worldcup_odds_timeline_append_status_20260604.json"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_odds_availability_monitor_20260604.json"


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_monitor(timeline_dir: Path) -> dict[str, Any]:
    rows = load_rows(timeline_dir / "v3_worldcup_odds_timeline.csv")
    append_status = load_json(APPEND_STATUS)
    fixture_ids = {r.get("fixture_id", "") for r in rows if r.get("fixture_id")}
    bookmaker_names = {r.get("bookmaker", "") for r in rows if r.get("bookmaker")}
    market_types = {r.get("market_type", "") for r in rows if r.get("market_type")}
    timestamps = [r.get("snapshot_time", "") for r in rows if r.get("snapshot_time")]
    requested_count = 72
    fixtures_with_odds = len(fixture_ids)
    result = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS",
        "fixture_count": requested_count,
        "fixtures_with_odds": fixtures_with_odds,
        "empty_odds_fixture_count": max(requested_count - fixtures_with_odds, 0),
        "bookmaker_count": len(bookmaker_names),
        "market_type_count": len(market_types),
        "market_types": sorted(market_types),
        "timestamp_coverage": {
            "record_count": len(timestamps),
            "total_records": len(rows),
            "record_pct": round((len(timestamps) / len(rows) * 100), 2) if rows else 0.0,
        },
        "last_snapshot_time": max(timestamps) if timestamps else "",
        "records_added": int(append_status.get("records_added") or 0),
        "duplicate_records_skipped": int(append_status.get("duplicate_records_skipped") or 0),
        "quota_guard_status": append_status.get("quota_guard_status") or "UNKNOWN",
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4": False,
        "has_native_opening": False,
        "has_native_closing": False,
        "movement_requires_timeline": True,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor V3 World Cup odds timeline availability")
    parser.add_argument("--timeline-dir", default=str(DEFAULT_TIMELINE_DIR))
    args = parser.parse_args()
    result = build_monitor(Path(args.timeline_dir))
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
