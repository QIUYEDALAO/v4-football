#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_BASE = ROOT / "data/runtime/v3_worldcup/odds_snapshot_dryrun"
DEFAULT_TIMELINE_DIR = ROOT / "data/runtime/v3_worldcup/odds_timeline"
STATUS_OUT = ROOT / "data/runtime/status/v3_worldcup_odds_timeline_append_status_20260604.json"

TIMELINE_FIELDS = [
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
    "scoring_changed",
    "snapshot_id",
    "dedupe_key",
    "appended_at",
]

REQUIRED_INPUT_FIELDS = [
    "snapshot_time",
    "api_update_time",
    "fixture_id",
    "bookmaker",
    "market_type",
    "market_name_raw",
    "selection",
    "line",
    "odds",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_latest_snapshot_json(base: Path) -> Path:
    candidates = sorted(base.rglob("v3_worldcup_odds_snapshot_dryrun_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        if "checker_dryrun" in path.parts or "quota_guard_test" in path.parts:
            continue
        return path
    raise FileNotFoundError(f"no live snapshot json found under {base}")


def snapshot_id_from_row(row: dict[str, Any]) -> str:
    raw = str(row.get("snapshot_time") or "").strip()
    if not raw:
        raw = now_utc()
    value = re.sub(r"[^0-9A-Za-z]+", "", raw)
    return value[:32] or hashlib.sha1(raw.encode()).hexdigest()[:16]


def build_dedupe_key(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("fixture_id") or ""),
        str(row.get("bookmaker") or ""),
        str(row.get("market_type") or ""),
        str(row.get("market_name_raw") or ""),
        str(row.get("selection") or ""),
        str(row.get("line") or ""),
        str(row.get("odds") or ""),
        str(row.get("api_update_time") or ""),
        str(row.get("snapshot_id") or snapshot_id_from_row(row)),
    ]
    return hashlib.sha1("\u001f".join(parts).encode("utf-8")).hexdigest()


def normalize_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def normalize_row(row: dict[str, Any], appended_at: str) -> dict[str, Any]:
    clean = {field: row.get(field, "") for field in TIMELINE_FIELDS}
    clean["snapshot_id"] = str(row.get("snapshot_id") or snapshot_id_from_row(row))
    clean["dedupe_key"] = str(row.get("dedupe_key") or build_dedupe_key(clean))
    clean["appended_at"] = appended_at
    clean["is_current_snapshot"] = normalize_bool(row.get("is_current_snapshot"), True)
    clean["has_native_opening"] = normalize_bool(row.get("has_native_opening"), False)
    clean["has_native_closing"] = normalize_bool(row.get("has_native_closing"), False)
    clean["movement_requires_timeline"] = normalize_bool(row.get("movement_requires_timeline"), True)
    clean["observation_only"] = normalize_bool(row.get("observation_only"), True)
    clean["betting_recommendation"] = normalize_bool(row.get("betting_recommendation"), False)
    clean["affects_v4"] = normalize_bool(row.get("affects_v4"), False)
    clean["scoring_changed"] = normalize_bool(row.get("scoring_changed"), False)
    return clean


def load_snapshot_records(snapshot_json: Path | None, snapshot_csv: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any], Path]:
    if snapshot_json:
        payload = json.loads(snapshot_json.read_text(encoding="utf-8"))
        records = payload.get("records") or []
        if not isinstance(records, list):
            raise ValueError(f"snapshot records is not a list: {snapshot_json}")
        return [r for r in records if isinstance(r, dict)], payload, snapshot_json
    if snapshot_csv:
        with snapshot_csv.open(encoding="utf-8", newline="") as f:
            rows = [dict(r) for r in csv.DictReader(f)]
        return rows, {"source_csv": str(snapshot_csv)}, snapshot_csv
    latest = find_latest_snapshot_json(SNAPSHOT_BASE)
    payload = json.loads(latest.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    if not isinstance(records, list):
        raise ValueError(f"snapshot records is not a list: {latest}")
    return [r for r in records if isinstance(r, dict)], payload, latest


def read_existing_keys(jsonl_path: Path) -> set[str]:
    keys: set[str] = set()
    if not jsonl_path.exists():
        return keys
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            key = row.get("dedupe_key")
            if key:
                keys.add(str(key))
    return keys


def write_timeline(csv_path: Path, jsonl_path: Path, rows: list[dict[str, Any]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as f:
            existing = [dict(r) for r in csv.DictReader(f)]
    all_rows = existing + rows
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TIMELINE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    with jsonl_path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append V3 World Cup odds snapshot rows into a deduped timeline")
    parser.add_argument("--snapshot-json", default="")
    parser.add_argument("--snapshot-csv", default="")
    parser.add_argument("--timeline-dir", default=str(DEFAULT_TIMELINE_DIR))
    args = parser.parse_args()

    snapshot_json = Path(args.snapshot_json) if args.snapshot_json else None
    snapshot_csv = Path(args.snapshot_csv) if args.snapshot_csv else None
    records, payload, source_path = load_snapshot_records(snapshot_json, snapshot_csv)
    timeline_dir = Path(args.timeline_dir)
    csv_path = timeline_dir / "v3_worldcup_odds_timeline.csv"
    jsonl_path = timeline_dir / "v3_worldcup_odds_timeline.jsonl"
    existing_keys = read_existing_keys(jsonl_path)
    appended_at = now_utc()
    added: list[dict[str, Any]] = []
    duplicate_records_skipped = 0
    warn_only: list[str] = []

    for raw in records:
        row = normalize_row(raw, appended_at)
        missing = [field for field in REQUIRED_INPUT_FIELDS if row.get(field) in {"", None}]
        if "odds" in missing:
            warn_only.append("WARN_ONLY_ODDS_MISSING")
        if row.get("market_type") in {"ASIAN_HANDICAP", "GOALS_OVER_UNDER"} and row.get("line") in {"", None}:
            warn_only.append("WARN_ONLY_LINE_MISSING")
        if row.get("market_type") == "OTHER_MARKET":
            warn_only.append("WARN_ONLY_UNKNOWN_MARKET_RAW_PRESERVED")
        key = str(row["dedupe_key"])
        if key in existing_keys:
            duplicate_records_skipped += 1
            continue
        existing_keys.add(key)
        added.append(row)

    write_timeline(csv_path, jsonl_path, added)
    summary = {
        "generated_at": appended_at,
        "conclusion": "PASS",
        "source_snapshot": str(source_path),
        "timeline_csv": str(csv_path),
        "timeline_jsonl": str(jsonl_path),
        "input_records": len(records),
        "records_added": len(added),
        "duplicate_records_skipped": duplicate_records_skipped,
        "total_dedupe_keys_after": len(existing_keys),
        "snapshot_status": payload.get("status"),
        "quota_guard_status": payload.get("coverage_report", {}).get("quota_guard_status") or payload.get("status"),
        "warn_only": sorted(set(warn_only)),
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4": False,
        "has_native_opening": False,
        "has_native_closing": False,
        "movement_requires_timeline": True,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
