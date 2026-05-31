#!/usr/bin/env python3
"""Checker for Phase 3C RF shadow promotion dryrun/replay."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUT = ROOT / "data" / "runtime" / "acceptance"


def _ok(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _latest_report_path() -> Path | None:
    files = sorted(OUT.glob("v4_rf_shadow_promotion_dryrun_replay_*.json"))
    return files[-1] if files else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bool(v: Any) -> bool:
    return bool(v)


def main() -> int:
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    runner = TOOLS / "run_v4_rf_shadow_promotion_dryrun_replay.py"
    _ok(checks, "runner_exists", runner.exists(), str(runner))
    if not runner.exists():
        blockers.append("missing_runner")

    # verify runner safety flags in source
    src = runner.read_text(encoding="utf-8", errors="replace") if runner.exists() else ""
    _ok(checks, "runner_no_api_called", "api_called\": False" in src or "api_called': False" in src)
    _ok(checks, "runner_no_pending_write", "pending_logic_changed\": False" in src or "pending_logic_changed': False" in src)
    _ok(checks, "runner_no_qq_push", "qq_pushed\": False" in src or "qq_pushed': False" in src)

    # execute runner once (read-only)
    date = ""
    if runner.exists():
        p = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True)
        _ok(checks, "runner_exec_ok", p.returncode == 0, (p.stdout + p.stderr)[-300:])
        if p.returncode != 0:
            blockers.append("runner_exec_failed")
        else:
            try:
                payload = json.loads(p.stdout)
                date = str(payload.get("scan_date") or "")
            except Exception:
                warnings.append("runner_stdout_not_json")

    report_path = _latest_report_path()
    _ok(checks, "report_exists", report_path is not None, str(report_path) if report_path else "")
    if report_path is None:
        blockers.append("missing_report")

    report = _read_json(report_path) if report_path else {}

    # required top fields
    top = [
        "distribution",
        "recent5_bilateral_gate_stats",
        "coverage",
        "safety_market_h2h_events_cpl",
        "safety_checks",
        "rows",
    ]
    for k in top:
        ok = isinstance(report.get(k), dict) if k != "rows" else isinstance(report.get(k), list)
        _ok(checks, f"field:{k}", ok)
        if not ok:
            blockers.append(f"missing_field:{k}")

    # replay fields presence
    rfp = report.get("replay_fields_presence", {}) if isinstance(report.get("replay_fields_presence"), dict) else {}
    for k in [
        "shadow_dryrun_grade",
        "shadow_dryrun_score",
        "shadow_dryrun_reason",
        "current_official_grade",
        "official_vs_shadow_delta",
        "promotion_delta_reason",
        "dryrun_allowed_to_promote",
        "dryrun_block_reason",
    ]:
        ok = _bool(rfp.get(k))
        _ok(checks, f"replay_field:{k}", ok)
        if not ok:
            blockers.append(f"missing_replay_field:{k}")

    # safety no mutation
    safety = report.get("safety_checks", {}) if isinstance(report.get("safety_checks"), dict) else {}
    for k in [
        "official_grade_changed",
        "production_grade_mode_changed",
        "pending_logic_changed",
        "qq_pushed",
        "validation_touched",
        "live_bet_touched",
        "cron_modified",
    ]:
        ok = not _bool(safety.get(k))
        _ok(checks, f"safety:{k}_false", ok, str(safety.get(k)))
        if not ok:
            blockers.append(f"safety_violation:{k}")

    # recent5 gate stats
    s5 = report.get("recent5_bilateral_gate_stats", {}) if isinstance(report.get("recent5_bilateral_gate_stats"), dict) else {}
    for k in [
        "recent5_bilateral_gate_pass_count",
        "hot_anchor_pass_count",
        "dual_heat_pass_count",
        "recent5_bilateral_gate_fail_count",
        "recent5_fail_cap_to_C_count",
        "rf_strong_confirmed_b_floor_exception_count",
        "exception_to_B_count",
        "exception_to_A_count",
    ]:
        ok = k in s5
        _ok(checks, f"recent5_stat:{k}", ok)
        if not ok:
            blockers.append(f"missing_recent5_stat:{k}")

    ex_to_a = int(s5.get("exception_to_A_count") or 0)
    _ok(checks, "exception_to_A_is_zero", ex_to_a == 0, str(ex_to_a))
    if ex_to_a != 0:
        blockers.append("exception_promoted_to_A")

    # market/h2h/events/cpl safety stats
    sm = report.get("safety_market_h2h_events_cpl", {}) if isinstance(report.get("safety_market_h2h_events_cpl"), dict) else {}
    must_zero = [
        "market_no_data_A_found",
        "market_extreme_veto_non_skip_found",
        "market_manufactured_AB_found",
        "h2h_manufactured_AB_found",
        "events_manufactured_AB_found",
        "cpl_changed_official_found",
        "cpl_touched_live_bet_found",
        "cpl_touched_validation_found",
    ]
    for k in must_zero:
        v = int(sm.get(k) or 0)
        ok = v == 0
        _ok(checks, f"safe_zero:{k}", ok, str(v))
        if not ok:
            blockers.append(f"non_zero:{k}")

    # coverage checks
    cov = report.get("coverage", {}) if isinstance(report.get("coverage"), dict) else {}
    mismatch = int(cov.get("common_fixtures_official_grade_mismatch_count") or 0)
    _ok(checks, "official_grade_mismatch_zero", mismatch == 0, str(mismatch))
    if mismatch != 0:
        blockers.append("official_grade_mismatch_detected")

    cover_ok = _bool(cov.get("official_fixture_coverage_ok"))
    _ok(checks, "official_fixture_coverage_ok", cover_ok, str(cov.get("official_fixture_coverage_ok")))
    if not cover_ok:
        blockers.append("official_fixture_not_covered")

    cover_ab_ok = _bool(cov.get("official_ab_fixture_coverage_ok"))
    _ok(checks, "official_ab_fixture_coverage_ok", cover_ab_ok, str(cov.get("official_ab_fixture_coverage_ok")))
    if not cover_ab_ok:
        blockers.append("official_ab_fixture_not_covered")

    shadow_only_pending = int(cov.get("shadow_only_rows_entered_pending_count") or 0)
    _ok(checks, "shadow_only_not_in_pending", shadow_only_pending == 0, str(shadow_only_pending))
    if shadow_only_pending != 0:
        blockers.append("shadow_only_entered_pending")

    # undefined/null/nan guard (string-level)
    report_text = json.dumps(report, ensure_ascii=False)
    bad_tokens = [t for t in ["undefined", "NaN"] if t in report_text]
    _ok(checks, "no_undefined_nan", len(bad_tokens) == 0, ",".join(bad_tokens))
    if bad_tokens:
        blockers.append("undefined_or_nan_in_report")

    # no runtime artifacts staged / no secrets staged
    gp = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged = [x.strip() for x in gp.stdout.splitlines() if x.strip()]
    runtime_staged = any(p.startswith("v2_football_quant/data/runtime/") or p.startswith("data/runtime/") for p in staged)
    _ok(checks, "runtime_artifact_not_staged", not runtime_staged, ";".join(staged))
    if runtime_staged:
        blockers.append("runtime_artifact_staged")

    secrets_staged = any(any(k in p.lower() for k in [".env", "secret", "token", "apikey", "api_key"]) for p in staged)
    _ok(checks, "no_secrets_staged", not secrets_staged)
    if secrets_staged:
        blockers.append("secrets_staged")

    result = {
        "checker": "check_v4_rf_shadow_promotion_dryrun",
        "generated_at": datetime_now_iso(),
        "scan_date": date,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


def datetime_now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
