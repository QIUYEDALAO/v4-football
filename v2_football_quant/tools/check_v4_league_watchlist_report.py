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
WEEKLY = ROOT / "data/weekly_reports"
VALIDATION = ROOT / "data/runtime/validation"
BUILDER = ROOT / "tools/build_v4_league_watchlist_report.py"
OUT = STATUS / "check_v4_league_watchlist_report_20260601.json"

ALLOWED_HINTS = {
    "KEEP_OBSERVE",
    "WATCH_ONLY",
    "LOW_TRUST_OBSERVE_ONLY",
    "LOW_SAMPLE_DO_NOT_CONCLUDE",
    "PENDING_ONLY_NO_DENOMINATOR",
    "DATA_GAP_REVIEW",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    json_out = WEEKLY / "v4_league_watchlist_report_dryrun.json"
    txt_out = WEEKLY / "v4_league_watchlist_report_dryrun.txt"

    run = subprocess.run(
        [sys.executable, str(BUILDER), "--report-type", "dryrun", "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    add(checks, "watchlist_builder_runs", run.returncode == 0, run.stderr or run.stdout[-1200:])
    add(checks, "json_output_exists", json_out.exists(), str(json_out))
    add(checks, "txt_output_exists", txt_out.exists(), str(txt_out))

    payload = load_json(json_out)
    ledger = load_json(VALIDATION / "v4_league_performance_ledger_latest.json")
    add(checks, "source_ledger_is_league_performance_ledger", "v4_league_performance_ledger_latest.json" in str(payload.get("source_ledger_path", "")))
    add(checks, "trend_anchor_date_2026_05_31", payload.get("trend_anchor_date") == "2026-05-31", payload.get("trend_anchor_date"))
    add(checks, "baseline_20260531_validated_pending", (payload.get("baseline_20260531", {}).get("validated_count") == 36 and payload.get("baseline_20260531", {}).get("pending_count") == 1), payload.get("baseline_20260531"))
    add(checks, "pending_excluded_from_denominator", bool(payload.get("safety_guard", {}).get("pending_excluded_from_denominator")), payload.get("safety_guard"))

    pending_only = payload.get("pending_only_leagues") or []
    arg_cup = next((x for x in pending_only if str(x.get("league")) == "阿根廷杯"), {})
    add(checks, "pending_only_list_contains_arg_cup", bool(arg_cup), pending_only[:3])
    add(checks, "arg_cup_hint_pending_only", arg_cup.get("action_hint") == "PENDING_ONLY_NO_DENOMINATOR", arg_cup)

    low_trust = payload.get("low_trust_alert_leagues") or []
    low_conclude = payload.get("do_not_conclude_leagues") or []
    add(checks, "low_trust_no_auto_exclude", all("AUTO_EXCLUDE" not in str(x.get("action_hint", "")) and "BLACKLIST" not in str(x.get("action_hint", "")) for x in low_trust), low_trust[:3])
    add(checks, "do_not_conclude_no_rule_change", all("RULE_CHANGE" not in str(x.get("action_hint", "")) for x in low_conclude), low_conclude[:3])

    all_lists = []
    for key in (
        "keep_leagues",
        "watch_leagues",
        "low_trust_alert_leagues",
        "low_sample_leagues",
        "do_not_conclude_leagues",
        "pending_only_leagues",
        "data_gap_leagues",
    ):
        all_lists.extend(payload.get(key) or [])
    add(checks, "all_action_hints_allowed", all(str(x.get("action_hint")) in ALLOWED_HINTS for x in all_lists), [x.get("action_hint") for x in all_lists if str(x.get("action_hint")) not in ALLOWED_HINTS][:5])

    builder_text = BUILDER.read_text(encoding="utf-8")
    add(checks, "no_api", "requests." not in builder_text and "urlopen(" not in builder_text)
    add(checks, "no_scan", "scan_and_brief" not in builder_text and "fullscan" not in builder_text)
    add(checks, "no_qq", "qq_push" not in builder_text.lower() and "send_qq" not in builder_text.lower())
    add(checks, "no_pending_write", "pending_route" not in builder_text and "write_pending" not in builder_text.lower())
    add(checks, "no_validation_recompute", "recompute" not in builder_text.lower())
    add(checks, "no_live_bet_write", "live_bet" not in builder_text.lower())
    add(checks, "no_cron_change", "crontab" not in builder_text.lower() and "cron" not in builder_text.lower())
    add(checks, "no_sent_marker_write", "sent_marker" not in builder_text.lower())

    add(checks, "ledger_has_pending_only_count", int(ledger.get("pending_only_count") or 0) >= 1, ledger.get("pending_only_count"))
    add(checks, "policy_note_safe", "never auto-change official grade/rules" in str(payload.get("policy_note", "")))

    blockers = [c["name"] for c in checks if not c["ok"]]
    result = {
        "generated_at": datetime.now().isoformat(),
        "status": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
        "full_scan_ran": False,
        "api_called": False,
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
