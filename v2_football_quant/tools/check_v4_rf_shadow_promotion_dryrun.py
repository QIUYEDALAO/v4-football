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


def _latest_sensitivity_report(date: str | None) -> Path | None:
    if date:
        p = OUT / f"v4_rf_shadow_promotion_dryrun_replay_sensitivity_{date}.json"
        return p if p.exists() else None
    fs = sorted(OUT.glob("v4_rf_shadow_promotion_dryrun_replay_sensitivity_*.json"))
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
            ("arg_rescue_threshold_exists", "--rescue-threshold"),
            ("arg_rescue_thresholds_exists", "--rescue-thresholds"),
            ("arg_sensitivity_exists", "--sensitivity"),
            ("arg_multi_artifact_exists", "--multi-artifact"),
            ("arg_min_fixtures_exists", "--min-fixtures"),
            ("arg_artifact_glob_exists", "--artifact-glob"),
            ("arg_baseline_threshold_exists", "--baseline-threshold"),
            ("arg_candidate_threshold_exists", "--candidate-threshold"),
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

        sp = subprocess.run([
            sys.executable,
            str(runner),
            "--date",
            args.date,
            "--sensitivity",
            "--rescue-thresholds",
            "77,75,73.5",
        ], capture_output=True, text=True)
        _ok(checks, "runner_sensitivity_exec_ok", sp.returncode == 0, (sp.stdout + sp.stderr)[-400:])
        if sp.returncode != 0:
            blockers.append("runner_sensitivity_exec_failed")

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
    sensitivity_path = _latest_sensitivity_report(args.date)
    _ok(checks, "sensitivity_report_exists", sensitivity_path is not None, str(sensitivity_path) if sensitivity_path else "")
    if sensitivity_path is None:
        blockers.append("missing_sensitivity_report")
        sensitivity = {}
    else:
        sensitivity = _read_json(sensitivity_path)

    # required coverage sections
    for k in [
        "official_artifact",
        "recent5_coverage",
        "recent5_bilateral_gate_stats",
        "bfloor_coverage",
        "bfloor_stats",
        "safety_coverage",
        "safety_checks",
        "coverage",
        "tuning_summary",
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
    bfloor_stats = report.get("bfloor_stats", {}) if isinstance(report.get("bfloor_stats"), dict) else {}
    safety_cov = report.get("safety_coverage", {}) if isinstance(report.get("safety_coverage"), dict) else {}
    safety = report.get("safety_checks", {}) if isinstance(report.get("safety_checks"), dict) else {}
    coverage = report.get("coverage", {}) if isinstance(report.get("coverage"), dict) else {}
    tuning = report.get("tuning_summary", {}) if isinstance(report.get("tuning_summary"), dict) else {}
    recent5_stats = report.get("recent5_bilateral_gate_stats", {}) if isinstance(report.get("recent5_bilateral_gate_stats"), dict) else {}
    dist = report.get("distribution", {}) if isinstance(report.get("distribution"), dict) else {}
    safety_market = report.get("safety_market_h2h_events_cpl", {}) if isinstance(report.get("safety_market_h2h_events_cpl"), dict) else {}

    # official missing must not be fake 0/0/0/0
    off_status = str(official.get("official_artifact_status") or "")
    off_dist = official.get("current_official_grade_distribution")
    _ok(checks, "official_artifact_status_present", off_status in {"FOUND", "MISSING", "CONFLICT"}, off_status)
    if off_status not in {"FOUND", "MISSING", "CONFLICT"}:
        blockers.append("invalid_official_artifact_status")

    rescue_threshold = float(report.get("rescue_threshold") or 0.0)
    _ok(checks, "default_rescue_threshold_is_77", abs(rescue_threshold - 77.0) < 1e-9, str(rescue_threshold))
    if abs(rescue_threshold - 77.0) >= 1e-9:
        blockers.append("default_rescue_threshold_changed")

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

    for k in [
        "recent5_rescue_to_B_count",
        "recent5_rescue_blocked_tier4_count",
        "recent5_rescue_blocked_extreme_veto_count",
        "recent5_rescue_blocked_baseline_only_count",
        "recent5_rescue_blocked_market_no_data_A_count",
    ]:
        ok = k in recent5_stats
        _ok(checks, f"recent5_stat:{k}", ok, str(recent5_stats.get(k)))
        if not ok:
            blockers.append(f"missing_recent5_stat:{k}")

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

    for k in [
        "bfloor_rescue_to_B_count",
        "bfloor_detected_but_noop_count",
        "bfloor_detected_blocked_count",
        "bfloor_detected_rescued_count",
        "rescue_to_A_count",
        "exception_to_B_count",
    ]:
        ok = k in bfloor_stats
        _ok(checks, f"bfloor_stat:{k}", ok, str(bfloor_stats.get(k)))
        if not ok:
            blockers.append(f"missing_bfloor_stat:{k}")

    # tuning boundaries
    rescue_to_a = int(bfloor_stats.get("rescue_to_A_count") or 0)
    _ok(checks, "rescue_to_A_count_zero", rescue_to_a == 0, str(rescue_to_a))
    if rescue_to_a != 0:
        blockers.append("rescue_to_a_nonzero")

    shadow_before = dist.get("shadow_dryrun_grade_before_tuning", {}) if isinstance(dist.get("shadow_dryrun_grade_before_tuning"), dict) else {}
    shadow_after = dist.get("shadow_dryrun_grade_after_tuning", {}) if isinstance(dist.get("shadow_dryrun_grade_after_tuning"), dict) else {}
    official_b = int((off_dist or {}).get("B", 0)) if isinstance(off_dist, dict) else 0
    shadow_a_before = int(shadow_before.get("A", 0))
    shadow_a_after = int(shadow_after.get("A", 0))
    shadow_b_after = int(shadow_after.get("B", 0))

    _ok(checks, "shadow_A_not_expanded", shadow_a_after <= shadow_a_before, f"before={shadow_a_before},after={shadow_a_after}")
    if shadow_a_after > shadow_a_before:
        blockers.append("shadow_a_expanded")

    _ok(checks, "shadow_B_not_above_official_B", shadow_b_after <= official_b, f"shadow_B={shadow_b_after},official_B={official_b}")
    if shadow_b_after > official_b:
        blockers.append("shadow_b_above_official_b")

    if off_status == "FOUND":
        default_dist_ok = (
            int((off_dist or {}).get("A", 0)) == 1
            and int((off_dist or {}).get("B", 0)) == 36
            and int((off_dist or {}).get("C", 0)) == 0
            and int((off_dist or {}).get("SKIP", 0)) == 55
            and int(shadow_after.get("A", 0)) == 1
            and int(shadow_after.get("B", 0)) == 32
            and int(shadow_after.get("C", 0)) == 39
            and int(shadow_after.get("SKIP", 0)) == 20
        )
        _ok(checks, "default_replay_distribution_unchanged", default_dist_ok, f"official={off_dist},shadow={shadow_after}")
        if not default_dist_ok:
            blockers.append("default_replay_distribution_changed")

    b_to_c_before = int(coverage.get("b_to_c_before") or 0)
    b_to_c_after = int(coverage.get("b_to_c_after") or 0)
    _ok(checks, "B_to_C_reduced_or_equal", b_to_c_after <= b_to_c_before, f"before={b_to_c_before},after={b_to_c_after}")
    if b_to_c_after > b_to_c_before:
        blockers.append("b_to_c_increased")

    skip_to_b_after = int(coverage.get("skip_to_b_after") or 0)
    _ok(checks, "SKIP_to_B_not_expanded", skip_to_b_after == 0, str(skip_to_b_after))
    if skip_to_b_after != 0:
        blockers.append("skip_to_b_nonzero")

    safety_violations = int(tuning.get("safety_violations_count") or 0)
    _ok(checks, "safety_violations_zero", safety_violations == 0, str(safety_violations))
    if safety_violations != 0:
        blockers.append("safety_violations_nonzero")

    # market-assisted rescue field rename cleanup
    for k in [
        "market_assisted_rescue_to_B_count",
        "market_assisted_rescue_to_B_list",
        "market_alone_manufactured_AB_count",
        "market_alone_manufactured_AB_list",
        "market_rescue_safety_status",
        "market_rescue_naming_status",
    ]:
        ok = k in safety_market
        _ok(checks, f"market_field:{k}", ok, str(safety_market.get(k)))
        if not ok:
            blockers.append(f"missing_market_field:{k}")

    assisted_cnt = int(safety_market.get("market_assisted_rescue_to_B_count") or 0)
    alone_cnt = int(safety_market.get("market_alone_manufactured_AB_count") or 0)
    assisted_list = safety_market.get("market_assisted_rescue_to_B_list") or []
    alone_list = safety_market.get("market_alone_manufactured_AB_list") or []
    naming_status = str(safety_market.get("market_rescue_naming_status") or "")
    safety_status = str(safety_market.get("market_rescue_safety_status") or "")

    _ok(checks, "market_assisted_rescue_to_B_count_expected_5", assisted_cnt == 5, str(assisted_cnt))
    if assisted_cnt != 5:
        blockers.append("market_assisted_rescue_count_not_5")

    _ok(checks, "market_alone_manufactured_AB_count_zero", alone_cnt == 0, str(alone_cnt))
    if alone_cnt != 0:
        blockers.append("market_alone_manufactured_nonzero")

    _ok(checks, "market_assisted_list_count_match", isinstance(assisted_list, list) and len(assisted_list) == assisted_cnt, str(len(assisted_list) if isinstance(assisted_list, list) else type(assisted_list)))
    if not (isinstance(assisted_list, list) and len(assisted_list) == assisted_cnt):
        blockers.append("market_assisted_list_mismatch")

    _ok(checks, "market_alone_list_count_match", isinstance(alone_list, list) and len(alone_list) == alone_cnt, str(len(alone_list) if isinstance(alone_list, list) else type(alone_list)))
    if not (isinstance(alone_list, list) and len(alone_list) == alone_cnt):
        blockers.append("market_alone_list_mismatch")

    _ok(checks, "market_rescue_naming_status_ok", naming_status == "RENAMED_SPLIT_ACTIVE", naming_status)
    if naming_status != "RENAMED_SPLIT_ACTIVE":
        blockers.append("market_rescue_naming_status_invalid")

    _ok(checks, "market_rescue_safety_status_clean", safety_status == "CLEAN", safety_status)
    if safety_status != "CLEAN":
        blockers.append("market_rescue_safety_status_not_clean")

    # legacy alias kept for compatibility but must not drive violation logic
    legacy_alias = safety_market.get("market_manufactured_AB_found")
    _ok(checks, "legacy_market_field_present", legacy_alias is not None, str(legacy_alias))
    _ok(checks, "legacy_market_field_deprecated_flag", bool(safety_market.get("market_manufactured_AB_found_deprecated")) is True, str(safety_market.get("market_manufactured_AB_found_deprecated")))

    # sensitivity coverage
    thresholds = sensitivity.get("sensitivity_thresholds") if isinstance(sensitivity, dict) else None
    threshold_results = sensitivity.get("threshold_results") if isinstance(sensitivity, dict) else None
    _ok(checks, "sensitivity_thresholds_present", isinstance(thresholds, list), str(thresholds))
    if not isinstance(thresholds, list):
        blockers.append("missing_sensitivity_thresholds")
        thresholds = []
    _ok(checks, "sensitivity_threshold_results_present", isinstance(threshold_results, dict), str(type(threshold_results)))
    if not isinstance(threshold_results, dict):
        blockers.append("missing_sensitivity_threshold_results")
        threshold_results = {}

    required_tags = ["77", "75", "73.5"]
    for tag in required_tags:
        present = tag in threshold_results
        _ok(checks, f"sensitivity_has_threshold_{tag}", present)
        if not present:
            blockers.append(f"missing_threshold_result:{tag}")
            continue
        summary = threshold_results[tag].get("summary", {}) if isinstance(threshold_results[tag], dict) else {}
        for key, expected in [
            ("rescue_to_A_count", 0),
            ("SKIP_to_B_count", 0),
            ("market_alone_manufactured_AB_count", 0),
            ("safety_violations_count", 0),
        ]:
            val = int(summary.get(key) or 0)
            ok = val == expected
            _ok(checks, f"sensitivity_{tag}_{key}_safe", ok, str(val))
            if not ok:
                blockers.append(f"sensitivity_{tag}_{key}_unsafe:{val}")

        shadow = summary.get("shadow_A_B_C_SKIP", {}) if isinstance(summary.get("shadow_A_B_C_SKIP"), dict) else {}
        a_cnt = int(shadow.get("A", 0))
        _ok(checks, f"sensitivity_{tag}_A_not_expanded", a_cnt <= 1, str(a_cnt))
        if a_cnt > 1:
            blockers.append(f"sensitivity_{tag}_a_expanded:{a_cnt}")

    if "73.5" in threshold_results:
        new_rescues = threshold_results["73.5"].get("new_rescues_vs_default", [])
        _ok(checks, "sensitivity_73_5_new_rescues_list_present", isinstance(new_rescues, list), str(type(new_rescues)))
        if not isinstance(new_rescues, list):
            blockers.append("sensitivity_73_5_new_rescues_missing")

    bfloor_detected = int(bfloor_stats.get("rf_strong_confirmed_b_floor_exception_count") or 0)
    bfloor_rescued = int(bfloor_stats.get("bfloor_detected_rescued_count") or 0)
    bfloor_blocked = int(bfloor_stats.get("bfloor_detected_blocked_count") or 0)
    bfloor_noop = int(bfloor_stats.get("bfloor_detected_but_noop_count") or 0)
    detected_accounted = bfloor_detected == (bfloor_rescued + bfloor_blocked + bfloor_noop)
    _ok(checks, "bfloor_detected_accounted", detected_accounted, f"detected={bfloor_detected},rescued={bfloor_rescued},blocked={bfloor_blocked},noop={bfloor_noop}")
    if not detected_accounted:
        blockers.append("bfloor_detected_not_accounted")

    if bfloor_detected > 0 and bfloor_blocked < bfloor_detected:
        ex_to_b = int(bfloor_stats.get("exception_to_B_count") or 0)
        _ok(checks, "bfloor_exception_to_B_positive_when_safe_detected", ex_to_b > 0, str(ex_to_b))
        if ex_to_b <= 0:
            blockers.append("bfloor_exception_to_B_not_positive")

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
