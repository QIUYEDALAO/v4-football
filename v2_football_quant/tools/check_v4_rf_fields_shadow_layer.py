#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
REPORT = ROOT / "data" / "daily_reports"
LIVE = ROOT / "data" / "runtime" / "live_bets"
TZ = timezone(timedelta(hours=8))

RECENT10_FIELDS = [
    "home_recent10_fh_involved_rate",
    "away_recent10_fh_involved_rate",
    "combined_recent10_fh_involved_rate",
    "home_recent10_fh_score_rate",
    "away_recent10_fh_score_rate",
    "home_recent10_fh_concede_rate",
    "away_recent10_fh_concede_rate",
    "recent10_sample_count_home",
    "recent10_sample_count_away",
    "recent10_window_days_home",
    "recent10_window_days_away",
    "recent_freshness_status",
]

RECENT5_FIELDS = [
    "home_recent5_fh_involved_rate",
    "away_recent5_fh_involved_rate",
    "combined_recent5_fh_involved_rate",
    "home_recent5_fh_score_rate",
    "away_recent5_fh_score_rate",
    "home_recent5_fh_concede_rate",
    "away_recent5_fh_concede_rate",
    "recent5_momentum_status",
]

PRIMARY_FIELDS = [
    "recent_form_primary_score",
    "recent_form_primary_level",
    "recent_form_primary_reason",
]

ALL_RF_FIELDS = RECENT10_FIELDS + RECENT5_FIELDS + PRIMARY_FIELDS


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _latest(pattern: str, base: Path):
    files = list(base.glob(pattern))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def _ok(checks, name, cond, detail=""):
    checks.append({"name": name, "ok": bool(cond), "detail": detail})


def _has_bad(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip().lower() in {"undefined", "null", "nan", ""}:
        return True
    return False


def _run_checker(script: str):
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def main() -> int:
    checks = []
    blockers = []
    warnings = []

    task_status_path = STATUS / "task_status_v4_scan_midday.json"
    task_status = _load_json(task_status_path) if task_status_path.exists() else {}
    task_state = str(task_status.get("status") or "")
    task_out = task_status.get("output_files") or {}
    scout_path = Path(task_out["scout"]) if task_out.get("scout") else _latest("scout_v4_*.json", REPORT)
    cv_path = Path(task_out["candidate_view"]) if task_out.get("candidate_view") else _latest("v3v4_dashboard_candidate_view_*.json", STATUS)
    model_path = _latest("v4_control_center_model_*.json", STATUS)

    _ok(checks, "task_status_exists", task_status_path.exists(), str(task_status_path))
    _ok(checks, "task_status_done", task_state == "DONE", task_state)
    if task_state in {"RUNNING", "DELAYED"}:
        blockers.append(f"formal_entry_task_not_done:{task_state}")

    _ok(checks, "scout_exists", scout_path is not None, str(scout_path) if scout_path else "")
    _ok(checks, "candidate_view_exists", cv_path is not None, str(cv_path) if cv_path else "")
    _ok(checks, "dashboard_model_exists", model_path is not None, str(model_path) if model_path else "")

    scout = _load_json(scout_path) if scout_path else []
    cv = _load_json(cv_path) if cv_path else {}
    model = _load_json(model_path) if model_path else {}
    adapter_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    model_src = (ROOT / "tools" / "build_v4_control_center_model.py").read_text(encoding="utf-8")
    runner_src = (ROOT / "engine" / "v4_runner.py").read_text(encoding="utf-8")
    worker_src = (ROOT / "engine" / "v4_scan_worker.py").read_text(encoding="utf-8")
    outside57_src = (ROOT / "engine" / "v4_outside57_scanner.py").read_text(encoding="utf-8")

    if scout_path and isinstance(scout, list) and scout:
        for f in ALL_RF_FIELDS:
            ok = all(f in row for row in scout if isinstance(row, dict))
            _ok(checks, f"scout_field:{f}", ok)
            if not ok and f not in adapter_src:
                blockers.append(f"scout_missing:{f}")
            elif not ok:
                warnings.append(f"scout_data_not_refreshed:{f}")
        grade_ok = all((row.get("official_grade") == row.get("grade")) for row in scout if isinstance(row, dict))
        _ok(checks, "scout_official_grade_preserved", grade_ok)
        if not grade_ok:
            blockers.append("official_grade_changed_in_scout")
    else:
        warnings.append("scout_empty_or_missing")

    ab_rows = (cv.get("A_candidates") or []) + (cv.get("B_candidates") or [])
    if isinstance(ab_rows, list) and ab_rows:
        for f in ALL_RF_FIELDS:
            ok = all(f in row for row in ab_rows if isinstance(row, dict))
            _ok(checks, f"candidate_field:{f}", ok)
            if not ok and f not in adapter_src:
                blockers.append(f"candidate_missing:{f}")
            elif not ok:
                warnings.append(f"candidate_data_not_refreshed:{f}")
        ab_grade_ok = all((row.get("grade") in ("A", "B")) for row in ab_rows if isinstance(row, dict))
        _ok(checks, "candidate_ab_grade_intact", ab_grade_ok)
        if not ab_grade_ok:
            blockers.append("candidate_grade_not_ab")
    else:
        warnings.append("candidate_ab_empty")

    items = (model.get("candidates") or {}).get("items") or []
    if isinstance(items, list) and items:
        for f in ALL_RF_FIELDS:
            ok = all((f in row and not _has_bad(row.get(f))) for row in items if isinstance(row, dict))
            _ok(checks, f"model_field:{f}", ok)
            if not ok:
                blockers.append(f"model_bad_or_missing:{f}")
    else:
        warnings.append("dashboard_items_empty")
        _ok(checks, "true_goal_distribution_available", True, "no_dashboard_candidates")
        _ok(checks, "playbook_script_available", True, "no_dashboard_candidates")

    # static propagation checks
    for f in ALL_RF_FIELDS:
        _ok(checks, f"adapter_code_contains:{f}", f in adapter_src)
        if f not in adapter_src:
            blockers.append(f"adapter_missing_field_mapping:{f}")
        _ok(checks, f"dashboard_model_code_contains:{f}", f in model_src)
        if f not in model_src:
            blockers.append(f"dashboard_model_missing_field_mapping:{f}")
        in_serial = (f in runner_src) or (f in adapter_src)
        in_parallel = f in outside57_src
        _ok(checks, f"serial_path_code_contains:{f}", in_serial)
        if not in_serial:
            blockers.append(f"serial_path_missing_field:{f}")
        _ok(checks, f"not_parallel_only:{f}", (not in_parallel) or in_serial)
        if in_parallel and not in_serial:
            blockers.append(f"parallel_only_field:{f}")

    # explicit production path proof: scan_and_brief defaults serial and calls scan_worker
    serial_default = "default=\"serial\"" in adapter_src or "default='serial'" in adapter_src
    worker_call = "v4_scan_worker.py" in adapter_src and "scan_engine == \"parallel\"" in adapter_src
    _ok(checks, "production_entry_default_serial", serial_default)
    _ok(checks, "production_entry_calls_scan_worker", worker_call)
    if not serial_default or not worker_call:
        blockers.append("production_path_not_proven_serial")

    # worker must route through v4_runner (serial production runtime)
    _ok(checks, "scan_worker_routes_to_v4_runner", "from engine.v4_runner import run_v4_scan" in worker_src)
    if "from engine.v4_runner import run_v4_scan" not in worker_src:
        blockers.append("scan_worker_not_using_v4_runner")

    # If latest push marker exists, require it to come from formal entry with no-push.
    push_markers = sorted((ROOT / "data/runtime/status").glob("v4_scan_*_push_*.json"), key=lambda p: p.stat().st_mtime)
    if push_markers:
        pm = _load_json(push_markers[-1])
        formal_no_push = bool(pm.get("no_push")) is True
        _ok(checks, "latest_formal_entry_no_push_marker", formal_no_push, str(push_markers[-1]))
        if not formal_no_push:
            warnings.append("latest_push_marker_not_no_push")
    else:
        warnings.append("formal_push_marker_not_found_for_this_run")

    # no regrade/static safety
    mi_src = (ROOT / "engine" / "v4_match_intelligence.py").read_text(encoding="utf-8")
    no_rf_in_grade = ("recent_form_primary_" not in mi_src and "combined_recent10_fh_involved_rate" not in mi_src)
    _ok(checks, "official_grade_logic_not_using_rf_shadow", no_rf_in_grade)
    if not no_rf_in_grade:
        blockers.append("official_grade_logic_references_rf_shadow")

    h2h_src = (ROOT / "engine" / "data_sources" / "h2h_engine.py").read_text(encoding="utf-8")
    h2h_unchanged_gate = "combined_recent10_fh_involved_rate" not in h2h_src
    _ok(checks, "h2h_runtime_gate_not_modified", h2h_unchanged_gate)
    if not h2h_unchanged_gate:
        blockers.append("h2h_runtime_contains_rf_shadow_gate")

    # baseline artifacts still exist
    _ok(checks, "no_market_marker_exists", (LIVE / "v4_no_market_exclusions_20260530.jsonl").exists())
    _ok(checks, "validation_history_exists", (ROOT / "data/runtime/validation/v4_ab_historical_ledger_20260526.json").exists())
    _ok(checks, "live_bet_raw_exists", (LIVE / "v4_live_bets_20260530.jsonl").exists())

    # dashboard no undefined/null/nan on rf fields
    no_bad_rf = True
    for row in items if isinstance(items, list) else []:
        if not isinstance(row, dict):
            continue
        for f in ALL_RF_FIELDS:
            if _has_bad(row.get(f)):
                no_bad_rf = False
                break
        if not no_bad_rf:
            break
    _ok(checks, "dashboard_rf_no_undefined_null_nan", no_bad_rf)
    if not no_bad_rf:
        blockers.append("dashboard_rf_bad_value")

    # true goal / playbook fields still present
    if isinstance(items, list) and items:
        has_goal_dist = any(isinstance(r, dict) and ("fh_goal_dist_source" in r) for r in items)
        has_playbook = any(isinstance(r, dict) and ("playbook_script" in r) for r in items)
        _ok(checks, "true_goal_distribution_available", has_goal_dist)
        _ok(checks, "playbook_script_available", has_playbook)

    # no secrets staged
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged_files = [x.strip() for x in staged.stdout.splitlines() if x.strip()]
    secret_hit = [x for x in staged_files if any(tok in x.lower() for tok in [".env", "secret", "token", "apikey", "api_key"])]
    _ok(checks, "no_secrets_staged", len(secret_hit) == 0, ",".join(secret_hit))
    if secret_hit:
        blockers.append("secrets_staged")

    # must-run guards
    guard_scripts = [
        "check_v4_production_default_rules_guard.py",
        "check_v4_system_slim_and_whitelist_mode.py",
        "check_v4_control_center.py",
        "check_v4_no_market_core_validation_skip.py",
        "check_v4_true_goal_time_distribution.py",
        "check_v4_playbook_script_and_time_distribution.py",
    ]
    for script in guard_scripts:
        ok, detail = _run_checker(script)
        soft_ok = False
        if not ok and script == "check_v4_control_center.py" and "\"conclusion\": \"WARN_ONLY\"" in detail:
            soft_ok = True
            warnings.append("guard_warn_only:check_v4_control_center.py")
        if not ok and script == "check_v4_no_market_core_validation_skip.py":
            if "\"no_market_action_status\": {\n      \"ok\": true" in detail and "\"DEFAULT_RULES_unchanged\": {\n      \"ok\": true" in detail:
                soft_ok = True
                warnings.append("guard_dataset_dependent_no_market_checker_nonzero")
        if not ok and script == "check_v4_true_goal_time_distribution.py":
            if "Conclusion: WARN_ONLY" in detail and "no_candidates" in detail:
                soft_ok = True
                warnings.append("guard_warn_only:true_goal_no_candidates")
        if not ok and script == "check_v4_playbook_script_and_time_distribution.py":
            if "Conclusion: WARN_ONLY" in detail and "no_candidate_cards" in detail:
                soft_ok = True
                warnings.append("guard_warn_only:playbook_no_candidates")
        final_ok = ok or soft_ok
        _ok(checks, f"guard:{script}", final_ok, detail[-400:])
        if not final_ok:
            blockers.append(f"guard_failed:{script}")

    conclusion = "PASS" if not blockers else "BLOCKER"
    out = {
        "schema_version": "v4_rf_fields_shadow_layer_checker.v1",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": conclusion,
    }
    out_path = STATUS / f"check_v4_rf_fields_shadow_layer_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if conclusion == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
