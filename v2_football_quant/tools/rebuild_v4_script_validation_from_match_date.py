#!/usr/bin/env python3
"""Build V4 script validation from trusted match_date postmatch history.

This resolver is deliberately separate from A/B result validation. It never
changes recommendation grades, never reads the brief for script judgement, and
never counts SCRIPT_UNKNOWN in the denominator.
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
ACTIVE_GRADES = {"A", "B"}
RESULT_ENUM = {"SCRIPT_HIT", "SCRIPT_PARTIAL", "SCRIPT_MISS", "SCRIPT_UNKNOWN"}

SCRIPT_RULES = {
    "中段发力型": {"hit": [(16, 60)], "partial": [(31, 75)]},
    "中后段发力型": {"hit": [(31, 75)], "partial": [(16, 60), (60, 90)]},
    "慢热绝杀型": {"hit": [(60, 90)], "partial": [(46, 90)]},
    "前压快开型": {"hit": [(0, 30)], "partial": [(31, 45)]},
    "开局冲击型": {"hit": [(0, 30)], "partial": [(31, 45)]},
    "后段冲击型": {"hit": [(60, 90)], "partial": [(46, 90)]},
}


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
            try:
                fid = int(row.get("fixture_id"))
            except Exception:
                continue
            index[fid] = {
                "fixture_id": fid,
                "match_date": norm_date(row.get("match_date") or row.get("date")),
                "date": norm_date(row.get("date")),
                "scan_date": norm_date(row.get("scan_date")),
                "kickoff": row.get("kickoff") or row.get("kickoff_time"),
                "source_file": rel(path),
            }
    return index


def event_minutes(row: dict[str, Any]) -> tuple[list[int], str]:
    minutes: list[int] = []
    raw_events = row.get("goal_events") or row.get("events") or []
    if isinstance(raw_events, list):
        for ev in raw_events:
            if not isinstance(ev, dict):
                continue
            value = ev.get("minute") or ev.get("elapsed") or (ev.get("time") or {}).get("elapsed")
            try:
                minute = int(value)
            except Exception:
                continue
            if 0 <= minute <= 130:
                minutes.append(minute)
    first = row.get("first_ht_goal_minute")
    try:
        if first is not None:
            minute = int(first)
            if 0 <= minute <= 45:
                minutes.append(minute)
    except Exception:
        pass
    minutes = sorted(set(minutes))
    if minutes:
        return minutes, "EVENT_MINUTES_AVAILABLE"
    if row.get("ht_scoreline") or row.get("ft_scoreline"):
        return [], "SCORE_ONLY_NO_EVENT_TIME"
    return [], "NO_POSTMATCH_EVENT_DATA"


def minute_in_ranges(minute: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= minute <= end for start, end in ranges)


def judge_script(script: str, minutes: list[int], quality: str) -> tuple[str, float | None, str, str]:
    if quality != "EVENT_MINUTES_AVAILABLE" or not minutes:
        return "SCRIPT_UNKNOWN", None, "no auditable goal event minute", quality
    rules = SCRIPT_RULES.get(script)
    if not rules:
        # Existing taxonomy value but no frozen rule yet: keep auditable and do not guess.
        return "SCRIPT_UNKNOWN", None, f"unsupported script family: {script}", "UNSUPPORTED_SCRIPT_FAMILY"
    if any(minute_in_ranges(m, rules["hit"]) for m in minutes):
        return "SCRIPT_HIT", 1.0, f"goal minute {minutes} supports {script}", quality
    if any(minute_in_ranges(m, rules.get("partial", [])) for m in minutes):
        return "SCRIPT_PARTIAL", 0.5, f"goal minute {minutes} partially supports {script}", quality
    return "SCRIPT_MISS", 0.0, f"goal minute {minutes} conflicts with {script}", quality


def classify_row(row: dict[str, Any], source_file: str, scout_index: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    try:
        fid = int(row.get("fixture_id"))
    except Exception:
        return None
    grade = row.get("pre_grade") or row.get("grade")
    if grade not in ACTIVE_GRADES:
        return None
    scout = scout_index.get(fid, {})
    match_date = scout.get("match_date") or norm_date(row.get("match_date") or row.get("date"))
    if not match_date:
        return None
    script = str(row.get("script_type") or row.get("script_predicted") or "").strip()
    minutes, quality = event_minutes(row)
    result, confidence, reason, data_quality = judge_script(script, minutes, quality)
    return {
        "fixture_id": fid,
        "match_id": fid,
        "match_date": match_date,
        "grade": grade,
        "home_team_cn": row.get("home_cn") or row.get("home"),
        "away_team_cn": row.get("away_cn") or row.get("away"),
        "script_predicted": script or "UNKNOWN_SCRIPT",
        "script_family": script if script in SCRIPT_RULES else "UNSUPPORTED_OR_UNKNOWN",
        "kickoff": scout.get("kickoff"),
        "ht_score": row.get("ht_scoreline"),
        "ft_score": row.get("ft_scoreline"),
        "goal_events": minutes,
        "actual_goal_timing_profile": timing_profile(minutes),
        "script_result": result,
        "script_confidence": confidence,
        "script_reason": reason,
        "source_files": [source_file, scout.get("source_file")],
        "api_enabled": False,
        "data_quality": data_quality,
        "brief_used_for_script_validation": False,
        "scan_date_used": False,
    }


def timing_profile(minutes: list[int]) -> str:
    if not minutes:
        return "NO_EVENT_TIMING"
    buckets = []
    for m in minutes:
        if m <= 15:
            buckets.append("0-15")
        elif m <= 30:
            buckets.append("16-30")
        elif m <= 45:
            buckets.append("31-45")
        elif m <= 60:
            buckets.append("46-60")
        elif m <= 75:
            buckets.append("61-75")
        else:
            buckets.append("76-90+")
    return ",".join(buckets)


def metric(rows: list[dict[str, Any]], grade: str | None = None) -> dict[str, Any]:
    subset = [r for r in rows if grade is None or r.get("grade") == grade]
    hit = sum(1 for r in subset if r.get("script_result") == "SCRIPT_HIT")
    partial = sum(1 for r in subset if r.get("script_result") == "SCRIPT_PARTIAL")
    miss = sum(1 for r in subset if r.get("script_result") == "SCRIPT_MISS")
    unknown = sum(1 for r in subset if r.get("script_result") == "SCRIPT_UNKNOWN")
    denom = hit + partial + miss
    rate = hit / denom if denom else None
    return {
        "script_hit": hit,
        "script_partial": partial,
        "script_miss": miss,
        "script_unknown": unknown,
        "script_denominator": denom,
        "script_hit_rate": rate,
        "display_rate": "N/A" if rate is None else f"{rate * 100:.1f}%",
        "display_compact": "N/A" if denom == 0 else f"{hit}/{denom} · {rate * 100:.1f}%",
        "unknown_excluded_from_denominator": True,
    }


def collect_rows() -> tuple[list[dict[str, Any]], list[str]]:
    scout_index = build_scout_index()
    out: list[dict[str, Any]] = []
    sources: list[str] = []
    for path in sorted(ARCHIVE.glob("v4_result_attribution_*.jsonl")):
        rows = load_jsonl(path)
        if not rows:
            continue
        source = rel(path)
        sources.append(source)
        for row in rows:
            item = classify_row(row, source, scout_index)
            if item:
                out.append(item)
    return out, sources


def build_summary(date: str) -> dict[str, Any]:
    rows, source_files = collect_rows()
    target = datetime.strptime(date, "%Y%m%d").date()
    yesterday_date = (target - timedelta(days=1)).isoformat()
    yesterday = [r for r in rows if r.get("match_date") == yesterday_date]
    cumulative = rows
    source_hash = hashlib.sha256("|".join(source_files + [str(len(rows))]).encode()).hexdigest()
    by_family = Counter(r.get("script_predicted") for r in rows)
    unknown_reasons = Counter(r.get("script_reason") for r in rows if r.get("script_result") == "SCRIPT_UNKNOWN")
    return {
        "schema_version": "v4_script_validation_summary.v1",
        "phase": "V4-POSTMATCH-SCRIPT-VALIDATION-ADDON-20260523",
        "generated_at": now(),
        "date": date,
        "date_filter_field": "match_date",
        "match_date_used": True,
        "scan_date_used": False,
        "brief_used_for_script_validation": False,
        "c_included": False,
        "skip_included": False,
        "c_observation_active": False,
        "last_7d_active": False,
        "script_result_enum": sorted(RESULT_ENUM),
        "unknown_excluded_from_denominator": True,
        "partial_not_counted_as_hit": True,
        "api_enabled": False,
        "api_disabled_reason": "--no-api: local formal attribution event timing only; rows without event timing remain SCRIPT_UNKNOWN",
        "source_files": source_files,
        "source_hash": source_hash,
        "per_match": rows,
        "yesterday": {
            "label": f"match_date {yesterday_date}",
            "A": metric(yesterday, "A"),
            "B": metric(yesterday, "B"),
            "AB": metric(yesterday),
        },
        "cumulative": {
            "label": "trusted match_date attribution event history",
            "A": metric(cumulative, "A"),
            "B": metric(cumulative, "B"),
            "AB": metric(cumulative),
        },
        "by_grade": {
            "A": metric(cumulative, "A"),
            "B": metric(cumulative, "B"),
            "AB": metric(cumulative),
        },
        "raw_audit": {
            "script_family_counts": dict(by_family),
            "unknown_reason_counts": dict(unknown_reasons),
            "total_ab_rows": len(rows),
            "yesterday_ab_rows": len(yesterday),
            "rules": SCRIPT_RULES,
        },
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
    }


def write_schema() -> None:
    schema = {
        "schema_version": "v4_script_validation_schema.v1",
        "generated_at": now(),
        "fields": [
            "match_id", "fixture_id", "match_date", "grade", "home_team_cn", "away_team_cn",
            "script_predicted", "script_family", "kickoff", "ht_score", "ft_score", "goal_events",
            "actual_goal_timing_profile", "script_result", "script_confidence", "script_reason",
            "source_files", "api_enabled", "data_quality",
        ],
        "script_result_enum": sorted(RESULT_ENUM),
        "rules": {
            "SCRIPT_UNKNOWN": "excluded from script hit-rate denominator",
            "SCRIPT_PARTIAL": "tracked separately and not counted as SCRIPT_HIT",
            "C": "excluded",
            "SKIP": "excluded",
            "AB": "A+B only, no C",
            "rating_impact": "none; script validation never changes recommendation grade",
        },
    }
    (STATUS / "v4_script_validation_schema_20260523.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    md = """# V4 Script Validation Schema 20260523

## Fields

- match_id / fixture_id
- match_date
- grade
- home_team_cn / away_team_cn
- script_predicted
- script_family
- kickoff
- ht_score / ft_score
- goal_events
- actual_goal_timing_profile
- script_result
- script_confidence
- script_reason
- source_files
- api_enabled
- data_quality

## script_result enum

- SCRIPT_HIT
- SCRIPT_PARTIAL
- SCRIPT_MISS
- SCRIPT_UNKNOWN

## Rules

- SCRIPT_UNKNOWN is excluded from the denominator.
- SCRIPT_PARTIAL is tracked separately and is not counted as HIT.
- C and SKIP are excluded.
- A+B script validation equals A+B only, never C.
- Script validation is an audit layer and never changes V4 recommendation grades.
- Brief text is not used for script validation judgement.
"""
    (ROOT / "docs/V4_SCRIPT_VALIDATION_SCHEMA_20260523.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], required=True)
    parser.add_argument("--no-api", action="store_true", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    write_schema()
    summary = build_summary(args.date)
    if args.mode == "apply":
        (STATUS / f"v4_script_validation_summary_{args.date}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    marker = {
        "phase": "V4-POSTMATCH-SCRIPT-VALIDATION-ADDON-20260523",
        "generated_at": now(),
        "mode": args.mode,
        "dry_run": args.mode == "dry-run",
        "apply": args.mode == "apply",
        "resolver_path": "tools/rebuild_v4_script_validation_from_match_date.py",
        "match_date_used": True,
        "scan_date_used": False,
        "brief_used": False,
        "brief_used_for_script_validation": False,
        "c_included": False,
        "skip_included": False,
        "script_rows": len(summary.get("per_match", [])),
        "script_unknown": summary["cumulative"]["AB"]["script_unknown"],
        "script_denominator": summary["cumulative"]["AB"]["script_denominator"],
        "source_files": summary.get("source_files", []),
        "summary_written": args.mode == "apply",
        "summary_path": f"data/runtime/status/v4_script_validation_summary_{args.date}.json" if args.mode == "apply" else None,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "blockers": [],
    }
    out = STATUS / f"v4_script_validation_{args.mode.replace('-', '_')}_{args.date}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"marker": marker, "summary": {k: summary[k] for k in summary if k != "per_match"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
