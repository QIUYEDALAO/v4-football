#!/usr/bin/env python3
"""Build the V4 official A/B league performance ledger.

This is a read-only aggregation layer. It never changes validation history,
candidate grades, pending records, live bets, QQ routes, scans, or cron.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "data/runtime/validation"
HISTORICAL_LEDGER_LATEST = VALIDATION / "v4_ab_historical_ledger_latest.json"
VALIDATION_20260531 = VALIDATION / "v4_official_ab_validation_review_20260531.json"
OUTPUT_JSON = VALIDATION / "v4_league_performance_ledger_latest.json"
OUTPUT_CSV = VALIDATION / "v4_league_performance_ledger_latest.csv"
LOCAL_TZ = timezone(timedelta(hours=8))

CSV_FIELDS = [
    "league", "normalized_league", "sample_total", "validated_count",
    "pending_count", "hit_count", "miss_count", "hit_rate", "A_count",
    "A_hit_count", "A_hit_rate", "B_count", "B_hit_count", "B_hit_rate",
    "rescue_count", "rescue_hit_count", "rescue_hit_rate",
    "non_rescue_count", "non_rescue_hit_count", "non_rescue_hit_rate",
    "last_seen_date", "first_seen_date", "last_7d_count", "last_7d_hit_rate",
    "last_30d_count", "last_30d_hit_rate", "confidence_level", "sample_tag", "trust_tag",
    "warning_flags", "source_files", "data_quality_status",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def normalize_league(value: Any) -> str:
    name = " ".join(str(value or "").strip().split())
    return name or "UNKNOWN"


def safe_rate(hits: int, total: int) -> float:
    return round(hits / total, 6) if total > 0 else 0.0


def confidence_level(validated_count: int) -> str:
    if validated_count >= 50:
        return "HIGH"
    if validated_count >= 20:
        return "MEDIUM"
    if validated_count >= 10:
        return "LOW"
    return "OBSERVE_ONLY"


def sample_tag(validated_count: int, pending_count: int) -> str:
    if validated_count == 0 and pending_count > 0:
        return "PENDING_ONLY"
    if validated_count >= 20:
        return "ENOUGH_SAMPLE"
    if validated_count >= 10:
        return "LOW_SAMPLE"
    if validated_count >= 5:
        return "VERY_LOW_SAMPLE"
    return "SINGLE_OR_TINY_SAMPLE"


def find_historical_ledger() -> tuple[Path | None, str]:
    if HISTORICAL_LEDGER_LATEST.exists():
        return HISTORICAL_LEDGER_LATEST, "OK"
    candidates = [
        path for path in VALIDATION.glob("v4_ab_historical_ledger_*.json")
        if not path.name.startswith("v4_league_performance_ledger_")
    ]
    if not candidates:
        return None, "HISTORICAL_LEDGER_MISSING_WARN_ONLY"

    def sort_key(path: Path) -> tuple[str, float]:
        suffix = path.stem.rsplit("_", 1)[-1]
        date_key = suffix if len(suffix) == 8 and suffix.isdigit() else ""
        return date_key, path.stat().st_mtime

    return sorted(candidates, key=sort_key)[-1], "OK"


def trust_tag(validated_count: int, hit_rate: float, pending_count: int = 0, data_gap: bool = False) -> str:
    if data_gap:
        return "DATA_GAP"
    if validated_count == 0 and pending_count > 0:
        return "PENDING_ONLY"
    if validated_count < 5:
        return "DO_NOT_CONCLUDE"
    if validated_count < 10:
        return "LOW_SAMPLE_ONLY"
    if validated_count < 20:
        return "OBSERVE"
    if hit_rate >= 0.60:
        return "KEEP"
    if hit_rate >= 0.55:
        return "WATCH"
    return "LOW_TRUST_ALERT"


def is_shadow_or_dryrun_only(record: dict[str, Any]) -> bool:
    markers = " ".join(
        str(record.get(key) or "")
        for key in ("record_type", "source", "source_window", "mode", "scope")
    ).lower()
    return "shadow-only" in markers or "shadow_only" in markers or "dryrun" in markers


def fixture_state(record: dict[str, Any]) -> str:
    status = " ".join(
        str(record.get(key) or "")
        for key in ("status", "fixture_status", "result_status", "excluded_reason")
    ).lower()
    if any(token in status for token in ("postpon", "pending", "void", "abandon", "result_missing", "not_settled")):
        return "PENDING"
    if record.get("settled") is True and isinstance(record.get("result_hit"), bool):
        return "VALIDATED"
    return "PENDING"


def review_rows(review: dict[str, Any]) -> list[dict[str, Any]]:
    groups = [
        ("enriched_hits", "hit_list", True, True),
        ("enriched_misses", "miss_list", False, True),
        ("enriched_pending", "pending_list", None, False),
    ]
    rows: list[dict[str, Any]] = []
    for enriched_key, fallback_key, result_hit, settled in groups:
        values = review.get(enriched_key) or review.get(fallback_key) or []
        if not isinstance(values, list):
            continue
        for raw in values:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            row.update(
                {
                    "date": "2026-05-31",
                    "scan_date": "20260531",
                    "official_recommendation": True,
                    "result_hit": result_hit,
                    "settled": settled,
                    "pending_retry": not settled,
                    "source_file": VALIDATION_20260531.name,
                    "source_window": "official_ab_validation_review",
                }
            )
            rows.append(row)
    return rows


def include_record(
    record: dict[str, Any],
    audit: dict[str, int],
) -> bool:
    grade = str(record.get("grade") or "").upper()
    if grade not in {"A", "B"} or record.get("official_recommendation") is not True:
        audit["non_official_excluded_count"] += 1
        return False
    if is_shadow_or_dryrun_only(record):
        audit["shadow_dryrun_excluded_count"] += 1
        return False
    return True


def record_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("fixture_id") or ""),
        str(record.get("date") or ""),
        str(record.get("grade") or "").upper(),
    )


def normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return ""


def max_record_date(records: list[dict[str, Any]]) -> str:
    dates = [normalize_date(row.get("date") or row.get("scan_date")) for row in records]
    dates = [date for date in dates if date]
    return max(dates) if dates else ""


def recent_stats(records: list[dict[str, Any]], days: int, anchor_date: str) -> tuple[int, float]:
    if not anchor_date:
        return 0, 0.0
    try:
        anchor = datetime.strptime(anchor_date, "%Y-%m-%d")
    except ValueError:
        return 0, 0.0
    cutoff = (anchor - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = [row for row in records if str(row.get("date") or "") >= cutoff]
    return len(rows), safe_rate(sum(1 for row in rows if row.get("result_hit") is True), len(rows))


def aggregate_leagues(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, str]:
    by_league: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        normalized_date = normalize_date(record.get("date") or record.get("scan_date"))
        if normalized_date:
            record = dict(record)
            record["date"] = normalized_date
        by_league[normalize_league(record.get("league"))].append(record)

    trend_anchor_date = max_record_date([
        record for records_for_league in by_league.values()
        for record in records_for_league
        if fixture_state(record) == "VALIDATED"
    ])
    pending_denominator_excluded = 0
    league_rows: list[dict[str, Any]] = []
    for league, league_records in sorted(by_league.items()):
        validated = [record for record in league_records if fixture_state(record) == "VALIDATED"]
        pending = [record for record in league_records if fixture_state(record) != "VALIDATED"]
        pending_denominator_excluded += len(pending)

        hits = sum(1 for record in validated if record.get("result_hit") is True)
        misses = sum(1 for record in validated if record.get("result_hit") is False)
        hit_rate = safe_rate(hits, len(validated))
        a_rows = [record for record in validated if str(record.get("grade") or "").upper() == "A"]
        b_rows = [record for record in validated if str(record.get("grade") or "").upper() == "B"]
        rescue_rows = [
            record for record in validated
            if "B_FLOOR" in str(record.get("official_reason") or record.get("reason") or "").upper()
        ]
        non_rescue_rows = [record for record in validated if record not in rescue_rows]
        dates = sorted(str(record.get("date") or "") for record in league_records if record.get("date"))
        last_7d_count, last_7d_rate = recent_stats(validated, 7, trend_anchor_date)
        last_30d_count, last_30d_rate = recent_stats(validated, 30, trend_anchor_date)
        data_gap = league == "UNKNOWN"
        tag = trust_tag(len(validated), hit_rate, len(pending), data_gap)
        warnings: list[str] = []
        if tag in {"LOW_TRUST_ALERT", "LOW_SAMPLE_ONLY", "DO_NOT_CONCLUDE", "DATA_GAP", "PENDING_ONLY"}:
            warnings.append(tag)
        if pending and len(pending) > len(validated):
            warnings.append("HIGH_PENDING_RATIO")
        if not warnings:
            warnings.append("NONE")
        sources = sorted(
            {
                str(record.get("source_file") or record.get("source") or "UNKNOWN")
                for record in league_records
            }
        )
        league_rows.append(
            {
                "league": league,
                "normalized_league": league,
                "sample_total": len(league_records),
                "validated_count": len(validated),
                "pending_count": len(pending),
                "hit_count": hits,
                "miss_count": misses,
                "hit_rate": hit_rate,
                "A_count": len(a_rows),
                "A_hit_count": sum(1 for record in a_rows if record.get("result_hit") is True),
                "A_hit_rate": safe_rate(sum(1 for record in a_rows if record.get("result_hit") is True), len(a_rows)),
                "B_count": len(b_rows),
                "B_hit_count": sum(1 for record in b_rows if record.get("result_hit") is True),
                "B_hit_rate": safe_rate(sum(1 for record in b_rows if record.get("result_hit") is True), len(b_rows)),
                "rescue_count": len(rescue_rows),
                "rescue_hit_count": sum(1 for record in rescue_rows if record.get("result_hit") is True),
                "rescue_hit_rate": safe_rate(sum(1 for record in rescue_rows if record.get("result_hit") is True), len(rescue_rows)),
                "non_rescue_count": len(non_rescue_rows),
                "non_rescue_hit_count": sum(1 for record in non_rescue_rows if record.get("result_hit") is True),
                "non_rescue_hit_rate": safe_rate(sum(1 for record in non_rescue_rows if record.get("result_hit") is True), len(non_rescue_rows)),
                "first_seen_date": dates[0] if dates else "",
                "last_seen_date": dates[-1] if dates else "",
                "last_7d_count": last_7d_count,
                "last_7d_hit_rate": last_7d_rate,
                "last_30d_count": last_30d_count,
                "last_30d_hit_rate": last_30d_rate,
                "confidence_level": confidence_level(len(validated)),
                "sample_tag": sample_tag(len(validated), len(pending)),
                "trust_tag": tag,
                "warning_flags": warnings,
                "source_files": sources,
                "data_quality_status": "DATA_GAP" if data_gap else ("PENDING_ONLY" if tag == "PENDING_ONLY" else "OK"),
            }
        )
    league_rows.sort(key=lambda row: (-row["validated_count"], row["normalized_league"]))
    return league_rows, pending_denominator_excluded, trend_anchor_date


def build() -> dict[str, Any]:
    historical_path, historical_status = find_historical_ledger()
    historical = load_json(historical_path) if historical_path else {}
    review = load_json(VALIDATION_20260531)
    historical_rows = historical.get("records") or []
    review_candidates = review_rows(review)
    audit = {
        "historical_input_count": len(historical_rows),
        "review_input_count": len(review_candidates),
        "historical_included_count": 0,
        "review_included_count": 0,
        "deduplicated_count": 0,
        "non_official_excluded_count": 0,
        "official_outside57_review_included_count": 0,
        "shadow_dryrun_excluded_count": 0,
        "pending_denominator_excluded_count": 0,
    }

    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    review_merged: list[dict[str, Any]] = []
    for source_rows, source_name in (
        (historical_rows, "historical"),
        (review_candidates, "review"),
    ):
        for record in source_rows:
            if not isinstance(record, dict):
                audit["non_official_excluded_count"] += 1
                continue
            if not include_record(record, audit):
                continue
            key = record_key(record)
            if key in seen:
                audit["deduplicated_count"] += 1
                continue
            seen.add(key)
            merged.append(dict(record))
            if source_name == "review":
                review_merged.append(dict(record))
                if bool(record.get("outside57")) or str(record.get("source_group") or "").upper() == "OUTSIDE_57":
                    audit["official_outside57_review_included_count"] += 1
            audit[f"{source_name}_included_count"] += 1

    league_rows, pending_excluded, trend_anchor_date = aggregate_leagues(merged)
    baseline_rows, _, baseline_trend_anchor_date = aggregate_leagues(review_merged)
    audit["pending_denominator_excluded_count"] = pending_excluded
    return {
        "schema_version": "v4.league_performance_ledger.v1",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "source_ledger": historical_path.name if historical_path else "NOT_FOUND",
        "source_ledger_resolved": str(historical_path) if historical_path else "NOT_FOUND",
        "historical_ledger_status": historical_status,
        "source_validation_review": VALIDATION_20260531.name,
        "trend_anchor_date": trend_anchor_date or "DATA_MISSING",
        "official_only": True,
        "C_SKIP_excluded": True,
        "shadow_dryrun_excluded": True,
        "outside57_policy": "locked official A/B reviews are included; no outside57-only source is read",
        "pending_excluded_from_denominator": True,
        "postponed_excluded_from_denominator": True,
        "void_abandoned_result_missing_excluded_from_denominator": True,
        "league_count": len(league_rows),
        "total_validated": sum(row["validated_count"] for row in league_rows),
        "total_pending": sum(row["pending_count"] for row in league_rows),
        "keep_count": sum(row["trust_tag"] == "KEEP" for row in league_rows),
        "watch_count": sum(row["trust_tag"] == "WATCH" for row in league_rows),
        "low_trust_count": sum(row["trust_tag"] == "LOW_TRUST_ALERT" for row in league_rows),
        "low_sample_count": sum(row["trust_tag"] in {"LOW_SAMPLE_ONLY", "DO_NOT_CONCLUDE", "PENDING_ONLY"} for row in league_rows),
        "do_not_conclude_count": sum(row["trust_tag"] == "DO_NOT_CONCLUDE" for row in league_rows),
        "pending_only_count": sum(row["sample_tag"] == "PENDING_ONLY" for row in league_rows),
        "data_gap_count": sum(row["trust_tag"] == "DATA_GAP" for row in league_rows),
        "observe_count": sum(row["trust_tag"] == "OBSERVE" for row in league_rows),
        "audit": audit,
        "leagues": league_rows,
        "baseline_20260531": {
            "validated_count": sum(row["validated_count"] for row in baseline_rows),
            "pending_count": sum(row["pending_count"] for row in baseline_rows),
            "trend_anchor_date": baseline_trend_anchor_date or "DATA_MISSING",
            "leagues": baseline_rows,
        },
    }


def write_outputs(payload: dict[str, Any]) -> None:
    VALIDATION.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in payload["leagues"]:
            csv_row = dict(row)
            csv_row["warning_flags"] = "|".join(row["warning_flags"])
            csv_row["source_files"] = "|".join(row["source_files"])
            writer.writerow({key: csv_row.get(key, "") for key in CSV_FIELDS})


def main() -> int:
    payload = build()
    write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(OUTPUT_JSON),
                "csv": str(OUTPUT_CSV),
                "league_count": payload["league_count"],
                "total_validated": payload["total_validated"],
                "total_pending": payload["total_pending"],
                "audit": payload["audit"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
