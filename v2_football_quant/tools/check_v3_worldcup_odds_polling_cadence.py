#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/v3_worldcup_odds_polling_cadence.json"
APPENDER = ROOT / "tools/append_v3_worldcup_odds_timeline.py"
MONITOR = ROOT / "tools/check_v3_worldcup_odds_availability_monitor.py"
TIMELINE_DIR = ROOT / "data/runtime/v3_worldcup/odds_timeline/checker_run"
TIMELINE_CSV = TIMELINE_DIR / "v3_worldcup_odds_timeline.csv"
TIMELINE_JSONL = TIMELINE_DIR / "v3_worldcup_odds_timeline.jsonl"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_odds_polling_cadence_20260604.json"

REQUIRED_CONFIG_FIELDS = [
    "schema_version",
    "max_requests_per_run",
    "default_limit",
    "fixture_batch_size",
    "recommended_cadence",
    "non_matchday_cadence",
    "pre_tournament_cadence",
    "matchweek_cadence",
    "matchday_cadence",
    "match_relative_polling_plan",
    "quota_budget_per_day",
    "system_max_daily_requests",
    "default_target_requests_per_day",
    "hard_stop_at_requests_per_day",
    "fixture_scope",
    "budget_projection",
    "default_target_usage_plan",
    "allowed_odds_observation_fields",
    "opening_closing_proxy_policy",
    "api_provider",
    "observation_only",
    "affects_v4",
]
EXPECTED_WINDOWS = ["T-24h", "T-6h", "T-2h", "T-90m", "T-60m", "T-30m"]
EXPECTED_ALLOWED_ODDS_FIELDS = [
    "first_seen_odds",
    "last_pre_kickoff_odds",
    "odds_observation_delta",
]

REQUIRED_TIMELINE_FIELDS = [
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
    "observation_only",
    "betting_recommendation",
    "affects_v4",
    "snapshot_id",
    "dedupe_key",
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


def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_ls_files(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    result = run_cmd(["git", "ls-files", rel])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def scan_secret_text(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
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

    if not CONFIG.exists():
        failures.append("cadence_config_missing")
        config: dict[str, Any] = {}
    else:
        config = load_json(CONFIG)
    for field in REQUIRED_CONFIG_FIELDS:
        if field not in config:
            failures.append(f"config_field_missing:{field}")
    if config.get("api_provider") != "api-football":
        failures.append("config_api_provider_not_api_football")
    if int(config.get("max_requests_per_run") or 0) > 80:
        failures.append("config_max_requests_per_run_exceeds_80")
    if int(config.get("quota_budget_per_day") or 0) != 7500:
        failures.append(f"config_quota_budget_per_day_unexpected:{config.get('quota_budget_per_day')}")
    if int(config.get("system_max_daily_requests") or 0) > 1500:
        failures.append(f"config_system_max_daily_requests_exceeds_1500:{config.get('system_max_daily_requests')}")
    if int(config.get("default_target_requests_per_day") or 0) > 600:
        failures.append(f"config_default_target_requests_per_day_exceeds_600:{config.get('default_target_requests_per_day')}")
    if int(config.get("hard_stop_at_requests_per_day") or 0) > 6000:
        failures.append(f"config_hard_stop_at_requests_per_day_exceeds_6000:{config.get('hard_stop_at_requests_per_day')}")
    if int(config.get("hard_stop_at_requests_per_day") or 0) <= int(config.get("system_max_daily_requests") or 0):
        failures.append("config_hard_stop_not_above_system_max")

    fixture_scope = config.get("fixture_scope") if isinstance(config.get("fixture_scope"), dict) else {}
    if fixture_scope.get("canonical_total") != 104:
        failures.append(f"config_canonical_total_unexpected:{fixture_scope.get('canonical_total')}")
    if fixture_scope.get("group_stage_total") != 72:
        failures.append(f"config_group_stage_total_unexpected:{fixture_scope.get('group_stage_total')}")
    if fixture_scope.get("knockout_reserved_total") != 32:
        failures.append(f"config_knockout_reserved_total_unexpected:{fixture_scope.get('knockout_reserved_total')}")

    plan = config.get("match_relative_polling_plan") if isinstance(config.get("match_relative_polling_plan"), list) else []
    windows = [item.get("window") for item in plan if isinstance(item, dict)]
    if windows != EXPECTED_WINDOWS:
        failures.append(f"config_polling_windows_unexpected:{windows}")
    for item in plan:
        if not isinstance(item, dict):
            failures.append("config_polling_window_not_object")
            continue
        if item.get("group_stage_request_budget") != 72:
            failures.append(f"config_window_group_budget_unexpected:{item}")
        if item.get("knockout_reserved_request_budget") != 32:
            failures.append(f"config_window_knockout_budget_unexpected:{item}")
        if item.get("full_104_request_budget") != 104:
            failures.append(f"config_window_full_104_budget_unexpected:{item}")

    projection = config.get("budget_projection") if isinstance(config.get("budget_projection"), dict) else {}
    if projection.get("group_stage_six_window_requests") != 432:
        failures.append(f"config_group_six_window_requests_unexpected:{projection.get('group_stage_six_window_requests')}")
    if projection.get("knockout_reserved_six_window_requests") != 192:
        failures.append(f"config_knockout_six_window_requests_unexpected:{projection.get('knockout_reserved_six_window_requests')}")
    if projection.get("full_104_six_window_requests") != 624:
        failures.append(f"config_full_104_six_window_requests_unexpected:{projection.get('full_104_six_window_requests')}")
    if projection.get("requires_batching_or_window_thinning_to_meet_default_target") is not True:
        failures.append("config_default_target_thinning_guard_missing")
    if projection.get("under_system_max_daily_requests") is not True:
        failures.append("config_under_system_max_guard_missing")
    if projection.get("under_hard_stop") is not True:
        failures.append("config_under_hard_stop_guard_missing")

    allowed_fields = config.get("allowed_odds_observation_fields")
    if allowed_fields != EXPECTED_ALLOWED_ODDS_FIELDS:
        failures.append(f"config_allowed_odds_fields_unexpected:{allowed_fields}")
    proxy = config.get("opening_closing_proxy_policy") if isinstance(config.get("opening_closing_proxy_policy"), dict) else {}
    for field in EXPECTED_ALLOWED_ODDS_FIELDS:
        if field not in proxy:
            failures.append(f"config_proxy_policy_missing:{field}")
    for field, expected in {
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4": False,
        "has_native_opening": False,
        "has_native_closing": False,
        "movement_requires_timeline": True,
        "no_money_flow_judgment": True,
    }.items():
        if config.get(field) is not expected:
            failures.append(f"config_{field}_unexpected:{config.get(field)}")
    disabled_claims = set(config.get("disabled_claims") or [])
    for claim in {"steam", "drift", "fund_flow", "true_opening", "true_closing"}:
        if claim not in disabled_claims:
            failures.append(f"config_disabled_claim_missing:{claim}")

    if TIMELINE_DIR.exists():
        shutil.rmtree(TIMELINE_DIR)

    first = run_cmd([sys.executable, str(APPENDER), "--timeline-dir", str(TIMELINE_DIR)])
    if first.returncode != 0:
        failures.append(f"append_first_failed:{first.stderr[-500:]}")
    second = run_cmd([sys.executable, str(APPENDER), "--timeline-dir", str(TIMELINE_DIR)])
    if second.returncode != 0:
        failures.append(f"append_second_failed:{second.stderr[-500:]}")

    first_payload: dict[str, Any] = {}
    second_payload: dict[str, Any] = {}
    try:
        first_payload = json.loads(first.stdout)
        second_payload = json.loads(second.stdout)
    except Exception:
        failures.append("append_output_not_json")

    if int(first_payload.get("records_added") or 0) <= 0 and int(second_payload.get("duplicate_records_skipped") or 0) <= 0:
        failures.append("append_dedupe_not_exercised")
    if int(second_payload.get("duplicate_records_skipped") or 0) <= 0:
        failures.append("append_duplicate_skip_missing")

    monitor = run_cmd([sys.executable, str(MONITOR), "--timeline-dir", str(TIMELINE_DIR)])
    if monitor.returncode != 0:
        failures.append(f"availability_monitor_failed:{monitor.stderr[-500:]}")
    try:
        monitor_payload = json.loads(monitor.stdout)
    except Exception:
        monitor_payload = {}
        failures.append("monitor_output_not_json")

    rows: list[dict[str, str]] = []
    if TIMELINE_CSV.exists():
        with TIMELINE_CSV.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        failures.append("timeline_csv_missing")
    if not TIMELINE_JSONL.exists():
        failures.append("timeline_jsonl_missing")
    if not rows:
        failures.append("timeline_rows_missing")
    else:
        for field in REQUIRED_TIMELINE_FIELDS:
            if field not in rows[0]:
                failures.append(f"timeline_field_missing:{field}")

    dedupe_keys = [r.get("dedupe_key") for r in rows if r.get("dedupe_key")]
    if len(dedupe_keys) != len(set(dedupe_keys)):
        failures.append("timeline_duplicate_dedupe_keys")
    for row in rows:
        checks = {
            "observation_only": "true",
            "betting_recommendation": "false",
            "affects_v4": "false",
            "has_native_opening": "false",
            "has_native_closing": "false",
            "movement_requires_timeline": "true",
        }
        for field, expected in checks.items():
            if str(row.get(field)).lower() != expected:
                failures.append(f"timeline_{field}_unexpected:{row.get(field)}")
                break
        if failures and failures[-1].startswith("timeline_"):
            break

    timeline_text = ""
    for path in [TIMELINE_CSV, TIMELINE_JSONL]:
        if path.exists():
            timeline_text += path.read_text(encoding="utf-8", errors="ignore")
    for token in DISALLOWED_CLAIMS:
        if token in timeline_text:
            failures.append(f"disallowed_claim_in_timeline:{token}")

    tracked_runtime = git_ls_files(TIMELINE_DIR)
    if tracked_runtime:
        failures.append("timeline_runtime_tracked")
    secret_hits = scan_secret_text([TIMELINE_CSV, TIMELINE_JSONL])
    if secret_hits:
        failures.append(f"secret_literal_in_timeline:{secret_hits}")

    if monitor_payload.get("fixtures_with_odds", 0) <= 0:
        failures.append("monitor_fixtures_with_odds_zero")
    if monitor_payload.get("timestamp_coverage", {}).get("record_pct") != 100.0:
        failures.append("monitor_timestamp_coverage_not_100")
    if monitor_payload.get("quota_guard_status") in {"", "UNKNOWN", None}:
        failures.append("monitor_quota_guard_status_missing")

    if any("WARN_ONLY_UNKNOWN_MARKET_RAW_PRESERVED" in str(x) for x in second_payload.get("warn_only", [])):
        warnings.append("WARN_ONLY_UNKNOWN_MARKET_RAW_PRESERVED")

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "warnings": warnings,
        "append_first": first_payload,
        "append_second": second_payload,
        "availability_monitor": monitor_payload,
        "api_budget": {
            "quota_budget_per_day": config.get("quota_budget_per_day"),
            "system_max_daily_requests": config.get("system_max_daily_requests"),
            "default_target_requests_per_day": config.get("default_target_requests_per_day"),
            "hard_stop_at_requests_per_day": config.get("hard_stop_at_requests_per_day"),
            "full_104_six_window_requests": (config.get("budget_projection") or {}).get("full_104_six_window_requests") if isinstance(config.get("budget_projection"), dict) else None,
        },
        "runtime_tracked": bool(tracked_runtime),
        "secret_hits": secret_hits,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
