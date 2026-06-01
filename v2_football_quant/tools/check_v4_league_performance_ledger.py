#!/usr/bin/env python3
"""Check the V4 official A/B league performance ledger."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "data/runtime/validation"
STATUS = ROOT / "data/runtime/status"
BUILDER = ROOT / "tools/build_v4_league_performance_ledger.py"
MODEL_BUILDER = ROOT / "tools/build_v4_control_center_model.py"
DASHBOARD = ROOT / "data/runtime/dashboard/v4_control_center.html"
OUTPUT_JSON = VALIDATION / "v4_league_performance_ledger_latest.json"
OUTPUT_CSV = VALIDATION / "v4_league_performance_ledger_latest.csv"
CHECK_OUTPUT = STATUS / "check_v4_league_performance_ledger_20260601.json"

REQUIRED_FIELDS = {
    "league", "normalized_league", "sample_total", "validated_count",
    "pending_count", "hit_count", "miss_count", "hit_rate", "A_count",
    "A_hit_count", "A_hit_rate", "B_count", "B_hit_count", "B_hit_rate",
    "rescue_count", "rescue_hit_count", "rescue_hit_rate",
    "non_rescue_count", "non_rescue_hit_count", "non_rescue_hit_rate",
    "last_seen_date", "first_seen_date", "last_7d_count", "last_7d_hit_rate",
    "last_30d_count", "last_30d_hit_rate", "confidence_level", "sample_tag", "trust_tag",
    "warning_flags", "source_files", "data_quality_status",
}
ALLOWED_TAGS = {
    "DO_NOT_CONCLUDE", "LOW_SAMPLE_ONLY", "OBSERVE", "KEEP", "WATCH",
    "LOW_TRUST_ALERT", "DATA_GAP", "PENDING_ONLY",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def expected_confidence(validated_count: int) -> str:
    if validated_count >= 50:
        return "HIGH"
    if validated_count >= 20:
        return "MEDIUM"
    if validated_count >= 10:
        return "LOW"
    return "OBSERVE_ONLY"


def expected_tag(validated_count: int, pending_count: int, hit_rate: float, data_gap: bool) -> str:
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


def expected_sample_tag(validated_count: int, pending_count: int) -> str:
    if validated_count == 0 and pending_count > 0:
        return "PENDING_ONLY"
    if validated_count >= 20:
        return "ENOUGH_SAMPLE"
    if validated_count >= 10:
        return "LOW_SAMPLE"
    if validated_count >= 5:
        return "VERY_LOW_SAMPLE"
    return "SINGLE_OR_TINY_SAMPLE"


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run(
        [sys.executable, str(BUILDER)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-1200:])
    add(checks, "json_exists", OUTPUT_JSON.exists(), str(OUTPUT_JSON))
    add(checks, "csv_exists", OUTPUT_CSV.exists(), str(OUTPUT_CSV))

    payload = load_json(OUTPUT_JSON)
    rows = payload.get("leagues") or []
    audit = payload.get("audit") or {}
    add(checks, "official_only_true", payload.get("official_only") is True)
    add(checks, "c_skip_excluded", payload.get("C_SKIP_excluded") is True)
    add(checks, "shadow_dryrun_excluded", payload.get("shadow_dryrun_excluded") is True)
    add(
        checks,
        "outside57_source_boundary",
        payload.get("outside57_policy") == "locked official A/B reviews are included; no outside57-only source is read",
    )
    add(checks, "pending_excluded_from_denominator", payload.get("pending_excluded_from_denominator") is True)
    add(checks, "postponed_excluded_from_denominator", payload.get("postponed_excluded_from_denominator") is True)
    add(
        checks,
        "void_abandoned_result_missing_excluded",
        payload.get("void_abandoned_result_missing_excluded_from_denominator") is True,
    )
    add(checks, "locked_review_rows_included", int(audit.get("review_included_count") or 0) == 37, audit)
    add(checks, "official_outside57_review_retained", int(audit.get("official_outside57_review_included_count") or 0) == 37, audit)
    add(checks, "league_rows_non_empty", bool(rows), f"rows={len(rows)}")

    row_errors: list[str] = []
    for row in rows:
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            row_errors.append(f"{row.get('league')}:missing={sorted(missing)}")
            continue
        validated = int(row.get("validated_count") or 0)
        pending = int(row.get("pending_count") or 0)
        hits = int(row.get("hit_count") or 0)
        misses = int(row.get("miss_count") or 0)
        hit_rate = float(row.get("hit_rate") or 0)
        expected_rate = round(hits / validated, 6) if validated else 0.0
        data_gap = row.get("data_quality_status") == "DATA_GAP"
        if validated != hits + misses:
            row_errors.append(f"{row.get('league')}:validated_not_hit_plus_miss")
        if abs(hit_rate - expected_rate) > 0.000001:
            row_errors.append(f"{row.get('league')}:hit_rate_bad")
        if row.get("confidence_level") != expected_confidence(validated):
            row_errors.append(f"{row.get('league')}:confidence_bad")
        if row.get("sample_tag") != expected_sample_tag(validated, pending):
            row_errors.append(f"{row.get('league')}:sample_tag_bad")
        if row.get("trust_tag") not in ALLOWED_TAGS:
            row_errors.append(f"{row.get('league')}:trust_tag_missing")
        if row.get("trust_tag") != expected_tag(validated, pending, hit_rate, data_gap):
            row_errors.append(f"{row.get('league')}:trust_tag_bad")
    add(checks, "league_rows_contract", not row_errors, row_errors[:20])

    csv_rows: list[dict[str, str]] = []
    if OUTPUT_CSV.exists():
        with OUTPUT_CSV.open(encoding="utf-8-sig", newline="") as handle:
            csv_rows = list(csv.DictReader(handle))
    add(checks, "csv_row_count_matches", len(csv_rows) == len(rows), f"csv={len(csv_rows)} json={len(rows)}")
    add(
        checks,
        "summary_totals_match",
        int(payload.get("total_validated") or 0) == sum(int(row.get("validated_count") or 0) for row in rows)
        and int(payload.get("total_pending") or 0) == sum(int(row.get("pending_count") or 0) for row in rows),
    )
    baseline = payload.get("baseline_20260531") or {}
    baseline_rows = {
        str(row.get("league") or ""): row
        for row in (baseline.get("leagues") or [])
        if isinstance(row, dict)
    }

    def baseline_is(league: str, hit: int, validated: int, pending: int = 0) -> bool:
        row = baseline_rows.get(league) or {}
        return (
            int(row.get("hit_count") or 0) == hit
            and int(row.get("validated_count") or 0) == validated
            and int(row.get("pending_count") or 0) == pending
        )

    add(checks, "baseline_20260531_totals", int(baseline.get("validated_count") or 0) == 36 and int(baseline.get("pending_count") or 0) == 1, baseline)
    add(checks, "baseline_20260531_冰岛超_4_4", baseline_is("冰岛超", 4, 4), baseline_rows.get("冰岛超"))
    add(checks, "baseline_20260531_挪甲_4_4", baseline_is("挪甲", 4, 4), baseline_rows.get("挪甲"))
    add(checks, "baseline_20260531_智利甲_1_3", baseline_is("智利甲", 1, 3), baseline_rows.get("智利甲"))
    add(checks, "baseline_20260531_巴西甲_3_5", baseline_is("巴西甲", 3, 5), baseline_rows.get("巴西甲"))
    add(checks, "baseline_20260531_阿根廷杯_pending_only", baseline_is("阿根廷杯", 0, 0, 1), baseline_rows.get("阿根廷杯"))
    arg_cup = baseline_rows.get("阿根廷杯") or {}
    add(
        checks,
        "baseline_20260531_阿根廷杯_pending_only_contract",
        int(arg_cup.get("validated_count") or 0) == 0
        and int(arg_cup.get("pending_count") or 0) == 1
        and int(arg_cup.get("hit_count") or 0) == 0
        and int(arg_cup.get("miss_count") or 0) == 0
        and arg_cup.get("sample_tag") == "PENDING_ONLY"
        and arg_cup.get("trust_tag") == "PENDING_ONLY",
        arg_cup,
    )
    add(checks, "source_ledger_resolved_present", bool(payload.get("source_ledger_resolved")), payload.get("source_ledger_resolved"))
    add(
        checks,
        "historical_ledger_status_ok_or_warn",
        payload.get("historical_ledger_status") in {"OK", "HISTORICAL_LEDGER_MISSING_WARN_ONLY"},
        payload.get("historical_ledger_status"),
    )
    add(checks, "trend_anchor_date_present", payload.get("trend_anchor_date") not in {"", None}, payload.get("trend_anchor_date"))

    builder_text = BUILDER.read_text(encoding="utf-8")
    model_text = MODEL_BUILDER.read_text(encoding="utf-8")
    dashboard_text = DASHBOARD.read_text(encoding="utf-8")
    add(checks, "no_api", "requests." not in builder_text and "urlopen(" not in builder_text)
    add(checks, "historical_source_not_hardcoded_20260526", "load_json(HISTORICAL_LEDGER)" not in builder_text and "HISTORICAL_LEDGER = VALIDATION / \"v4_ab_historical_ledger_20260526.json\"" not in builder_text)
    add(checks, "trend_window_not_datetime_now", "datetime.now(LOCAL_TZ) - timedelta(days=days)" not in builder_text)
    add(checks, "no_scan", "scan_and_brief" not in builder_text and "fullscan" not in builder_text)
    add(checks, "no_qq", "qq_push" not in builder_text.lower() and "send_qq" not in builder_text.lower())
    add(checks, "no_pending_write", "pending" not in " ".join(path.name for path in [OUTPUT_JSON, OUTPUT_CSV]))
    add(checks, "no_validation_recompute", "ht_goal_count >=" not in builder_text and "ht_goals >=" not in builder_text)
    add(checks, "no_live_bet_write", "live_bet" not in builder_text.lower())
    add(checks, "no_cron_change", "crontab" not in builder_text.lower() and "cron.write" not in builder_text.lower())
    add(
        checks,
        "low_trust_alert_display_only",
        "LOW_TRUST_ALERT" in dashboard_text
        and "LOW_TRUST_ALERT" in model_text
        and "official_grade = league" not in model_text
        and "grade = league" not in model_text,
    )
    add(checks, "dashboard_pending_only_copy", "延期/未完赛，仅记录，不进分母" in dashboard_text)
    add(checks, "dashboard_low_sample_copy", "样本偏少，仅辅助参考" in dashboard_text)

    blockers = [check["name"] for check in checks if not check["ok"]]
    result = {
        "phase": "LEAGUE-LEDGER-A1",
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
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    CHECK_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "blockers": blockers, "output": str(CHECK_OUTPUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
