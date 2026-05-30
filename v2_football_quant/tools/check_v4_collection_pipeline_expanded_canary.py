#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
ACCEPT = ROOT / "data" / "runtime" / "acceptance"
STATUS = ROOT / "data" / "runtime" / "status"
TZ = timezone(timedelta(hours=8))


def _ok(checks: dict[str, dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def _latest(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _run(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(TOOLS / script)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def _extract_json_line(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        pass
    i = text.find("{")
    while i >= 0:
        chunk = text[i:]
        try:
            return json.loads(chunk)
        except Exception:
            i = text.find("{", i + 1)
    return {}


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_collection_pipeline_expanded_canary",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    rolling_tool = TOOLS / "run_v4_collection_pipeline_rolling_canary.py"
    _ok(result["checks"], "rolling_tool_exists", rolling_tool.exists(), str(rolling_tool))
    if not rolling_tool.exists():
        result["blockers"].append("rolling_tool_missing")
        return _finish(result)

    src = rolling_tool.read_text(encoding="utf-8")
    _ok(result["checks"], "rolling_supports_max_15", "<= 15" in src)

    latest_json = _latest("v4_collection_pipeline_rolling_canary_*.json", ACCEPT)
    _ok(result["checks"], "expanded_artifact_exists", latest_json is not None and latest_json.exists(), str(latest_json) if latest_json else "")
    if latest_json is None:
        result["blockers"].append("expanded_artifact_missing")
        return _finish(result)

    payload = json.loads(latest_json.read_text(encoding="utf-8"))
    max_fx = int(payload.get("max_fixtures") or 0)
    _ok(result["checks"], "max_fixtures_eq_15", max_fx == 15, str(max_fx))
    if max_fx != 15:
        result["blockers"].append("max_fixtures_not_15")

    per = payload.get("per_date_results") or []
    agg = payload.get("aggregate") or {}
    dates_passed = int(agg.get("dates_passed") or 0)
    _ok(result["checks"], "at_least_2_dates_success", dates_passed >= 2, str(dates_passed))
    if dates_passed < 2:
        result["blockers"].append("not_enough_success_dates")

    total_h2h_t = total_h2h_f = total_h2h_c = total_h2h_s = 0
    total_e_t = total_e_f = total_e_c = total_e_s = 0
    total_cpl_t = total_cpl_f = total_cpl_c = total_cpl_s = 0
    total_saved = 0

    uncovered_official_dates: list[str] = []
    uncovered_ab_dates: list[str] = []
    lazy_zero_dates: list[str] = []
    mismatch_dates: list[str] = []
    no_push_bad_dates: list[str] = []
    whitelist_bad_dates: list[str] = []
    serial_bad_dates: list[str] = []
    mode_bad_dates: list[str] = []

    shadow_only_ids_all: set[str] = set()

    for row in per:
        date = str(row.get("date") or "")
        if row.get("status") != "PASS":
            continue

        cmd = str(row.get("command") or "")
        compare_path = Path(str(row.get("compare_json") or ""))

        # lazy scout zero risk
        lazy_raw = int(row.get("rf_lazy_shadow_raw") or 0)
        lazy_scout = int(row.get("rf_lazy_shadow_scout") or 0)
        if lazy_raw > 0 and lazy_scout == 0:
            lazy_zero_dates.append(date)

        # aggregate counters
        total_h2h_t += int(row.get("h2h_required_true_count") or 0)
        total_h2h_f += int(row.get("h2h_required_false_count") or 0)
        total_h2h_c += int(row.get("h2h_collected_count") or 0)
        total_h2h_s += int(row.get("h2h_skipped_count") or 0)
        total_e_t += int(row.get("events_required_true_count") or 0)
        total_e_f += int(row.get("events_required_false_count") or 0)
        total_e_c += int(row.get("events_collected_count") or 0)
        total_e_s += int(row.get("events_skipped_count") or 0)
        total_cpl_t += int(row.get("cpl_required_true_count") or 0)
        total_cpl_f += int(row.get("cpl_required_false_count") or 0)
        total_cpl_c += int(row.get("cpl_collected_count") or 0)
        total_cpl_s += int(row.get("cpl_skipped_count") or 0)
        total_saved += int(row.get("estimated_expensive_calls_saved") or 0)

        # command-level checks
        if "run_v4_collection_pipeline_canary_compare.py" not in cmd:
            mode_bad_dates.append(date)

        if not compare_path.exists():
            mode_bad_dates.append(date)
            continue

        cp = json.loads(compare_path.read_text(encoding="utf-8"))
        off_cmd = str((cp.get("comparison") or {}).get("official_command") or "")
        lazy_cmd = str((cp.get("comparison") or {}).get("lazy_command") or "")
        no_push_ok = bool(cp.get("no_push"))
        if not no_push_ok:
            no_push_bad_dates.append(date)

        if "--fixture-universe whitelist" not in off_cmd or "--fixture-universe whitelist" not in lazy_cmd:
            whitelist_bad_dates.append(date)
        if "--scan-engine serial" not in off_cmd or "--scan-engine serial" not in lazy_cmd:
            serial_bad_dates.append(date)
        if "--collection-mode official_legacy" not in off_cmd or "--collection-mode rf_lazy_shadow" not in lazy_cmd:
            mode_bad_dates.append(date)

        # official/lazy coverage checks from compare payload
        miss_off = cp.get("missing_official_fixture_ids_in_lazy") or []
        miss_ab = cp.get("missing_official_ab_fixture_ids_in_lazy") or []
        if miss_off:
            uncovered_official_dates.append(f"{date}:{len(miss_off)}")
        if miss_ab:
            uncovered_ab_dates.append(f"{date}:{len(miss_ab)}")

        # mismatch in common fixtures
        mismatch = int(row.get("official_grade_mismatch_count") or 0)
        if mismatch != 0:
            mismatch_dates.append(f"{date}:{mismatch}")

        off_ids = set(str(x) for x in (cp.get("official_fixture_ids") or []))
        lazy_ids = set(str(x) for x in (cp.get("lazy_fixture_ids") or []))
        shadow_only_ids_all |= (lazy_ids - off_ids)

    _ok(result["checks"], "lazy_scout_nonzero_each_success_date", len(lazy_zero_dates) == 0, ",".join(lazy_zero_dates))
    if lazy_zero_dates:
        result["blockers"].append("lazy_scout_zero_detected")

    _ok(result["checks"], "common_fixture_mismatch_zero", len(mismatch_dates) == 0, ",".join(mismatch_dates))
    if mismatch_dates:
        result["blockers"].append("official_grade_mismatch_detected")

    _ok(result["checks"], "official_fixture_covered_by_lazy", len(uncovered_official_dates) == 0, ",".join(uncovered_official_dates))
    if uncovered_official_dates:
        result["blockers"].append("official_fixture_not_covered")

    _ok(result["checks"], "official_ab_fixture_covered_by_lazy", len(uncovered_ab_dates) == 0, ",".join(uncovered_ab_dates))
    if uncovered_ab_dates:
        result["blockers"].append("official_ab_not_covered")

    _ok(result["checks"], "every_success_date_no_push", len(no_push_bad_dates) == 0, ",".join(no_push_bad_dates))
    _ok(result["checks"], "every_success_date_whitelist", len(whitelist_bad_dates) == 0, ",".join(whitelist_bad_dates))
    _ok(result["checks"], "every_success_date_serial", len(serial_bad_dates) == 0, ",".join(serial_bad_dates))
    _ok(result["checks"], "every_success_date_modes_explicit", len(mode_bad_dates) == 0, ",".join(mode_bad_dates))
    if no_push_bad_dates or whitelist_bad_dates or serial_bad_dates or mode_bad_dates:
        result["blockers"].append("date_level_command_contract_broken")

    # savings positive or explained
    _ok(result["checks"], "estimated_saved_positive_or_explained", total_saved > 0, str(total_saved))
    if total_saved <= 0:
        result["warnings"].append("estimated_saved_not_positive")

    # pending/validation/livebet/qq isolation
    model_file = _latest("v4_control_center_model_*.json", STATUS)
    model = {}
    if model_file and model_file.exists():
        model = json.loads(model_file.read_text(encoding="utf-8"))
    pending = model.get("pending_bet_candidates") or []
    pending_ids = {
        str((x or {}).get("fixture_id") or "").strip()
        for x in pending
        if isinstance(x, dict)
    }
    pending_ids.discard("")
    shadow_pending_hits = sorted(shadow_only_ids_all & pending_ids)
    _ok(result["checks"], "shadow_only_not_in_pending_bet_candidates", len(shadow_pending_hits) == 0, f"hits={len(shadow_pending_hits)}")
    if shadow_pending_hits:
        result["blockers"].append("shadow_only_entered_pending")

    # validation/livetbet/qq guard by existing checkers
    ok_dash, out_dash = _run("check_v4_rf_shadow_dashboard_review.py")
    dash_payload = _extract_json_line(out_dash)
    dash_flags = {
        str((x or {}).get("name") or ""): bool((x or {}).get("ok"))
        for x in (dash_payload.get("checks") or [])
        if isinstance(x, dict)
    }
    _ok(
        result["checks"],
        "validation_not_using_shadow_grade",
        ok_dash and dash_flags.get("validation_not_using_shadow_grade", False),
        out_dash[-260:],
    )
    _ok(
        result["checks"],
        "live_bet_not_using_shadow_grade",
        ok_dash and dash_flags.get("live_bet_not_using_shadow_grade", False),
        out_dash[-260:],
    )
    _ok(
        result["checks"],
        "qq_not_using_shadow_grade",
        ok_dash and dash_flags.get("qq_not_using_shadow_grade", False),
        out_dash[-260:],
    )
    if not ok_dash:
        result["blockers"].append("dashboard_shadow_guard_failed")

    ok_default, out_default = _run("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", ok_default, out_default[-260:])
    if not ok_default:
        result["blockers"].append("default_rules_guard_failed")

    ok_slim, out_slim = _run("check_v4_system_slim_and_whitelist_mode.py")
    _ok(result["checks"], "cron_whitelist_guard_pass", ok_slim, out_slim[-260:])
    if not ok_slim:
        result["blockers"].append("cron_whitelist_guard_failed")

    ok_no_market, out_nm = _run("check_v4_no_market_core_validation_skip.py")
    nm_soft = ok_no_market or ("WARN_ONLY" in out_nm)
    _ok(result["checks"], "validation_livebet_guard_soft_pass", nm_soft, out_nm[-260:])
    if not nm_soft:
        result["blockers"].append("validation_livebet_guard_failed")

    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    _ok(result["checks"], "qq_disabled", "V4_QQ_ENABLED = False" in brief_src)

    # no staged runtime artifacts / secrets
    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    secret_hits = [x for x in staged if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    runtime_hits = [x for x in staged if x.startswith("data/runtime/")]
    _ok(result["checks"], "runtime_artifact_not_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    if runtime_hits:
        result["blockers"].append("runtime_artifact_staged")
    if secret_hits:
        result["blockers"].append("secrets_staged")

    # attach aggregate counters for report reuse
    result["aggregate"] = {
        "h2h_required_true_total": total_h2h_t,
        "h2h_required_false_total": total_h2h_f,
        "h2h_collected_total": total_h2h_c,
        "h2h_skipped_total": total_h2h_s,
        "events_required_true_total": total_e_t,
        "events_required_false_total": total_e_f,
        "events_collected_total": total_e_c,
        "events_skipped_total": total_e_s,
        "cpl_required_true_total": total_cpl_t,
        "cpl_required_false_total": total_cpl_f,
        "cpl_collected_total": total_cpl_c,
        "cpl_skipped_total": total_cpl_s,
        "estimated_saved_total": total_saved,
        "shadow_only_fixture_total": len(shadow_only_ids_all),
    }

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    return _finish(result)


def _finish(result: dict[str, Any]) -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_collection_pipeline_expanded_canary_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
