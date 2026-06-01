#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
BUILDER = ROOT / "tools/build_v4_league_watchlist_trend_report.py"
OUT = STATUS / "check_v4_league_watchlist_trend_report_20260601.json"
TREND_JSON = ROOT / "data/runtime/league_watchlist_trends/v4_league_watchlist_trend_latest.json"
TREND_TXT = ROOT / "data/runtime/league_watchlist_trends/v4_league_watchlist_trend_latest.txt"

ALLOWED_HINTS = {
    "OBSERVE_ONLY",
    "CONTINUE_MONITORING",
    "LOW_TRUST_OBSERVE_ONLY",
    "LOW_SAMPLE_DO_NOT_CONCLUDE",
    "PENDING_ONLY_NO_DENOMINATOR",
    "DATA_GAP_REVIEW",
    "BASELINE_ONLY_WAIT_NEXT_SNAPSHOT",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def flatten_changed(payload: dict[str, Any]) -> list[dict[str, Any]]:
    keys = [
        "trust_tag_changed_leagues",
        "improved_leagues",
        "worsened_leagues",
        "new_low_trust_alert_leagues",
        "resolved_low_trust_alert_leagues",
        "new_low_sample_leagues",
        "pending_to_validated_leagues",
        "new_pending_only_leagues",
        "sample_count_delta_top",
        "hit_rate_delta_top",
    ]
    rows: list[dict[str, Any]] = []
    for key in keys:
        rows.extend([x for x in (payload.get(key) or []) if isinstance(x, dict)])
    return rows


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run(
        [sys.executable, str(BUILDER), "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    add(checks, "trend_builder_runs", run.returncode == 0, run.stderr or run.stdout[-1000:])
    add(checks, "trend_latest_json_exists", TREND_JSON.exists(), str(TREND_JSON))
    add(checks, "trend_latest_txt_exists", TREND_TXT.exists(), str(TREND_TXT))

    payload = load_json(TREND_JSON)
    add(checks, "current_snapshot_id_present", bool(payload.get("current_snapshot_id")), payload.get("current_snapshot_id"))
    add(checks, "baseline_only_field_present", "baseline_only" in payload, payload.get("baseline_only"))

    baseline_only = bool(payload.get("baseline_only"))
    if baseline_only:
        add(checks, "baseline_only_reason_present", bool(payload.get("baseline_only_reason")), payload.get("baseline_only_reason"))
        changed_rows = flatten_changed(payload)
        allowed = all(row.get("change_type") in {"BASELINE_ONLY"} and row.get("action_hint") == "BASELINE_ONLY_WAIT_NEXT_SNAPSHOT" for row in changed_rows)
        add(checks, "baseline_only_change_lists_safe", (not changed_rows) or allowed, changed_rows[:3])
    else:
        curr = payload.get("tag_distribution_current") or {}
        prev = payload.get("tag_distribution_previous") or {}
        delta = payload.get("tag_distribution_delta") or {}
        keys = sorted(set(curr) | set(prev) | set(delta))
        ok = all(int(delta.get(k, 0)) == int(curr.get(k, 0)) - int(prev.get(k, 0)) for k in keys)
        add(checks, "tag_distribution_delta_correct", ok, {"curr": curr, "prev": prev, "delta": delta})

        changed = payload.get("trust_tag_changed_leagues") or []
        add(
            checks,
            "trust_tag_changed_leagues_correct",
            all(str(x.get("previous_trust_tag")) != str(x.get("current_trust_tag")) for x in changed if isinstance(x, dict)),
            changed[:3],
        )

    all_rows = flatten_changed(payload)
    add(
        checks,
        "action_hint_whitelist",
        all(str(row.get("action_hint")) in ALLOWED_HINTS for row in all_rows),
        [row.get("action_hint") for row in all_rows if str(row.get("action_hint")) not in ALLOWED_HINTS][:5],
    )
    add(checks, "policy_note_safe", "不自动修改 official grade" in str(payload.get("policy_note", "")), payload.get("policy_note"))

    guard = payload.get("safety_guard") or {}
    add(checks, "guard_no_official_grade_change", guard.get("no_official_grade_change") is True, guard)
    add(checks, "guard_no_auto_exclude", guard.get("no_auto_exclude") is True, guard)
    add(checks, "guard_pending_excluded", guard.get("pending_only_excluded_from_denominator") is True, guard)

    src = BUILDER.read_text(encoding="utf-8")
    add(checks, "no_api", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_scan", "scan_and_brief" not in src and "fullscan" not in src)
    add(checks, "no_qq", "qq_push" not in src.lower() and "send_qq" not in src.lower())
    add(checks, "no_pending_write", "pending_route" not in src and "write_pending" not in src.lower())
    add(checks, "no_validation_recompute", "recompute" not in src.lower())
    add(checks, "no_live_bet_write", "live_bet" not in src.lower())
    add(checks, "no_cron_change", "crontab" not in src.lower() and "cron" not in src.lower())
    add(checks, "no_sent_marker_write", "sent_marker" not in src.lower())

    blockers = [c["name"] for c in checks if not c["ok"]]
    result = {
        "generated_at": datetime.now().isoformat(),
        "status": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
        "api_called": False,
        "full_scan_ran": False,
        "QQ_push": False,
        "pending_written": False,
        "validation_recomputed": False,
        "live_bet_written": False,
        "cron_modified": False,
        "sent_marker_written": False,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
