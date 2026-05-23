#!/usr/bin/env python3
"""V3/V4 Intel Ops Console daily refresh entrypoint.

Dry-run/apply runner. It reads the daily formal brief, candidate source, and
formal validation summary. It does not run capture, push QQ, publish cloud, or
create cron.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from generate_intel_desk_html import MODULE, STATUS_DIR, build_dashboard, render_html, resolve_source_date, _latest_candidate_view, _latest_v3_status, _counts, _source_hash
from v3v4_dashboard_brief_resolver import resolve as resolve_brief
from v3v4_dashboard_validation_resolver import resolve as resolve_validation

TZ = timezone(timedelta(hours=8))
LOCK_PATH = MODULE / "data/runtime/locks/v3v4_intel_ops_console_daily_refresh.lock"
LAST_GOOD = STATUS_DIR / "v3v4_intel_ops_console_daily_refresh_last_good.json"


def build_preview(date: str, source_window: str) -> dict:
    brief = resolve_brief(date, write=True)
    validation = resolve_validation(date, write=True)
    data, candidate_path = _latest_candidate_view(date)
    v3, v3_path = _latest_v3_status()
    source_resolution = resolve_source_date(data, candidate_path, write=True)
    html_text = render_html(data, candidate_path, v3, v3_path, validation, source_resolution)
    counts = _counts(data)
    preview_hash = hashlib.sha256(html_text.encode()).hexdigest()
    last_good = {}
    if LAST_GOOD.exists():
        try:
            last_good = json.loads(LAST_GOOD.read_text(encoding="utf-8"))
        except Exception:
            last_good = {}
    source_hash = _source_hash(candidate_path, data)
    noop = bool(last_good and last_good.get("source_hash") == source_hash and last_good.get("dashboard_sha256") == preview_hash)
    return {
        "schema_version": "v3v4_dashboard_daily_refresh.two_column_script.v1",
        "phase": "V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523",
        "generated_at": datetime.now(TZ).isoformat(),
        "date": date,
        "mode": "dry-run",
        "source_window": source_window,
        "entrypoint": "tools/run_v3v4_intel_ops_console_daily_refresh.py",
        "active_scope": "V3_V4_ONLY",
        "brief_path": brief.get("brief_path"),
        "brief_sha256": brief.get("brief_sha256"),
        "brief_exists": brief.get("brief_exists"),
        "brief_is_today": brief.get("is_today_brief"),
        "is_today_brief": brief.get("is_today_brief"),
        "A": counts["A"],
        "B": counts["B"],
        "C_deprecated_count": counts["C"],
        "C_active": False,
        "SKIP": counts["SKIP"],
        "formal_count": counts["A"] + counts["B"],
        "source_hash": source_hash,
        "preview_dashboard_sha256": preview_hash,
        "dashboard_sha256": preview_hash,
        "candidate_source": str(candidate_path.relative_to(MODULE)) if candidate_path else None,
        "source_date": source_resolution.get("scan_date"),
        "candidate_source_date": source_resolution.get("scan_date"),
        "is_today_source": source_resolution.get("is_today_source"),
        "source_date_mismatch": source_resolution.get("source_date_mismatch"),
        "display_label": source_resolution.get("display_label"),
        "validation_source_files": validation.get("source_files", []),
        "brief_used_for_hit_rate": validation.get("brief_used_for_hit_rate", False),
        "c_observation_active": validation.get("c_observation_active", False),
        "last_7d_active": validation.get("last_7d_active", False),
        "c_excluded_from_ab": validation.get("c_excluded_from_ab", True),
        "validation_layout": "two_column",
        "script_value_highlight": True,
        "v3_source": str(v3_path.relative_to(MODULE)) if v3_path else "reserved",
        "lock_path": str(LOCK_PATH.relative_to(MODULE)),
        "last_good_path": str(LAST_GOOD.relative_to(MODULE)),
        "has_lock_contract": True,
        "has_last_good_contract": True,
        "noop": noop,
        "noop_reason": "source_hash_unchanged" if noop else None,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "cron_enabled": False,
        "strategy_changed": False,
        "v4_candidate_numbers_changed": False,
        "daily_refresh_v2_dependency": False,
        "daily_refresh_v3v4_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260523")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--source-window", choices=["auto", "early", "midday", "evening", "night"], default="auto")
    parser.add_argument("--no-capture", action="store_true", required=False)
    parser.add_argument("--no-push", action="store_true", required=False)
    parser.add_argument("--no-cloud", action="store_true", required=False)
    parser.add_argument("--strict", action="store_true", required=False)
    args = parser.parse_args()
    if args.strict and not (args.no_capture and args.no_push and args.no_cloud):
        raise SystemExit("BLOCKER: --strict requires --no-capture --no-push --no-cloud")
    if args.mode == "apply":
        # Refresh the display-only candidate view before rendering so the
        # dashboard inherits the corrected daily_1200 source-window contract.
        resolve_brief(args.date, write=True)
        marker = build_dashboard(write=True, date_key=args.date)
        marker = marker | {
            "date": args.date,
            "mode": "apply",
            "source_window": args.source_window,
            "has_lock_contract": True,
            "has_last_good_contract": True,
            "daily_refresh_v2_dependency": False,
            "daily_refresh_v3v4_only": True,
        }
        LAST_GOOD.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        marker = build_preview(args.date, args.source_window)
    out = STATUS_DIR / f"v3v4_intel_ops_console_daily_refresh_{args.mode.replace('-', '_')}_{args.date}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    daily_marker = {
        "schema_version": "v3v4_dashboard_daily_refresh.two_column_script.v1",
        "phase": "V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523",
        "generated_at": datetime.now(TZ).isoformat(),
        "date": args.date,
        "mode": args.mode,
        "brief_path": marker.get("brief_path"),
        "brief_sha256": marker.get("brief_sha256"),
        "brief_is_today": marker.get("brief_is_today", marker.get("is_today_brief")),
        "candidate_source_date": marker.get("candidate_source_date", marker.get("source_date")),
        "validation_source_files": marker.get("validation_source_files", []),
        "dashboard_sha256": marker.get("dashboard_sha256", marker.get("preview_dashboard_sha256")),
        "source_hash": marker.get("source_hash"),
        "A": marker.get("A"),
        "B": marker.get("B"),
        "SKIP": marker.get("SKIP"),
        "C_active": False,
        "last_7d_active": False,
        "validation_layout": marker.get("validation_layout", "two_column"),
        "script_value_highlight": marker.get("script_value_highlight", True),
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "cron_enabled": False,
    }
    (STATUS_DIR / f"v3v4_dashboard_daily_refresh_{args.date}.json").write_text(json.dumps(daily_marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(marker, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
