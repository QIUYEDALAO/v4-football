#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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


def run_builder(env: dict[str, str] | None = None) -> tuple[int, str, str]:
    run = subprocess.run(
        [sys.executable, str(BUILDER), "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return run.returncode, run.stdout, run.stderr


def main() -> int:
    checks: list[dict[str, Any]] = []
    code, out, err = run_builder()
    add(checks, "trend_builder_runs", code == 0, err or out[-1000:])
    add(checks, "trend_latest_json_exists", TREND_JSON.exists(), str(TREND_JSON))
    add(checks, "trend_latest_txt_exists", TREND_TXT.exists(), str(TREND_TXT))

    payload = load_json(TREND_JSON)
    add(checks, "current_snapshot_id_present", bool(payload.get("current_snapshot_id")), payload.get("current_snapshot_id"))
    add(checks, "baseline_only_field_present", "baseline_only" in payload, payload.get("baseline_only"))
    add(checks, "self_reference_guard_present", bool(payload.get("self_reference_guard_status")), payload.get("self_reference_guard_status"))

    baseline_only = bool(payload.get("baseline_only"))
    current_id = str(payload.get("current_snapshot_id") or "")
    previous_id = str(payload.get("previous_snapshot_id") or "")
    current_path = str(payload.get("current_snapshot_path") or "")
    previous_path = str(payload.get("previous_snapshot_path") or "")

    if not baseline_only:
        self_ref_block = bool(previous_id) and previous_id == current_id or bool(previous_path) and previous_path == current_path
        add(checks, "SELF_REFERENCE_PREVIOUS_SNAPSHOT_BLOCKER", not self_ref_block, {"current_id": current_id, "previous_id": previous_id, "current_path": current_path, "previous_path": previous_path})
        add(checks, "previous_snapshot_id_required_when_not_baseline", bool(previous_id), previous_id)
        add(checks, "previous_snapshot_id_not_equal_current", previous_id != current_id, {"current_id": current_id, "previous_id": previous_id})
        add(checks, "previous_snapshot_path_not_equal_current", bool(previous_path) and previous_path != current_path, {"current_path": current_path, "previous_path": previous_path})

    if baseline_only:
        add(checks, "baseline_only_reason_present", bool(payload.get("baseline_only_reason")), payload.get("baseline_only_reason"))
        add(checks, "baseline_only_reason_value", str(payload.get("baseline_only_reason") or "") == "NO_PREVIOUS_DISTINCT_SNAPSHOT", payload.get("baseline_only_reason"))
        add(checks, "baseline_only_previous_snapshot_empty", not payload.get("previous_snapshot_id"), payload.get("previous_snapshot_id"))
        changed_rows = flatten_changed(payload)
        allowed = all(row.get("change_type") in {"BASELINE_ONLY"} and row.get("action_hint") == "BASELINE_ONLY_WAIT_NEXT_SNAPSHOT" for row in changed_rows)
        add(checks, "baseline_only_change_lists_safe", (not changed_rows) or allowed, changed_rows[:3])
        add(checks, "baseline_only_delta_empty", (payload.get("tag_distribution_delta") or {}) == {}, payload.get("tag_distribution_delta"))
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

    # isolated baseline-only run
    with tempfile.TemporaryDirectory(prefix="v4_a3_fix_base_") as td:
        td_path = Path(td)
        base_env = dict(os.environ)
        base_env["V4_LEAGUE_WATCHLIST_SNAPSHOT_DIR"] = str(td_path / "snap")
        base_env["V4_LEAGUE_WATCHLIST_TREND_DIR"] = str(td_path / "trend")
        code1, out1, err1 = run_builder(base_env)
        temp_payload = load_json(td_path / "trend" / "v4_league_watchlist_trend_latest.json")
        add(checks, "isolated_baseline_run_ok", code1 == 0, err1 or out1[-400:])
        add(checks, "isolated_baseline_only_true", bool(temp_payload.get("baseline_only")) is True, temp_payload.get("baseline_only"))
        add(checks, "isolated_baseline_reason", str(temp_payload.get("baseline_only_reason") or "") == "NO_PREVIOUS_DISTINCT_SNAPSHOT", temp_payload.get("baseline_only_reason"))
        add(checks, "isolated_previous_empty", not temp_payload.get("previous_snapshot_id"), temp_payload.get("previous_snapshot_id"))
        add(checks, "isolated_change_lists_empty", len(flatten_changed(temp_payload)) == 0, len(flatten_changed(temp_payload)))

    # isolated double-run run
    with tempfile.TemporaryDirectory(prefix="v4_a3_fix_double_") as td2:
        td2_path = Path(td2)
        env2 = dict(os.environ)
        env2["V4_LEAGUE_WATCHLIST_SNAPSHOT_DIR"] = str(td2_path / "snap")
        env2["V4_LEAGUE_WATCHLIST_TREND_DIR"] = str(td2_path / "trend")
        code2a, _, err2a = run_builder(env2)
        code2b, _, err2b = run_builder(env2)
        temp2_payload = load_json(td2_path / "trend" / "v4_league_watchlist_trend_latest.json")
        add(checks, "isolated_double_run_first_ok", code2a == 0, err2a[-300:] if err2a else "")
        add(checks, "isolated_double_run_second_ok", code2b == 0, err2b[-300:] if err2b else "")
        add(checks, "isolated_double_run_not_baseline", bool(temp2_payload.get("baseline_only")) is False, temp2_payload.get("baseline_only"))
        add(
            checks,
            "isolated_double_run_distinct_previous",
            bool(temp2_payload.get("previous_snapshot_id")) and str(temp2_payload.get("previous_snapshot_id")) != str(temp2_payload.get("current_snapshot_id")) and str(temp2_payload.get("previous_snapshot_path") or "") != str(temp2_payload.get("current_snapshot_path") or ""),
            {
                "current_snapshot_id": temp2_payload.get("current_snapshot_id"),
                "previous_snapshot_id": temp2_payload.get("previous_snapshot_id"),
                "current_snapshot_path": temp2_payload.get("current_snapshot_path"),
                "previous_snapshot_path": temp2_payload.get("previous_snapshot_path"),
            },
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
