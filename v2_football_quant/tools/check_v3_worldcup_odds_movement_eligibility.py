#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TIMELINE_DIR = ROOT / "data/runtime/v3_worldcup/odds_timeline"
TIMELINE_CSV = TIMELINE_DIR / "v3_worldcup_odds_timeline.csv"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_odds_movement_eligibility_20260604.json"

BASE_KEY_FIELDS = [
    "fixture_id",
    "bookmaker",
    "market_type",
    "market_name_raw",
    "selection",
    "line",
]

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
    r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
]

DISALLOWED_CLAIMS = [
    "FAVORITE_STEAM",
    "FAVORITE_DRIFT",
    "LATE_SHARP_MOVE",
    "AH_LINE_MOVEMENT",
    "OU_LINE_MOVEMENT",
    "FUND_FLOW_SIGNAL",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def git_ls_files(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    result = subprocess.run(["git", "ls-files", rel], cwd=ROOT, text=True, capture_output=True, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def secret_hits(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [pattern for pattern in SECRET_PATTERNS if re.search(pattern, text)]


def base_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in BASE_KEY_FIELDS)


def snapshot_id(row: dict[str, str]) -> str:
    return str(row.get("snapshot_id") or row.get("snapshot_time") or "")


def build_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    snapshots = sorted({snapshot_id(r) for r in rows if snapshot_id(r)})
    fixture_ids = sorted({r.get("fixture_id", "") for r in rows if r.get("fixture_id")})
    by_key: dict[tuple[str, ...], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        sid = snapshot_id(row)
        if sid:
            by_key[base_key(row)][sid] = row

    records_compared = 0
    changed_odds_count = 0
    unchanged_odds_count = 0
    same_api_update_time_count = 0
    for versions in by_key.values():
        if len(versions) < 2:
            continue
        ordered = [versions[s] for s in sorted(versions)]
        first = ordered[0]
        last = ordered[-1]
        records_compared += 1
        if str(first.get("odds") or "") != str(last.get("odds") or ""):
            changed_odds_count += 1
        else:
            unchanged_odds_count += 1
        if str(first.get("api_update_time") or "") == str(last.get("api_update_time") or ""):
            same_api_update_time_count += 1

    first_keys = {base_key(r) for r in rows if snapshot_id(r) == snapshots[0]} if snapshots else set()
    last_keys = {base_key(r) for r in rows if snapshot_id(r) == snapshots[-1]} if snapshots else set()
    added_market_count = len(last_keys - first_keys) if len(snapshots) >= 2 else 0
    removed_market_count = len(first_keys - last_keys) if len(snapshots) >= 2 else 0

    fixture_snapshots: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("fixture_id") and snapshot_id(row):
            fixture_snapshots[str(row["fixture_id"])].add(snapshot_id(row))
    fixtures_with_multiple_snapshots = sum(1 for values in fixture_snapshots.values() if len(values) >= 2)

    if len(snapshots) < 2:
        eligibility_status = "NOT_ELIGIBLE_SINGLE_SNAPSHOT"
    elif changed_odds_count > 0 or added_market_count > 0 or removed_market_count > 0:
        eligibility_status = "ELIGIBLE_MULTIPLE_SNAPSHOTS_WITH_CHANGE"
    else:
        eligibility_status = "ELIGIBLE_MULTIPLE_SNAPSHOTS_NO_CHANGE"

    return {
        "generated_at": datetime.now().isoformat(),
        "snapshot_count": len(snapshots),
        "snapshot_ids": snapshots,
        "fixture_count": len(fixture_ids),
        "fixtures_with_multiple_snapshots": fixtures_with_multiple_snapshots,
        "records_compared": records_compared,
        "changed_odds_count": changed_odds_count,
        "unchanged_odds_count": unchanged_odds_count,
        "added_market_count": added_market_count,
        "removed_market_count": removed_market_count,
        "same_api_update_time_count": same_api_update_time_count,
        "eligibility_status": eligibility_status,
        "delta_label": "odds_observation_delta",
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4": False,
        "has_native_opening": False,
        "has_native_closing": False,
        "movement_requires_timeline": True,
        "no_money_flow_judgment": True,
    }


def main() -> int:
    failures: list[str] = []
    rows = read_rows(TIMELINE_CSV)
    if not rows:
        failures.append("timeline_rows_missing")
    report = build_report(rows)
    text = TIMELINE_CSV.read_text(encoding="utf-8", errors="ignore") if TIMELINE_CSV.exists() else ""
    for token in DISALLOWED_CLAIMS:
        if token in text:
            failures.append(f"disallowed_claim_in_timeline:{token}")
    if git_ls_files(TIMELINE_DIR):
        failures.append("timeline_runtime_tracked")
    if secret_hits(TIMELINE_CSV):
        failures.append("secret_literal_in_timeline")
    if report["snapshot_count"] < 2:
        failures.append("movement_not_eligible_single_snapshot")
    if report["eligibility_status"] not in {
        "NOT_ELIGIBLE_SINGLE_SNAPSHOT",
        "ELIGIBLE_MULTIPLE_SNAPSHOTS_NO_CHANGE",
        "ELIGIBLE_MULTIPLE_SNAPSHOTS_WITH_CHANGE",
    }:
        failures.append(f"invalid_eligibility_status:{report['eligibility_status']}")
    if report["delta_label"] != "odds_observation_delta":
        failures.append("delta_label_not_odds_observation_delta")
    for field, expected in {
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4": False,
        "has_native_opening": False,
        "has_native_closing": False,
        "movement_requires_timeline": True,
        "no_money_flow_judgment": True,
    }.items():
        if report.get(field) is not expected:
            failures.append(f"{field}_unexpected:{report.get(field)}")

    out = {
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "movement_eligibility": report,
        "runtime_tracked": bool(git_ls_files(TIMELINE_DIR)),
        "secret_hits": secret_hits(TIMELINE_CSV),
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
