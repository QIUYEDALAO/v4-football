#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "runtime" / "acceptance"
STATUS = ROOT / "data" / "runtime" / "status"
TZ = timezone(timedelta(hours=8))


def _ok(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _latest(date: str | None = None) -> Path | None:
    if date:
        p = OUT / f"v4_rf_shadow_promotion_dryrun_replay_multi_artifact_{date}.json"
        if p.exists():
            return p
    fs = sorted(OUT.glob("v4_rf_shadow_promotion_dryrun_replay_multi_artifact_*.json"))
    return fs[-1] if fs else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(cmd: list[str]) -> tuple[bool, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def main() -> int:
    date = "20260531"
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    runner = ROOT / "tools" / "run_v4_rf_shadow_promotion_dryrun_replay.py"
    _ok(checks, "runner_exists", runner.exists(), str(runner))
    if not runner.exists():
        blockers.append("missing_runner")

    if runner.exists():
        ok, out = _run([
            sys.executable,
            str(runner),
            "--multi-artifact",
            "--min-fixtures", "30",
            "--baseline-threshold", "77",
            "--candidate-threshold", "73.5",
        ])
        _ok(checks, "runner_multi_artifact_exec_ok", ok, out[-400:])
        if not ok:
            blockers.append("runner_multi_artifact_exec_failed")

    report_path = _latest(date)
    _ok(checks, "multi_artifact_report_exists", report_path is not None, str(report_path) if report_path else "")
    if report_path is None:
        blockers.append("missing_multi_artifact_report")
        return _finish(checks, warnings, blockers)

    report = _read_json(report_path)

    _ok(checks, "multi_artifact_mode_true", bool(report.get("multi_artifact_mode")) is True, str(report.get("multi_artifact_mode")))
    if bool(report.get("multi_artifact_mode")) is not True:
        blockers.append("multi_artifact_mode_false")

    _ok(checks, "min_fixtures_filter_30", int(report.get("min_fixtures") or 0) == 30, str(report.get("min_fixtures")))
    if int(report.get("min_fixtures") or 0) != 30:
        blockers.append("min_fixtures_not_30")

    _ok(checks, "baseline_threshold_77", abs(float(report.get("baseline_threshold") or 0) - 77.0) < 1e-9, str(report.get("baseline_threshold")))
    if abs(float(report.get("baseline_threshold") or 0) - 77.0) >= 1e-9:
        blockers.append("baseline_threshold_changed")

    _ok(checks, "candidate_threshold_73_5", abs(float(report.get("candidate_threshold") or 0) - 73.5) < 1e-9, str(report.get("candidate_threshold")))
    if abs(float(report.get("candidate_threshold") or 0) - 73.5) >= 1e-9:
        blockers.append("candidate_threshold_invalid")

    _ok(checks, "default_threshold_unchanged_73_5", abs(float(report.get("default_rescue_threshold") or 0) - 73.5) < 1e-9, str(report.get("default_rescue_threshold")))
    if abs(float(report.get("default_rescue_threshold") or 0) - 73.5) >= 1e-9:
        blockers.append("default_threshold_changed")

    total = int(report.get("artifact_count_total") or 0)
    sufficient = int(report.get("artifact_count_sufficient") or 0)
    small = int(report.get("artifact_count_sample_too_small") or 0)
    _ok(checks, "artifact_counts_non_negative", total >= 0 and sufficient >= 0 and small >= 0, f"total={total},sufficient={sufficient},small={small}")

    artifact_results = report.get("artifact_results") if isinstance(report.get("artifact_results"), list) else []
    _ok(checks, "artifact_results_present", isinstance(artifact_results, list), str(type(report.get("artifact_results"))))
    if not isinstance(artifact_results, list):
        blockers.append("artifact_results_missing")
        artifact_results = []

    # sample too small artifacts should not enter aggregate
    small_dates = {
        str(x.get("date"))
        for x in artifact_results
        if isinstance(x, dict) and str(x.get("sample_status")) == "SAMPLE_TOO_SMALL_WARN_ONLY"
    }
    _ok(checks, "sample_too_small_marked", len(small_dates) >= 1, ",".join(sorted(small_dates)) if small_dates else "")
    if len(small_dates) == 0:
        warnings.append("no_sample_too_small_artifact_detected")
    _ok(checks, "sample_too_small_has_20260601", "20260601" in small_dates, ",".join(sorted(small_dates)) if small_dates else "")

    sufficient_with_official = [
        x for x in artifact_results
        if isinstance(x, dict)
        and str(x.get("sample_status")) == "SAMPLE_SUFFICIENT"
        and str(x.get("official_artifact_status")) == "FOUND"
    ]
    _ok(checks, "at_least_one_sufficient_official_found", len(sufficient_with_official) >= 1, str(len(sufficient_with_official)))
    if len(sufficient_with_official) == 0:
        blockers.append("no_sufficient_official_found")

    for i, x in enumerate(sufficient_with_official):
        ca = int(x.get("candidate_A_expansion") or 0)
        cs = int(x.get("candidate_SKIP_to_B") or 0)
        cm = int(x.get("candidate_market_alone") or 0)
        cv = int(x.get("candidate_safety_violations") or 0)
        _ok(checks, f"sufficient[{i}]_candidate_A_expansion_zero", ca == 0, str(ca))
        _ok(checks, f"sufficient[{i}]_candidate_SKIP_to_B_zero", cs == 0, str(cs))
        _ok(checks, f"sufficient[{i}]_candidate_market_alone_zero", cm == 0, str(cm))
        _ok(checks, f"sufficient[{i}]_candidate_safety_violations_zero", cv == 0, str(cv))
        if ca != 0:
            blockers.append("candidate_a_expansion_nonzero")
        if cs != 0:
            blockers.append("candidate_skip_to_b_nonzero")
        if cm != 0:
            blockers.append("candidate_market_alone_nonzero")
        if cv != 0:
            blockers.append("candidate_safety_violations_nonzero")

    agg = report.get("aggregate_summary", {}) if isinstance(report.get("aggregate_summary"), dict) else {}
    agg_safety = report.get("aggregate_safety_summary", {}) if isinstance(report.get("aggregate_safety_summary"), dict) else {}
    _ok(checks, "aggregate_present", isinstance(agg, dict), str(type(agg)))
    _ok(checks, "aggregate_safety_present", isinstance(agg_safety, dict), str(type(agg_safety)))

    _ok(checks, "aggregate_candidate_a_expansion_zero", int(agg_safety.get("candidate_A_expansion_total") or 0) == 0, str(agg_safety.get("candidate_A_expansion_total")))
    if int(agg_safety.get("candidate_A_expansion_total") or 0) != 0:
        blockers.append("aggregate_a_expansion_nonzero")
    _ok(checks, "aggregate_candidate_skip_to_b_zero", int(agg_safety.get("candidate_SKIP_to_B_total") or 0) == 0, str(agg_safety.get("candidate_SKIP_to_B_total")))
    if int(agg_safety.get("candidate_SKIP_to_B_total") or 0) != 0:
        blockers.append("aggregate_skip_to_b_nonzero")
    _ok(checks, "aggregate_candidate_market_alone_zero", int(agg_safety.get("candidate_market_alone_total") or 0) == 0, str(agg_safety.get("candidate_market_alone_total")))
    if int(agg_safety.get("candidate_market_alone_total") or 0) != 0:
        blockers.append("aggregate_market_alone_nonzero")
    _ok(checks, "aggregate_candidate_safety_violations_zero", int(agg_safety.get("candidate_safety_violations_total") or 0) == 0, str(agg_safety.get("candidate_safety_violations_total")))
    if int(agg_safety.get("candidate_safety_violations_total") or 0) != 0:
        blockers.append("aggregate_safety_violations_nonzero")

    # no runtime artifacts staged
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged_files = [x.strip() for x in staged.stdout.splitlines() if x.strip()]
    runtime_staged = [x for x in staged_files if ("data/runtime/" in x or "data/daily_reports/" in x)]
    _ok(checks, "runtime_artifact_not_staged", len(runtime_staged) == 0, ",".join(runtime_staged))
    if runtime_staged:
        blockers.append("runtime_artifact_staged")

    secrets_staged = [x for x in staged_files if any(t in x.lower() for t in [".env", "secret", "token", "apikey", "api_key"])]
    _ok(checks, "no_secrets_staged", len(secrets_staged) == 0, ",".join(secrets_staged))
    if secrets_staged:
        blockers.append("secrets_staged")

    # guard checks
    for script in [
        "check_v4_production_default_rules_guard.py",
        "check_v4_qq_enabled_gate.py",
    ]:
        ok, out = _run([sys.executable, str(ROOT / "tools" / script)])
        _ok(checks, f"guard:{script}", ok, out[-300:])
        if not ok:
            blockers.append(f"guard_failed:{script}")

    return _finish(checks, warnings, blockers)


def _finish(checks: list[dict[str, Any]], warnings: list[str], blockers: list[str]) -> int:
    result = {
        "checker": "check_v4_rescue_threshold_multi_artifact_replay",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    out_path = STATUS / f"check_v4_rescue_threshold_multi_artifact_replay_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
