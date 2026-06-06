#!/usr/bin/env python3
"""Audit V4 price/source fields and selection signal readiness.

This checker is read-only. It verifies that current local V4 artifacts do not
pretend the paper odds proxy is a real price ledger, and that future edge work
depends on saving real price/timing fields from the scan/scout path.
"""
from __future__ import annotations

import glob
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/V4_PRICE_SOURCE_AND_SELECTION_SIGNAL_INVENTORY_20260606.md"
LEDGER = ROOT / "data/runtime/validation/v4_ab_historical_ledger_20260526.json"

ARTIFACT_PATTERNS = {
    "scan_perf": ["data/daily_reports/scan_perf_v4_*.json"],
    "scout": ["data/daily_reports/scout_v4_*.json"],
    "brief_txt": ["data/daily_reports/v4_openclaw_brief_*.txt"],
    "candidate_view": ["data/runtime/status/v4_official_candidate_view_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].json"],
    "validation_replay_dryrun": [
        "data/runtime/validation/*.json",
        "data/runtime/status/*validation*.json",
        "data/runtime/status/*replay*.json",
        "data/runtime/status/*dryrun*.json",
    ],
}

FIELD_GROUPS = {
    "fixture_id": [r"fixture_id"],
    "kickoff_time": [r"kickoff", r"kickoff_time", r"kickoff_local"],
    "selected_scan_time": [r"selected_at", r"scan_time", r"snapshot_time", r"generated_at", r"opening_market_snapshot_time"],
    "odds_bookmaker_market_price": [r"odds", r"bookmaker", r"market", r"price", r"prematch_over_odds", r"opening_.*odds"],
    "line_handicap_ou": [r"line", r"handicap", r"over_under", r"\bou\b", r"opening_.*line", r"prematch_ht_line"],
    "first_last_closing": [r"first_seen", r"last_seen", r"closing", r"last_pre_kickoff"],
    "result_hit": [r"result_hit", r"\bhit\b"],
}

PRICE_KEYS = {
    "prematch_over_odds",
    "prematch_under_odds",
    "opening_ht_ou_over_odds",
    "opening_ht_ou_under_odds",
    "opening_ft_ou_over_odds",
    "opening_ft_ou_under_odds",
    "price",
    "odds",
}


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_dicts(value)


def flatten_keys(obj: Any, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)
            keys.append(full_key)
            if isinstance(value, (dict, list)):
                keys.extend(flatten_keys(value, full_key))
    elif isinstance(obj, list):
        for value in obj[:2000]:
            if isinstance(value, (dict, list)):
                keys.extend(flatten_keys(value, prefix))
    return keys


def is_event_like(row: dict[str, Any]) -> bool:
    return bool(
        {
            "fixture_id",
            "match_id",
            "official_grade",
            "grade",
            "result_hit",
            "home",
            "away",
            "home_team",
            "away_team",
        }
        & set(map(str, row.keys()))
    )


def paths_for(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(ROOT.glob(pattern))
    return sorted(set(paths))


def has_real_price(row: dict[str, Any]) -> bool:
    return any(row.get(key) not in (None, "") for key in PRICE_KEYS)


def scan_artifacts() -> dict[str, Any]:
    compiled = {name: [re.compile(pattern, re.I) for pattern in patterns] for name, patterns in FIELD_GROUPS.items()}
    coverage: dict[str, Any] = {}
    for category, patterns in ARTIFACT_PATTERNS.items():
        files = paths_for(patterns)
        file_hits = {name: 0 for name in FIELD_GROUPS}
        event_hits = {name: 0 for name in FIELD_GROUPS}
        event_like_records = 0
        real_price_records = 0
        examples: dict[str, list[str]] = {name: [] for name in FIELD_GROUPS}

        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name, regexes in compiled.items():
                if any(regex.search(text) for regex in regexes):
                    file_hits[name] += 1
                    if len(examples[name]) < 3:
                        examples[name].append(str(path.relative_to(ROOT)))

            if path.suffix != ".json":
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            for row in iter_dicts(data):
                if not isinstance(row, dict) or not is_event_like(row):
                    continue
                event_like_records += 1
                if has_real_price(row):
                    real_price_records += 1
                joined_keys = "\n".join(list(map(str, row.keys())) + flatten_keys(row))
                for name, regexes in compiled.items():
                    if any(regex.search(joined_keys) for regex in regexes):
                        event_hits[name] += 1

        coverage[category] = {
            "files": len(files),
            "file_hits": file_hits,
            "event_like_records": event_like_records,
            "event_hits": event_hits,
            "real_price_event_records": real_price_records,
            "example_files": examples,
        }
    return coverage


def audit_historical_ab_ledger() -> dict[str, Any]:
    data = load_json(LEDGER) if LEDGER.exists() else {}
    records = data.get("records", []) if isinstance(data, dict) else []
    odds_sources = Counter(str(row.get("odds_source")) for row in records)

    scout_by_fixture: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths_for(ARTIFACT_PATTERNS["scout"]):
        try:
            data = load_json(path)
        except json.JSONDecodeError:
            continue
        for row in iter_dicts(data):
            if isinstance(row, dict) and row.get("fixture_id") is not None:
                scout_by_fixture[str(row.get("fixture_id"))].append(row)

    joined = 0
    joined_real_price = 0
    joined_snapshot_time = 0
    joined_first_last_closing = 0
    for row in records:
        fixture_id = str(row.get("fixture_id"))
        scout_rows = scout_by_fixture.get(fixture_id, [])
        if scout_rows:
            joined += 1
        if any(has_real_price(candidate) for candidate in scout_rows):
            joined_real_price += 1
        if any(candidate.get("opening_market_snapshot_time") for candidate in scout_rows):
            joined_snapshot_time += 1
        if any(any(key in candidate for key in ("first_seen", "last_seen", "closing", "last_pre_kickoff_odds")) for candidate in scout_rows):
            joined_first_last_closing += 1

    return {
        "records": len(records),
        "odds_sources": dict(odds_sources),
        "paper_default_records": odds_sources.get("paper_default_0.80", 0),
        "real_odds_source_records": sum(count for source, count in odds_sources.items() if "paper" not in source.lower()),
        "joined_to_scout_by_fixture": joined,
        "joined_real_price_records": joined_real_price,
        "joined_snapshot_time_records": joined_snapshot_time,
        "joined_first_last_closing_records": joined_first_last_closing,
    }


def main() -> int:
    coverage = scan_artifacts()
    historical = audit_historical_ab_ledger()
    doc_text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = [
        path
        for path in staged
        if path.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/", "data/runtime/", "data/cache/"))
        or re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", path)
    ]

    checks = {
        "doc_exists": DOC.exists(),
        "historical_ledger_exists": LEDGER.exists(),
        "historical_ledger_uses_only_paper_odds": historical.get("records", 0) >= 140
        and historical.get("paper_default_records") == historical.get("records")
        and historical.get("real_odds_source_records") == 0,
        "historical_join_has_no_real_price": historical.get("joined_real_price_records") == 0,
        "historical_join_has_no_snapshot_time": historical.get("joined_snapshot_time_records") == 0,
        "historical_join_has_no_first_last_closing": historical.get("joined_first_last_closing_records") == 0,
        "scout_contains_some_market_price_fields": coverage.get("scout", {}).get("real_price_event_records", 0) > 0,
        "candidate_view_has_no_real_price_events": coverage.get("candidate_view", {}).get("real_price_event_records", 0) == 0,
        "candidate_view_has_no_first_last_closing": coverage.get("candidate_view", {}).get("event_hits", {}).get("first_last_closing", 0) == 0,
        "doc_states_no_fake_edge": all(
            phrase in doc_text
            for phrase in [
                "Do not use paper odds as real price evidence",
                "historical official A/B cannot be rebuilt into a complete true price ledger",
                "future scan/scout must persist price timing fields",
                "historical form is auxiliary only",
            ]
        ),
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_price_source_selection_signal_inventory.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "price_sources_found": {
            "historical_ab_odds_source": historical.get("odds_sources"),
            "scout_has_prematch_or_opening_price_fields": checks["scout_contains_some_market_price_fields"],
            "candidate_view_has_real_price_events": coverage.get("candidate_view", {}).get("real_price_event_records", 0),
        },
        "field_coverage": coverage,
        "historical_ab_join": historical,
        "historical_ledger_possible": "PARTIAL_ONLY_NOT_COMPLETE_TRUE_PRICE_LEDGER",
        "missing_fields": [
            "official candidate_view real price fields",
            "first_seen odds",
            "last_seen odds",
            "last_pre_kickoff odds",
            "native closing odds",
            "event-level selected_at for historical official ledger",
            "bookmaker/market/line persisted into validation ledger",
        ],
        "new_selection_signals": [
            "strength_gap",
            "market_confirmation",
            "price_quality",
            "data_quality",
            "lineup_injury_fatigue_travel_context",
            "historical_form_auxiliary_only",
        ],
        "forbidden_staged": forbidden_staged,
        "live_api_called": False,
        "scan_executed": False,
        "official_grade_changed": False,
        "pending_written": False,
        "qq_sent": False,
        "cron_or_launchd_modified": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
