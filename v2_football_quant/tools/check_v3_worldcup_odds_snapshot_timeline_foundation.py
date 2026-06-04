#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools/run_v3_worldcup_odds_snapshot_dryrun.py"
OUT_DIR = ROOT / "data/runtime/v3_worldcup/odds_snapshot_dryrun/20260604"
QUOTA_OUT_DIR = ROOT / "data/runtime/v3_worldcup/odds_snapshot_dryrun/quota_guard_test"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_timeline_foundation_20260604.json"

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

DISALLOWED_SIGNAL_WORDS = [
    "FAVORITE_STEAM",
    "FAVORITE_DRIFT",
    "LATE_SHARP_MOVE",
    "AH_LINE_MOVEMENT",
    "OU_LINE_MOVEMENT",
    "FUND_FLOW_SIGNAL",
]


def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_ls_files(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    result = run_cmd(["git", "ls-files", rel])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    normal = run_cmd([sys.executable, str(RUNNER), "--limit", "3", "--out-dir", str(OUT_DIR)])
    if normal.returncode != 0:
        failures.append(f"runner_failed:{normal.stderr[-500:]}")

    quota = run_cmd([sys.executable, str(RUNNER), "--limit", "3", "--max-requests", "2", "--out-dir", str(QUOTA_OUT_DIR)])
    if quota.returncode != 0:
        failures.append(f"quota_runner_failed:{quota.stderr[-500:]}")

    json_path = OUT_DIR / "v3_worldcup_odds_snapshot_dryrun_20260604.json"
    csv_path = OUT_DIR / "v3_worldcup_odds_snapshot_timeline_20260604.csv"
    quota_json_path = QUOTA_OUT_DIR / "v3_worldcup_odds_snapshot_dryrun_20260604.json"

    if not json_path.exists():
        failures.append("snapshot_json_missing")
    if not csv_path.exists():
        failures.append("snapshot_csv_missing")
    if not quota_json_path.exists():
        failures.append("quota_json_missing")

    payload: dict[str, Any] = {}
    rows: list[dict[str, str]] = []
    if json_path.exists():
        payload = load_json(json_path)
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

    schema = payload.get("timeline_schema") or []
    for field in REQUIRED_SCHEMA:
        if field not in schema:
            failures.append(f"schema_field_missing:{field}")
    if rows:
        for field in REQUIRED_SCHEMA:
            if field not in rows[0]:
                failures.append(f"csv_field_missing:{field}")
    else:
        failures.append("snapshot_rows_missing")

    markets = set(payload.get("normalized_market_types") or [])
    missing_markets = sorted(REQUIRED_MARKETS - markets)
    for market in missing_markets:
        failures.append(f"market_normalization_missing:{market}")

    for row in rows:
        if str(row.get("observation_only")).lower() != "true":
            failures.append("observation_only_false")
            break
        if str(row.get("betting_recommendation")).lower() != "false":
            failures.append("betting_recommendation_not_false")
            break
        if str(row.get("affects_v4")).lower() != "false":
            failures.append("affects_v4_not_false")
            break
        if str(row.get("scoring_changed")).lower() != "false":
            failures.append("scoring_changed_not_false")
            break
        if str(row.get("is_current_snapshot")).lower() != "true":
            failures.append("is_current_snapshot_not_true")
            break
        if str(row.get("has_native_opening")).lower() != "false":
            failures.append("has_native_opening_not_false")
            break
        if str(row.get("has_native_closing")).lower() != "false":
            failures.append("has_native_closing_not_false")
            break
        if str(row.get("movement_requires_timeline")).lower() != "true":
            failures.append("movement_requires_timeline_not_true")
            break

    combined_rows_text = json.dumps(rows, ensure_ascii=False)
    for token in DISALLOWED_SIGNAL_WORDS:
        if token in combined_rows_text:
            failures.append(f"disallowed_signal_token_present:{token}")

    if payload.get("safety", {}).get("betting_recommendation") is not False:
        failures.append("payload_betting_recommendation_not_false")
    if payload.get("safety", {}).get("affects_v4") is not False:
        failures.append("payload_affects_v4_not_false")

    if git_ls_files(OUT_DIR):
        failures.append("runtime_output_tracked")
    if git_ls_files(QUOTA_OUT_DIR):
        failures.append("quota_runtime_output_tracked")

    for path in [RUNNER, Path(__file__).resolve(), ROOT / "docs/V3_WC_MARKET_INTELLIGENCE_PACK_PHASE_1_20260604.md"]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", text):
            failures.append(f"secret_literal_detected:{path.relative_to(ROOT)}")

    if quota_json_path.exists():
        quota_payload = load_json(quota_json_path)
        if quota_payload.get("status") != "QUOTA_GUARD_STOP":
            failures.append("quota_guard_did_not_stop")
        if quota_payload.get("quota", {}).get("remote_requests_executed") != 0:
            failures.append("quota_guard_remote_request_executed")
        if not quota_payload.get("quota", {}).get("quota_warning"):
            failures.append("quota_warning_missing")

    docs = ROOT / "docs/V3_WC_MARKET_INTELLIGENCE_PACK_PHASE_1_20260604.md"
    if docs.exists():
        doc_text = docs.read_text(encoding="utf-8", errors="ignore")
        for phrase in [
            "API-Football",
            "TheStatsAPI",
            "Free plan",
            "single snapshot",
            "self-built timeline",
            "observation_only=true",
        ]:
            if phrase not in doc_text:
                failures.append(f"doc_phrase_missing:{phrase}")
    else:
        failures.append("docs_missing")

    status = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "warnings": warnings,
        "records": len(rows),
        "markets": sorted(markets),
        "runtime_tracked": bool(git_ls_files(OUT_DIR)),
        "quota_guard_status": load_json(quota_json_path).get("status") if quota_json_path.exists() else "MISSING",
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
