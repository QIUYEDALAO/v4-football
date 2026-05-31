#!/usr/bin/env python3
"""Phase 3D-F checker: RF shadow promotion replay field completeness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUT = ROOT / "data" / "runtime" / "acceptance"


def _ok(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _latest_report(date: str | None) -> Path | None:
    if date:
        p = OUT / f"v4_rf_shadow_promotion_dryrun_replay_{date}.json"
        return p if p.exists() else None
    fs = sorted(OUT.glob("v4_rf_shadow_promotion_dryrun_replay_*.json"))
    return fs[-1] if fs else None


def _read_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _staged_files() -> list[str]:
    p = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="20260531")
    args = ap.parse_args()

    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []

    runner = TOOLS / "run_v4_rf_shadow_promotion_dryrun_replay.py"
    _ok(checks, "runner_exists", runner.exists(), str(runner))
    if not runner.exists():
        blockers.append("missing_runner")

    if runner.exists():
        src = runner.read_text(encoding="utf-8", errors="replace")
        for key, pat in [
            ("arg_date_exists", "--date"),
            ("arg_source_artifact_exists", "--source-artifact"),
            ("arg_official_artifact_exists", "--official-artifact"),
            ("arg_strict_field_coverage_exists", "--strict-field-coverage"),
        ]:
            ok = pat in src
            _ok(checks, key, ok)
            if not ok:
                blockers.append(f"missing_runner_arg:{pat}")

    # run once for target date
    if runner.exists():
        p = subprocess.run([
            sys.executable,
            str(runner),
            "--date",
            args.date,
            "--strict-field-coverage",
        ], capture_output=True, text=True)
        _ok(checks, "runner_exec_ok", p.returncode == 0, (p.stdout + p.stderr)[-400:])
        if p.returncode != 0:
            blockers.append("runner_exec_failed")

    report_path = _latest_report(args.date)
    _ok(checks, "report_exists", report_path is not None, str(report_path) if report_path else "")
    if report_path is None:
        blockers.append("missing_report")
        out = {
            "checker": "check_v4_rf_shadow_promotion_dryrun",
            "generated_at": datetime.now().isoformat(),
            "checks": checks,
            "warnings": warnings,
            "blockers": blockers,
            "conclusion": "BLOCKER",
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    report = _read_json(report_path)

    # required coverage sections
    for k in [
        "official_artifact",
        "recent5_coverage",
        "bfloor_coverage",
        "safety_coverage",
        "safety_checks",
        "distribution",
        "final_replay_conclusion",
    ]:
        ok = k in report
        _ok(checks, f"field:{k}", ok)
        if not ok:
            blockers.append(f"missing_field:{k}")

    official = report.get("official_artifact", {}) if isinstance(report.get("official_artifact"), dict) else {}
    recent5 = report.get("recent5_coverage", {}) if isinstance(report.get("recent5_coverage"), dict) else {}
    bfloor = report.get("bfloor_coverage", {}) if isinstance(report.get("bfloor_coverage"), dict) else {}
    safety_cov = report.get("safety_coverage", {}) if isinstance(report.get("safety_coverage"), dict) else {}
    safety = report.get("safety_checks", {}) if isinstance(report.get("safety_checks"), dict) else {}
    dist = report.get("distribution", {}) if isinstance(report.get("distribution"), dict) else {}

    # official missing must not be fake 0/0/0/0
    off_status = str(official.get("official_artifact_status") or "")
    off_dist = official.get("current_official_grade_distribution")
    _ok(checks, "official_artifact_status_present", off_status in {"FOUND", "MISSING", "CONFLICT"}, off_status)
    if off_status not in {"FOUND", "MISSING", "CONFLICT"}:
        blockers.append("invalid_official_artifact_status")

    if off_status == "MISSING":
        bad_zero = isinstance(off_dist, dict) and all(int(off_dist.get(k, 0) or 0) == 0 for k in ["A", "B", "C", "SKIP"])
        _ok(checks, "official_missing_not_fake_zero_dist", not bad_zero, str(off_dist))
        if bad_zero:
            blockers.append("official_missing_fake_zero_distribution")
    else:
        _ok(checks, "official_dist_dict_when_found", isinstance(off_dist, dict), str(type(off_dist)))
        if not isinstance(off_dist, dict):
            blockers.append("official_distribution_missing")

    # delta distinction
    delta_dist = dist.get("official_vs_shadow_delta", {}) if isinstance(dist.get("official_vs_shadow_delta"), dict) else {}
    if off_status == "MISSING":
        has_missing_delta = "OFFICIAL_MISSING_SHADOW_ONLY" in delta_dist
        _ok(checks, "delta_has_official_missing_shadow_only", has_missing_delta, str(delta_dist))
        if not has_missing_delta:
            blockers.append("missing_official_missing_shadow_only_delta")

    # recent5 coverage fields
    for k in [
        "recent5_gate_field_coverage_status",
        "recent5_gate_reconstructable",
        "recent5_gate_available_count",
        "recent5_gate_unknown_count",
        "recent5_gate_missing_fields",
    ]:
        ok = k in recent5
        _ok(checks, f"recent5_field:{k}", ok)
        if not ok:
            blockers.append(f"missing_recent5_field:{k}")

    # UNKNOWN not counted as zero-pass
    r5_unknown = int(recent5.get("recent5_gate_unknown_count") or 0)
    r5_available = int(recent5.get("recent5_gate_available_count") or 0)
    zero_as_pass = r5_unknown > 0 and r5_available == 0 and str(recent5.get("recent5_gate_field_coverage_status")) == "COMPLETE"
    _ok(checks, "unknown_not_counted_as_zero_pass_recent5", not zero_as_pass, f"unknown={r5_unknown},available={r5_available},status={recent5.get('recent5_gate_field_coverage_status')}")
    if zero_as_pass:
        blockers.append("recent5_unknown_counted_as_pass")

    # bfloor coverage fields
    for k in [
        "bfloor_exception_field_coverage_status",
        "bfloor_exception_available_count",
        "bfloor_exception_unknown_count",
        "bfloor_exception_missing_fields",
    ]:
        ok = k in bfloor
        _ok(checks, f"bfloor_field:{k}", ok)
        if not ok:
            blockers.append(f"missing_bfloor_field:{k}")

    # safety coverage fields
    for k in [
        "safety_field_coverage_status",
        "market_safety_coverage_status",
        "h2h_safety_coverage_status",
        "events_safety_coverage_status",
        "cpl_safety_coverage_status",
        "safety_unknown_count",
        "safety_missing_fields",
    ]:
        ok = k in safety_cov
        _ok(checks, f"safety_cov_field:{k}", ok)
        if not ok:
            blockers.append(f"missing_safety_coverage_field:{k}")

    # final conclusion guard
    final_conclusion = str(report.get("final_replay_conclusion") or "")
    _ok(checks, "final_conclusion_present", final_conclusion in {
        "SUFFICIENT_SAMPLE_REPLAY_BASELINE_READY",
        "SUFFICIENT_SAMPLE_BUT_FIELD_COVERAGE_INCOMPLETE",
        "OFFICIAL_ARTIFACT_MISSING_BLOCKER",
        "RECENT5_GATE_COVERAGE_INCOMPLETE_BLOCKER",
        "FAIL_NEED_CODE_REVIEW",
    }, final_conclusion)
    if final_conclusion not in {
        "SUFFICIENT_SAMPLE_REPLAY_BASELINE_READY",
        "SUFFICIENT_SAMPLE_BUT_FIELD_COVERAGE_INCOMPLETE",
        "OFFICIAL_ARTIFACT_MISSING_BLOCKER",
        "RECENT5_GATE_COVERAGE_INCOMPLETE_BLOCKER",
        "FAIL_NEED_CODE_REVIEW",
    }:
        blockers.append("invalid_final_conclusion")

    r5_cov = str(recent5.get("recent5_gate_field_coverage_status") or "")
    if r5_cov in {"MISSING", "PARTIAL"} and final_conclusion == "SUFFICIENT_SAMPLE_REPLAY_BASELINE_READY":
        _ok(checks, "coverage_incomplete_not_baseline_ready", False, final_conclusion)
        blockers.append("coverage_incomplete_but_baseline_ready")
    else:
        _ok(checks, "coverage_incomplete_not_baseline_ready", True, final_conclusion)

    # no mutation safety
    for k in [
        "official_grade_changed",
        "production_grade_mode_changed",
        "pending_logic_changed",
        "qq_pushed",
        "validation_touched",
        "live_bet_touched",
        "cron_modified",
    ]:
        ok = not bool(safety.get(k))
        _ok(checks, f"safety:{k}_false", ok, str(safety.get(k)))
        if not ok:
            blockers.append(f"safety_violation:{k}")

    # defaults guard
    dg = subprocess.run([sys.executable, str(TOOLS / "check_v4_production_default_rules_guard.py")], capture_output=True, text=True)
    _ok(checks, "default_rules_guard_exec_ok", dg.returncode == 0, (dg.stdout + dg.stderr)[-300:])
    if dg.returncode != 0:
        blockers.append("default_rules_guard_failed")

    # staged safety
    staged = _staged_files()
    runtime_staged = any(("data/runtime/" in f) or ("data/daily_reports/" in f) for f in staged)
    _ok(checks, "runtime_artifact_not_staged", not runtime_staged, ";".join(staged))
    if runtime_staged:
        blockers.append("runtime_artifact_staged")

    secrets_staged = any(any(k in f.lower() for k in [".env", "secret", "token", "apikey", "api_key"]) for f in staged)
    _ok(checks, "no_secrets_staged", not secrets_staged)
    if secrets_staged:
        blockers.append("secrets_staged")

    result = {
        "checker": "check_v4_rf_shadow_promotion_dryrun",
        "generated_at": datetime.now().isoformat(),
        "scan_date": args.date,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
