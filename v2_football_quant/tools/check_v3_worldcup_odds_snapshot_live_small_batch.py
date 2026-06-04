#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = ROOT / "data/runtime/v3_worldcup/odds_snapshot_dryrun/20260604"
SNAPSHOT_JSON = LIVE_DIR / "v3_worldcup_odds_snapshot_dryrun_20260604.json"
SNAPSHOT_CSV = LIVE_DIR / "v3_worldcup_odds_snapshot_timeline_20260604.csv"
COVERAGE_JSON = LIVE_DIR / "v3_worldcup_odds_snapshot_live_coverage_20260604.json"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json"

REQUIRED_SCHEMA = [
    "snapshot_time",
    "api_update_time",
    "fixture_id",
    "year",
    "home",
    "away",
    "bookmaker",
    "market_type",
    "market_name_raw",
    "selection",
    "line",
    "odds",
    "source",
    "is_current_snapshot",
    "has_native_opening",
    "has_native_closing",
    "movement_requires_timeline",
]

REQUIRED_MARKETS = {
    "MATCH_WINNER_1X2",
    "ASIAN_HANDICAP",
    "GOALS_OVER_UNDER",
    "BOTH_TEAMS_TO_SCORE",
    "DOUBLE_CHANCE",
    "FIRST_HALF_WINNER",
}

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
    r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_ls_files(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    result = subprocess.run(["git", "ls-files", rel], cwd=ROOT, text=True, capture_output=True, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def scan_secret_text(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                hits.append(str(path.relative_to(ROOT)))
                break
    return hits


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    for path, label in [(SNAPSHOT_JSON, "snapshot_json"), (SNAPSHOT_CSV, "snapshot_csv"), (COVERAGE_JSON, "coverage_json")]:
        if not path.exists():
            failures.append(f"{label}_missing")

    payload: dict[str, Any] = load_json(SNAPSHOT_JSON) if SNAPSHOT_JSON.exists() else {}
    coverage: dict[str, Any] = load_json(COVERAGE_JSON) if COVERAGE_JSON.exists() else {}
    rows: list[dict[str, str]] = []
    if SNAPSHOT_CSV.exists():
        with SNAPSHOT_CSV.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

    if payload.get("dry_run") is not False:
        failures.append("live_payload_not_marked_live")
    if payload.get("status") != "LIVE_SNAPSHOT_READY":
        failures.append(f"unexpected_live_status:{payload.get('status')}")
    if coverage.get("requested_count") != 72:
        failures.append(f"coverage_requested_count_not_72:{coverage.get('requested_count')}")
    if int(coverage.get("total_records") or 0) <= 0:
        failures.append("coverage_total_records_zero")
    if int(coverage.get("api_error_count") or 0) != 0:
        failures.append(f"api_error_count_nonzero:{coverage.get('api_error_count')}")

    schema = payload.get("timeline_schema") or []
    for field in REQUIRED_SCHEMA:
        if field not in schema:
            failures.append(f"schema_field_missing:{field}")
        if rows and field not in rows[0]:
            failures.append(f"csv_field_missing:{field}")

    markets = set(payload.get("normalized_market_types") or [])
    for market in sorted(REQUIRED_MARKETS - markets):
        failures.append(f"market_normalization_missing:{market}")
    if "OTHER_MARKET" in markets:
        warnings.append("WARN_ONLY_UNKNOWN_MARKET_RAW_PRESERVED")

    for row in rows:
        checks = {
            "observation_only": "true",
            "betting_recommendation": "false",
            "affects_v4": "false",
            "scoring_changed": "false",
            "has_native_opening": "false",
            "has_native_closing": "false",
            "movement_requires_timeline": "true",
        }
        for field, expected in checks.items():
            if str(row.get(field)).lower() != expected:
                failures.append(f"{field}_unexpected:{row.get(field)}")
                break
        if failures and failures[-1].endswith(str(row.get(field))):
            break

    for field, expected in {
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4": False,
        "has_native_opening": False,
        "has_native_closing": False,
        "movement_requires_timeline": True,
    }.items():
        if coverage.get(field) is not expected:
            failures.append(f"coverage_{field}_unexpected:{coverage.get(field)}")

    if git_ls_files(LIVE_DIR):
        failures.append("live_runtime_output_tracked")
    secret_hits = scan_secret_text([SNAPSHOT_JSON, SNAPSHOT_CSV, COVERAGE_JSON])
    if secret_hits:
        failures.append(f"secret_literal_in_runtime:{secret_hits}")

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "warnings": warnings + list(coverage.get("warn_only") or []),
        "coverage": coverage,
        "runtime_tracked": bool(git_ls_files(LIVE_DIR)),
        "secret_hits": secret_hits,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
