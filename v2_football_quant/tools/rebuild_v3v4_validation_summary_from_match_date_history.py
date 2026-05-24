#!/usr/bin/env python3
"""Rebuild V3/V4 dashboard validation summary from trusted match_date history.

This script is deliberately no-API and display-summary only. It does not infer
hit rates from the daily brief and does not modify raw attribution artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
REPORTS = ROOT / "data/daily_reports"
ARCHIVE = ROOT / "data/v4_archive"
TZ = timezone(timedelta(hours=8))
ALLOWED_MODEL_RESULTS = {"MODEL_HIT", "MODEL_MISS", "MODEL_SKIP_CORRECT", "MODEL_SKIP_BACKFIRE", "RESULT_UNKNOWN", "MODEL_RESULT_UNKNOWN"}
TRUSTED_RESULTS = {"MODEL_HIT", "MODEL_MISS"}
ACTIVE_GRADES = {"A", "B"}


def now() -> str:
    return datetime.now(TZ).isoformat()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def norm_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def build_scout_index() -> dict[int, dict[str, Any]]:
    index: dict[int, dict[str, Any]] = {}
    for path in sorted(REPORTS.glob("scout_v4_*.json")):
        if "raw_dump" in path.name:
            continue
        rows = load_json(path, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            fid = row.get("fixture_id")
            try:
                fid_i = int(fid)
            except Exception:
                continue
            match_date = norm_date(row.get("match_date") or row.get("date"))
            kickoff = row.get("kickoff") or row.get("kickoff_time")
            index[fid_i] = {
                "fixture_id": fid_i,
                "match_date": match_date,
                "date": norm_date(row.get("date")),
                "scan_date": norm_date(row.get("scan_date")),
                "kickoff": kickoff,
                "source_file": rel(path),
            }
    return index


def source_inventory() -> list[dict[str, Any]]:
    patterns = [
        (STATUS, "v3v4_validation_summary_*.json"),
        (STATUS, "v4_validation_*.json"),
        (STATUS, "v4_result_attribution_*.json"),
        (STATUS, "v4_result_attribution_*.jsonl"),
        (ARCHIVE, "v4_result_attribution_*.jsonl"),
        (REPORTS, "v4_ht_recommend_validation_*.json"),
        (REPORTS, "v4_review_structured_*.json"),
        (REPORTS, "v4_review_full_*.txt"),
        (STATUS, "v4_postmatch_review_*.json"),
        (STATUS, "v4_review_route_marker_*.json"),
    ]
    out: list[dict[str, Any]] = []
    for base, pattern in patterns:
        for path in sorted(base.glob(pattern)):
            if "pre_repair_marked_stale" in path.name:
                category = "STALE_SCAN_DATE_POLLUTED"
                reason = "explicit stale marker for pre-repair validation summary"
            elif path.name.startswith("v3v4_validation_summary_"):
                category = "STALE_SCAN_DATE_POLLUTED"
                reason = "active summary was intentionally marked stale after scout date repair"
            elif path.suffix == ".jsonl" and "v4_result_attribution" in path.name:
                category = "TRUSTED_MATCH_DATE_READY"
                reason = "local attribution history; fixture_id can be reconnected to repaired scout match_date"
            elif "v4_validation_raw_records" in path.name:
                category = "TRUSTED_MATCH_DATE_READY"
                reason = "raw validation records include match_date but are audit source only"
            elif "v4_ht_recommend_validation" in path.name:
                category = "MISSING_MATCH_DATE_CAN_BACKFILL"
                reason = "validation artifact may require fixture_id to repaired scout match_date backfill"
            elif "v4_review_structured" in path.name:
                category = "DO_NOT_USE"
                reason = "review/report artifact is not the primary hit-rate source for recovery"
            elif "v4_review_full" in path.name:
                category = "DO_NOT_USE"
                reason = "text report is not a hit-rate source"
            elif "route_marker" in path.name:
                category = "DO_NOT_USE"
                reason = "route marker is delivery metadata, not validation evidence"
            elif "postmatch_review" in path.name:
                category = "API_DISABLED_UNRESOLVED"
                reason = "postmatch review planning/status only unless structured attribution rows exist"
            else:
                category = "DO_NOT_USE"
                reason = "not an active validation recovery source"
            out.append({
                "path": rel(path),
                "category": category,
                "size": path.stat().st_size,
                "sha256": sha(path),
                "reason": reason,
            })
    return out


def classify_record(row: dict[str, Any], source_file: str, scout_index: dict[int, dict[str, Any]]) -> dict[str, Any]:
    fid_raw = row.get("fixture_id")
    try:
        fid = int(fid_raw)
    except Exception:
        return {"classification": "MISSING_MATCH_DATE_BLOCKED", "reason": "missing fixture_id", "source_file": source_file}
    scout = scout_index.get(fid)
    grade = row.get("pre_grade") or row.get("grade")
    result = row.get("model_result") or row.get("result_status")
    match_date = scout.get("match_date") if scout else norm_date(row.get("match_date"))
    if not match_date:
        return {"classification": "MISSING_MATCH_DATE_BLOCKED", "reason": "fixture_id cannot reconnect to repaired scout match_date", "fixture_id": fid, "source_file": source_file}
    if grade == "C":
        return {"classification": "DO_NOT_USE", "reason": "C deprecated and excluded from active validation", "fixture_id": fid, "grade": grade, "match_date": match_date, "source_file": source_file}
    if grade == "SKIP":
        return {"classification": "DO_NOT_USE", "reason": "SKIP excluded from A/B validation", "fixture_id": fid, "grade": grade, "match_date": match_date, "source_file": source_file}
    if grade not in ACTIVE_GRADES:
        return {"classification": "MISSING_MATCH_DATE_BLOCKED", "reason": "unknown active grade", "fixture_id": fid, "grade": grade, "match_date": match_date, "source_file": source_file}
    if result not in ALLOWED_MODEL_RESULTS:
        return {"classification": "MISSING_MATCH_DATE_BLOCKED", "reason": "unknown model_result", "fixture_id": fid, "grade": grade, "model_result": result, "match_date": match_date, "source_file": source_file}
    base = {
        "fixture_id": fid,
        "grade": grade,
        "model_result": result,
        "match_date": match_date,
        "source_file": source_file,
        "source_date": norm_date(row.get("date")),
        "home": row.get("home"),
        "away": row.get("away"),
    }
    if result in TRUSTED_RESULTS:
        return {**base, "classification": "TRUSTED_MATCH_DATE_READY", "reason": "fixture_id matched repaired scout match_date and result is resolved"}
    return {**base, "classification": "API_DISABLED_UNRESOLVED", "reason": "local row exists but result is unresolved/API-disabled or non-A/B hit-rate result"}


def collect_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scout_index = build_scout_index()
    all_records: list[dict[str, Any]] = []
    for path in sorted(ARCHIVE.glob("v4_result_attribution_*.jsonl")):
        for row in load_jsonl(path):
            all_records.append(classify_record(row, rel(path), scout_index))
    counters = Counter(r.get("classification") for r in all_records)
    blocked_reasons = Counter(r.get("reason") for r in all_records if r.get("classification") == "MISSING_MATCH_DATE_BLOCKED")
    audit = {
        "generated_at": now(),
        "total_records": len(all_records),
        "trusted_records": counters.get("TRUSTED_MATCH_DATE_READY", 0),
        "stale_records": counters.get("STALE_SCAN_DATE_POLLUTED", 0),
        "recoverable_records": counters.get("TRUSTED_MATCH_DATE_READY", 0),
        "blocked_records": counters.get("MISSING_MATCH_DATE_BLOCKED", 0),
        "unknown_records": counters.get("API_DISABLED_UNRESOLVED", 0),
        "trusted_source_files": sorted({r["source_file"] for r in all_records if r.get("classification") == "TRUSTED_MATCH_DATE_READY"}),
        "blocked_reason_counts": dict(blocked_reasons),
        "classification_counts": dict(counters),
        "sample_trusted_records": [r for r in all_records if r.get("classification") == "TRUSTED_MATCH_DATE_READY"][:10],
        "sample_blocked_records": [r for r in all_records if r.get("classification") == "MISSING_MATCH_DATE_BLOCKED"][:10],
    }
    return all_records, audit


def metric(rows: list[dict[str, Any]], grade: str | None = None) -> dict[str, Any]:
    subset = [r for r in rows if r.get("classification") == "TRUSTED_MATCH_DATE_READY"]
    if grade:
        subset = [r for r in subset if r.get("grade") == grade]
    hit = sum(1 for r in subset if r.get("model_result") == "MODEL_HIT")
    miss = sum(1 for r in subset if r.get("model_result") == "MODEL_MISS")
    settled = hit + miss
    rate = (hit / settled) if settled else None
    return {
        "count": settled,
        "hit": hit,
        "miss": miss,
        "unknown": 0,
        "settled": settled,
        "hit_rate": rate,
        "display_rate": "N/A" if rate is None else f"{rate * 100:.1f}%",
    }


def empty_metric(reason: str) -> dict[str, Any]:
    return {"count": 0, "hit": 0, "miss": 0, "unknown": 0, "settled": 0, "hit_rate": None, "display_rate": "N/A", "reason": reason}


def build_summary(date: str, records: list[dict[str, Any]], audit: dict[str, Any], *, write: bool) -> dict[str, Any]:
    target = datetime.strptime(date, "%Y%m%d").date()
    yesterday_date = (target - timedelta(days=1)).isoformat()
    yesterday_yyyymmdd = yesterday_date.replace("-", "")
    trusted = [r for r in records if r.get("classification") == "TRUSTED_MATCH_DATE_READY"]
    yesterday = [r for r in trusted if r.get("match_date") == yesterday_date]
    source_files = sorted(audit.get("trusted_source_files", []))
    source_hash = hashlib.sha256("|".join(source_files + [date, yesterday_yyyymmdd, str(audit.get("trusted_records")), str(audit.get("unknown_records"))]).encode()).hexdigest()
    unresolved = [r for r in records if r.get("classification") == "API_DISABLED_UNRESOLVED"]
    y_has = bool(yesterday)
    c_has = bool(trusted)
    script_path = STATUS / f"v4_script_validation_summary_{date}.json"
    script_summary = load_json(script_path, {}) if script_path.exists() else {}
    result = {
        "schema_version": "v3v4_validation_summary.match_date_history.v1",
        "phase": "V4-MATCH-DATE-VALIDATION-HISTORY-RECOVERY-20260523",
        "generated_at": now(),
        "date": date,
        "dashboard_date": date,
        "yesterday_validation_target_date": yesterday_yyyymmdd,
        "dashboard_active": {
            "yesterday": {
                "label": f"match_date {yesterday_date}",
                "A": metric(yesterday, "A") if y_has else empty_metric("no_trusted_history_for_yesterday_or_api_disabled"),
                "B": metric(yesterday, "B") if y_has else empty_metric("no_trusted_history_for_yesterday_or_api_disabled"),
                "A_plus_B": metric(yesterday) if y_has else empty_metric("no_trusted_history_for_yesterday_or_api_disabled"),
            },
            "cumulative": {
                "label": "trusted match_date attribution history",
                "A": metric(trusted, "A") if c_has else empty_metric("no_trusted_history"),
                "B": metric(trusted, "B") if c_has else empty_metric("no_trusted_history"),
                "A_plus_B": metric(trusted) if c_has else empty_metric("no_trusted_history"),
            },
        },
        "result_validation": {
            "yesterday": {
                "label": f"match_date {yesterday_date}",
                "A": metric(yesterday, "A") if y_has else empty_metric("no_trusted_history_for_yesterday_or_api_disabled"),
                "B": metric(yesterday, "B") if y_has else empty_metric("no_trusted_history_for_yesterday_or_api_disabled"),
                "A_plus_B": metric(yesterday) if y_has else empty_metric("no_trusted_history_for_yesterday_or_api_disabled"),
            },
            "cumulative": {
                "label": "trusted match_date attribution history",
                "A": metric(trusted, "A") if c_has else empty_metric("no_trusted_history"),
                "B": metric(trusted, "B") if c_has else empty_metric("no_trusted_history"),
                "A_plus_B": metric(trusted) if c_has else empty_metric("no_trusted_history"),
            },
        },
        "script_validation": {
            "summary_path": f"data/runtime/status/v4_script_validation_summary_{date}.json" if script_summary else None,
            "yesterday": script_summary.get("yesterday", {}),
            "cumulative": script_summary.get("cumulative", {}),
            "by_grade": script_summary.get("by_grade", {}),
            "source_files": script_summary.get("source_files", []),
            "brief_used_for_script_validation": bool(script_summary.get("brief_used_for_script_validation")) if script_summary else False,
            "scan_date_used": bool(script_summary.get("scan_date_used")) if script_summary else False,
            "c_included": bool(script_summary.get("c_included")) if script_summary else False,
            "skip_included": bool(script_summary.get("skip_included")) if script_summary else False,
            "unknown_excluded_from_denominator": bool(script_summary.get("unknown_excluded_from_denominator", True)),
            "status": "SCRIPT_VALIDATION_READY" if script_summary else "SCRIPT_VALIDATION_NOT_READY",
        },
        "source_files": source_files,
        "source_hash": source_hash,
        "latest_validation_date": max([r.get("match_date") for r in trusted], default=None),
        "date_filter_field": "match_date",
        "validation_rebased_from_match_date": True,
        "old_summary_marked_stale": True,
        "active_summary_uses_stale_polluted_source": False,
        "trusted_records": len(trusted),
        "unresolved_records": len(unresolved),
        "blocked_records": audit.get("blocked_records", 0),
        "api_enabled": False,
        "api_disabled_reason": "--no-api: local trusted match_date attribution only; unresolved rows remain unresolved",
        "validation_source_status": "MATCH_DATE_HISTORY_RECOVERED" if trusted else "NO_TRUSTED_HISTORY_API_DISABLED",
        "yesterday": {
            "status": "READY" if y_has else "N/A",
            "reason": "" if y_has else "NO_TRUSTED_MATCH_DATE_ATTRIBUTION",
        },
        "unknown_policy": "unknown rows are excluded from hit-rate denominator and shown only in audit",
        "c_observation_active": False,
        "last_7d_active": False,
        "brief_used_for_hit_rate": False,
        "c_excluded_from_ab": True,
        "no_free_recompute": True,
        "raw_audit": {
            "trusted_records": len(trusted),
            "unresolved_records": len(unresolved),
            "blocked_records": audit.get("blocked_records", 0),
            "yesterday_match_date": yesterday_date,
            "yesterday_trusted_records": len(yesterday),
            "c_observation_deprecated": True,
            "c_deprecated_count": audit.get("classification_counts", {}).get("DO_NOT_USE", 0),
            "last_7d_removed_from_dashboard": True,
            "brief_used_for_hit_rate": False,
            "source_classification_marker": "data/runtime/status/v4_validation_history_recoverability_audit_20260523.json",
        },
        "v3_status": "N/A: V3 战备预留 / 暂无正式 validation",
        "v4_status": "trusted_match_date_history_recovered" if trusted else "validation_data_not_ready",
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
    }
    if write:
        (STATUS / f"v3v4_validation_summary_{date}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def write_inventory_docs(inventory: list[dict[str, Any]], audit: dict[str, Any]) -> None:
    inv_out = {
        "phase": "V4-MATCH-DATE-VALIDATION-HISTORY-RECOVERY-20260523",
        "generated_at": now(),
        "sources": inventory,
        "category_counts": dict(Counter(item["category"] for item in inventory)),
    }
    (STATUS / "v4_validation_history_source_inventory_20260523.json").write_text(json.dumps(inv_out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# V4 Validation History Source Inventory - 20260523", "", "| path | classification | reason |", "|---|---|---|"]
    for item in inventory:
        lines.append(f"| `{item['path']}` | `{item['category']}` | {item['reason']} |")
    lines += ["", "## Recoverability Summary", "", f"trusted_records: {audit['trusted_records']}", f"recoverable_records: {audit['recoverable_records']}", f"blocked_records: {audit['blocked_records']}", f"unknown_records: {audit['unknown_records']}"]
    (ROOT / "docs/V4_VALIDATION_HISTORY_SOURCE_INVENTORY_20260523.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (STATUS / "v4_validation_history_recoverability_audit_20260523.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], required=True)
    parser.add_argument("--no-api", action="store_true", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    inventory = source_inventory()
    records, audit = collect_records()
    write_inventory_docs(inventory, audit)
    summary = build_summary(args.date, records, audit, write=args.mode == "apply")
    marker = {
        "phase": "V4-MATCH-DATE-VALIDATION-HISTORY-RECOVERY-20260523",
        "mode": args.mode,
        "generated_at": now(),
        "dry_run": args.mode == "dry-run",
        "apply": args.mode == "apply",
        "api_enabled": False,
        "api_called": False,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "trusted_records": summary["trusted_records"],
        "unresolved_records": summary["unresolved_records"],
        "blocked_records": summary["blocked_records"],
        "brief_used_for_hit_rate": False,
        "stale_polluted_summary_used": False,
        "c_observation_active": False,
        "last_7d_active": False,
        "summary_written": args.mode == "apply",
        "summary_path": f"data/runtime/status/v3v4_validation_summary_{args.date}.json" if args.mode == "apply" else None,
        "blockers": [] if audit["blocked_records"] == 0 else ["blocked_records_present_in_history_audit"],
    }
    out = STATUS / f"v4_match_date_validation_history_recovery_{args.mode.replace('-', '_')}_20260523.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"marker": marker, "summary": summary}, ensure_ascii=False, indent=2))
    if args.strict and marker["blockers"]:
        return 2
    if summary["trusted_records"] <= 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
