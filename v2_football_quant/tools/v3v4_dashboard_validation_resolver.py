#!/usr/bin/env python3
"""Resolve compact V3/V4 dashboard validation summary from formal artifacts.

The resolver is display-only: it reads formal validation/attribution outputs and
never recomputes grades or hit rates from the daily brief. Dashboard active
validation intentionally excludes deprecated C observation and last-7-day blocks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    from rebuild_v3v4_validation_summary_from_match_date_history import collect_records, build_summary
except Exception:  # pragma: no cover - fallback when script is unavailable
    collect_records = None
    build_summary = None

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))


def load(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def latest(pattern: str) -> Path | None:
    files = sorted(STATUS.glob(pattern))
    return files[-1] if files else None


def sha(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt_rate(rate: Any, resolved: Any = None) -> str:
    if rate is None:
        return "N/A"
    try:
        if resolved is not None and int(resolved or 0) <= 0:
            return "N/A"
        return f"{float(rate) * 100:.1f}%"
    except Exception:
        return "N/A"


def metric(src: dict[str, Any]) -> dict[str, Any]:
    rate = src.get("hit_rate_resolved_only")
    if rate is None:
        rate = src.get("hit_rate")
    resolved = src.get("resolved_count")
    if resolved is None:
        resolved = int(src.get("hit", 0) or 0) + int(src.get("miss", 0) or 0)
    return {
        "count": int(src.get("count", 0) or 0),
        "hit": int(src.get("hit", 0) or 0),
        "miss": int(src.get("miss", 0) or 0),
        "unknown": int(src.get("unknown", 0) or 0),
        "settled": int(resolved or 0),
        "hit_rate": rate,
        "display_rate": fmt_rate(rate, resolved),
    }


def empty_metric() -> dict[str, Any]:
    return {
        "count": 0,
        "hit": 0,
        "miss": 0,
        "unknown": 0,
        "settled": 0,
        "hit_rate": None,
        "display_rate": "N/A",
    }


def c_metric(src: dict[str, Any]) -> dict[str, Any]:
    rate = src.get("observation_hit_rate_resolved_only")
    if rate is None:
        rate = src.get("observation_hit_rate") or src.get("hit_rate_resolved_only") or src.get("hit_rate")
    resolved = src.get("resolved_count")
    if resolved is None:
        resolved = int(src.get("hit", 0) or 0) + int(src.get("miss", 0) or 0)
    return {
        "count": int(src.get("count", 0) or 0),
        "hit": int(src.get("hit", 0) or 0),
        "miss": int(src.get("miss", 0) or 0),
        "unknown": int(src.get("unknown", 0) or 0),
        "settled": int(resolved or 0),
        "hit_rate": rate,
        "display_rate": fmt_rate(rate, resolved),
    }


def active_pack(src: dict[str, Any]) -> dict[str, Any]:
    return {
        "A": metric(src.get("A", {}) if isinstance(src.get("A"), dict) else {}),
        "B": metric(src.get("B", {}) if isinstance(src.get("B"), dict) else {}),
        "A_plus_B": metric(src.get("A_plus_B", {}) if isinstance(src.get("A_plus_B"), dict) else {}),
    }


def empty_active_pack() -> dict[str, Any]:
    return {
        "A": empty_metric(),
        "B": empty_metric(),
        "A_plus_B": empty_metric(),
    }


def resolve(date: str, *, write: bool = True) -> dict[str, Any]:
    y_path = latest("v4_yesterday_validation_rebuilt_*.json") or latest("v4_yesterday_validation_*.json")
    r_path = latest("v4_rolling_validation_rebuilt_*.json") or latest("v4_rolling_validation_split_*.json")
    raw_path = latest("v4_validation_raw_records_*.json")
    y = load(y_path)
    r = load(r_path)
    stale_marker_path = STATUS / "v4_validation_pre_repair_marked_stale_20260523.json"
    integrity_marker_path = STATUS / "check_v4_scout_date_integrity_result_20260523.json"
    repair_marker_path = STATUS / "v4_scout_date_repair_apply_20260523.json"
    stale_marker = load(stale_marker_path)
    integrity_marker = load(integrity_marker_path)
    old_summary_marked_stale = bool(stale_marker.get("old_summary_marked_stale"))
    if old_summary_marked_stale and collect_records is not None and build_summary is not None:
        records, audit = collect_records()
        recovered = build_summary(date, records, audit, write=write)
        recovered["recovery_resolver"] = "match_date_history"
        if write:
            out = STATUS / f"v3v4_validation_summary_{date}.json"
            out.write_text(json.dumps(recovered, ensure_ascii=False, indent=2), encoding="utf-8")
        return recovered
    official_y = y.get("official", {}) if isinstance(y.get("official"), dict) else {}
    obs_y = y.get("observation", {}) if isinstance(y.get("observation"), dict) else {}
    windows = r.get("windows", {}) if isinstance(r.get("windows"), dict) else {}
    last7 = windows.get("last_7d", {}) if isinstance(windows.get("last_7d"), dict) else {}
    cumulative = windows.get("cumulative") or windows.get("last_30d") or last7
    if not isinstance(cumulative, dict):
        cumulative = {}
    source_paths = [y_path, r_path, raw_path, stale_marker_path if stale_marker_path.exists() else None, integrity_marker_path if integrity_marker_path.exists() else None, repair_marker_path if repair_marker_path.exists() else None]
    source_files = [str(p.relative_to(ROOT)) for p in source_paths if p]
    source_hash = hashlib.sha256("|".join(filter(None, [sha(p) for p in source_paths if p])).encode()).hexdigest()
    y_active = {
        "label": f"最近正式昨日验证产物 / 数据日期 {y.get('date', 'unknown')}",
        **active_pack(official_y),
    }
    cumulative_active = active_pack(cumulative)
    if old_summary_marked_stale:
        y_active = {
            "label": "赛果数据未就绪 / 修复后等待 match_date 正式 attribution",
            **empty_active_pack(),
        }
        cumulative_active = empty_active_pack()
    c_deprecated_count = 0
    c_sources: dict[str, Any] = {}
    if isinstance(obs_y.get("C"), dict):
        c_sources["yesterday"] = c_metric(obs_y["C"])
        c_deprecated_count += int(c_sources["yesterday"].get("count", 0) or 0)
    if isinstance(last7.get("C"), dict):
        c_sources["last_7d"] = c_metric(last7["C"])
    if isinstance(cumulative.get("C"), dict):
        c_sources["cumulative"] = c_metric(cumulative["C"])
        c_deprecated_count = max(c_deprecated_count, int(c_sources["cumulative"].get("count", 0) or 0))
    result = {
        "schema_version": "v3v4_validation_summary.two_column.v1",
        "phase": "V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523",
        "generated_at": datetime.now(TZ).isoformat(),
        "date": date,
        "dashboard_active": {
            "yesterday": y_active,
            "cumulative": cumulative_active,
        },
        "source_files": source_files,
        "source_hash": source_hash,
        "latest_validation_date": y.get("date") or r.get("generated_at"),
        "date_filter_field": "match_date",
        "validation_rebased_from_match_date": True,
        "old_summary_marked_stale": old_summary_marked_stale,
        "scout_date_integrity_checked": integrity_marker.get("contaminated_rows") == 0 if integrity_marker else False,
        "validation_source_status": "STALE_REBASED_NO_API_RESULTS_READY" if old_summary_marked_stale else "FORMAL_ARTIFACTS_READ_ONLY",
        "unknown_policy": "unknown 显示 N/A 或 unknown_count；样本不足不得显示 0%",
        "c_observation_active": False,
        "last_7d_active": False,
        "brief_used_for_hit_rate": False,
        "c_excluded_from_ab": True,
        "no_free_recompute": True,
        "raw_audit": {
            "c_observation_deprecated": True,
            "c_deprecated_count": c_deprecated_count,
            "c_deprecated_sources": c_sources,
            "last_7d_removed_from_dashboard": True,
            "last_7d_source_present": bool(last7),
        },
        "v3_status": "N/A: V3 战备预留 / 暂无正式 validation",
        "v4_status": "source_files_present" if source_files else "validation_data_not_ready",
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
    }
    if write:
        out = STATUS / f"v3v4_validation_summary_{date}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260523")
    args = parser.parse_args()
    result = resolve(args.date, write=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("source_files"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
