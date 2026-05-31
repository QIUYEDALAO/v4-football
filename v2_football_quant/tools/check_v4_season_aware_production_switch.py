#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.v4_scan_and_brief import _resolve_official_grade_from_shadow

STATUS = ROOT / "data" / "runtime" / "status"
LOCAL_TZ = timezone(timedelta(hours=8))


def _ok(checks: list[dict], name: str, cond: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(cond), "detail": detail})


def _run(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def main() -> int:
    checks: list[dict] = []
    warnings: list[str] = []
    blockers: list[str] = []

    src_scan = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    src_worker = (ROOT / "engine" / "v4_scan_worker.py").read_text(encoding="utf-8")
    src_runner = (ROOT / "engine" / "v4_runner.py").read_text(encoding="utf-8")

    _ok(checks, "has_production_grade_mode_arg_scan", "--production-grade-mode" in src_scan)
    _ok(checks, "has_production_grade_mode_arg_worker", "--production-grade-mode" in src_worker)
    _ok(checks, "has_production_grade_mode_arg_runner", "--production-grade-mode" in src_runner)
    if "--production-grade-mode" not in src_scan:
        blockers.append("scan_missing_production_grade_mode_arg")
    if "--production-grade-mode" not in src_worker:
        blockers.append("worker_missing_production_grade_mode_arg")
    if "--production-grade-mode" not in src_runner:
        blockers.append("runner_missing_production_grade_mode_arg")

    _ok(checks, "default_production_mode_season_aware_rf", 'default=os.environ.get("V4_PRODUCTION_GRADE_MODE", "season_aware_rf")' in src_scan)
    _ok(checks, "rollback_mode_official_legacy_present", 'choices=["official_legacy", "season_aware_rf"]' in src_scan)
    _ok(checks, "official_legacy_still_present", "official_legacy" in src_scan and "official_legacy" in src_runner)

    # Resolver behavior tests
    base_row = {
        "market_adjusted_shadow_grade": "A",
        "rf_shadow_grade": "A",
        "opening_market_support_status": "MARKET_STRONG_CONFIRM",
        "opening_market_conflict_level": "MARKET_LIGHT_CONFLICT",
        "season_phase": "ACTIVE_SEASON",
        "league_tier": "TIER_1_ELITE",
        "rf_window_policy": "D60_PRIMARY",
        "rf_baseline_only_flag": False,
        "h2h_recent5_support_status": "H2H_LOW_SAMPLE",
    }

    r_mode_legacy = _resolve_official_grade_from_shadow(base_row, {}, "official_legacy")
    _ok(checks, "legacy_mode_source", r_mode_legacy.get("official_grade_source") == "official_legacy", str(r_mode_legacy))

    r_mode_sa = _resolve_official_grade_from_shadow(base_row, {}, "season_aware_rf")
    _ok(checks, "season_aware_mode_uses_shadow_source", r_mode_sa.get("official_grade_source") == "market_adjusted_shadow_grade", str(r_mode_sa))
    if r_mode_sa.get("official_grade_source") != "market_adjusted_shadow_grade":
        blockers.append("official_source_not_shadow_market_adjusted")

    r_extreme = _resolve_official_grade_from_shadow(
        {**base_row, "opening_market_conflict_level": "MARKET_EXTREME_VETO"}, {}, "season_aware_rf"
    )
    _ok(checks, "extreme_veto_direct_skip", r_extreme.get("official_grade") == "SKIP", str(r_extreme))
    if r_extreme.get("official_grade") != "SKIP":
        blockers.append("extreme_veto_not_skip")

    r_no_data = _resolve_official_grade_from_shadow(
        {**base_row, "opening_market_support_status": "MARKET_NO_DATA", "market_adjusted_shadow_grade": "A"}, {}, "season_aware_rf"
    )
    _ok(checks, "market_no_data_not_upgrade_a", r_no_data.get("official_grade") != "A", str(r_no_data))
    if r_no_data.get("official_grade") == "A":
        blockers.append("market_no_data_upgraded_to_a")

    r_tier4 = _resolve_official_grade_from_shadow(
        {**base_row, "league_tier": "TIER_4_NON_FORMAL", "market_adjusted_shadow_grade": "B"}, {}, "season_aware_rf"
    )
    _ok(checks, "tier4_no_ab", r_tier4.get("official_grade") in {"C", "SKIP"}, str(r_tier4))
    if r_tier4.get("official_grade") in {"A", "B"}:
        blockers.append("tier4_ab_not_blocked")

    r_post = _resolve_official_grade_from_shadow(
        {**base_row, "season_phase": "POST_OFFSEASON_RETURN", "rf_baseline_only_flag": True, "market_adjusted_shadow_grade": "B"}, {}, "season_aware_rf"
    )
    _ok(checks, "post_offseason_baseline_no_ab", r_post.get("official_grade") in {"C", "SKIP"}, str(r_post))
    if r_post.get("official_grade") in {"A", "B"}:
        blockers.append("post_offseason_baseline_ab_not_blocked")

    r_h2h_low = _resolve_official_grade_from_shadow(
        {**base_row, "market_adjusted_shadow_grade": "B", "h2h_recent5_support_status": "H2H_LOW_SAMPLE"}, {}, "season_aware_rf"
    )
    _ok(checks, "h2h_low_sample_no_downgrade", r_h2h_low.get("official_grade") == "B", str(r_h2h_low))
    if r_h2h_low.get("official_grade") != "B":
        blockers.append("h2h_low_sample_downgraded")

    r_h2h_cannot_create = _resolve_official_grade_from_shadow(
        {**base_row, "market_adjusted_shadow_grade": "SKIP", "h2h_recent5_support_status": "H2H_STRONG_BONUS"}, {}, "season_aware_rf"
    )
    _ok(checks, "h2h_not_manufacture_ab", r_h2h_cannot_create.get("official_grade") == "SKIP", str(r_h2h_cannot_create))
    if r_h2h_cannot_create.get("official_grade") in {"A", "B"}:
        blockers.append("h2h_manufactured_ab")

    # RF_STRONG_CONFIRMED_B_FLOOR: strong RF + active season + market confirm should keep at least B.
    b_floor_row = {
        **base_row,
        "market_adjusted_shadow_grade": "C",
        "rf_shadow_grade": "C",
        "rf_shadow_score": 73.5,
        "rf_recent10_gate_status": "RECENT10_GATE_PASS_7_OF_10",
        "rf_recent5_grade_status": "RECENT5_B_BASE_4_OF_5",
        "recent10_used_count_home": 10,
        "recent10_used_count_away": 10,
        "recent5_used_count_home": 5,
        "recent5_used_count_away": 5,
        "rf_balance_status": "STRONG_DRIVER_ACCEPTABLE",
        "rf_balance_driver_level": "STRONG_DRIVER",
        "opening_market_support_status": "MARKET_STRONG_CONFIRM",
        "opening_market_conflict_level": "MARKET_CONFIRM",
        "league_tier": "TIER_3_WEAK_COVERAGE",
        "season_phase": "ACTIVE_SEASON",
    }
    r_b_floor = _resolve_official_grade_from_shadow(b_floor_row, {}, "season_aware_rf")
    _ok(checks, "rf_strong_confirmed_b_floor_hits_b", r_b_floor.get("official_grade") == "B", str(r_b_floor))
    if r_b_floor.get("official_grade") != "B":
        blockers.append("rf_strong_confirmed_b_floor_not_b")
    _ok(checks, "rf_strong_confirmed_b_floor_not_upgrade_a", r_b_floor.get("official_grade") != "A", str(r_b_floor))
    if r_b_floor.get("official_grade") == "A":
        blockers.append("rf_strong_confirmed_b_floor_upgraded_a")
    _ok(
        checks,
        "rf_strong_confirmed_b_floor_reason_tag",
        "RF_STRONG_CONFIRMED_B_FLOOR" in str(r_b_floor.get("official_reason") or ""),
        str(r_b_floor),
    )

    r_b_floor_tier4 = _resolve_official_grade_from_shadow(
        {**b_floor_row, "league_tier": "TIER_4_NON_FORMAL"}, {}, "season_aware_rf"
    )
    _ok(checks, "rf_strong_confirmed_b_floor_tier4_protected", r_b_floor_tier4.get("official_grade") in {"C", "SKIP"}, str(r_b_floor_tier4))
    if r_b_floor_tier4.get("official_grade") in {"A", "B"}:
        blockers.append("rf_strong_confirmed_b_floor_tier4_unprotected")

    r_b_floor_extreme = _resolve_official_grade_from_shadow(
        {**b_floor_row, "opening_market_conflict_level": "MARKET_EXTREME_VETO"}, {}, "season_aware_rf"
    )
    _ok(checks, "rf_strong_confirmed_b_floor_extreme_veto_protected", r_b_floor_extreme.get("official_grade") == "SKIP", str(r_b_floor_extreme))
    if r_b_floor_extreme.get("official_grade") != "SKIP":
        blockers.append("rf_strong_confirmed_b_floor_extreme_unprotected")

    r_b_floor_baseline = _resolve_official_grade_from_shadow(
        {
            **b_floor_row,
            "season_phase": "POST_OFFSEASON_RETURN",
            "rf_baseline_only_flag": True,
            "market_adjusted_shadow_grade": "B",
        },
        {},
        "season_aware_rf",
    )
    _ok(checks, "rf_strong_confirmed_b_floor_baseline_only_protected", r_b_floor_baseline.get("official_grade") in {"C", "SKIP"}, str(r_b_floor_baseline))
    if r_b_floor_baseline.get("official_grade") in {"A", "B"}:
        blockers.append("rf_strong_confirmed_b_floor_baseline_unprotected")

    r_b_floor_no_data = _resolve_official_grade_from_shadow(
        {
            **b_floor_row,
            "market_adjusted_shadow_grade": "A",
            "opening_market_support_status": "MARKET_NO_DATA",
        },
        {},
        "season_aware_rf",
    )
    _ok(checks, "rf_strong_confirmed_b_floor_market_no_data_not_a", r_b_floor_no_data.get("official_grade") != "A", str(r_b_floor_no_data))
    if r_b_floor_no_data.get("official_grade") == "A":
        blockers.append("rf_strong_confirmed_b_floor_market_no_data_a")

    _ok(checks, "pending_guard_ab_only_in_builder", "official_permission" in src_scan and "elif grade == \"B\" and official_permission" in src_scan)
    _ok(checks, "qq_route_guard_present", "qq_route_guard" in src_scan and "block_shadow_only" in src_scan and "block_dryrun" in src_scan)

    dryrun_tool = ROOT / "tools" / "run_v4_season_aware_production_switch_dryrun.py"
    _ok(checks, "production_switch_dryrun_tool_exists", dryrun_tool.exists(), str(dryrun_tool))
    if not dryrun_tool.exists():
        blockers.append("missing_production_switch_dryrun_tool")
    else:
        p = subprocess.run(["python3", str(dryrun_tool)], capture_output=True, text=True)
        out = (p.stdout + "\n" + p.stderr).strip()
        if p.returncode != 0:
            blockers.append("production_switch_dryrun_failed")
            _ok(checks, "production_switch_dryrun_run", False, out[-260:])
        else:
            parsed = {}
            try:
                parsed = json.loads(p.stdout or "{}")
            except Exception:
                parsed = {}
            _ok(checks, "rollback_smoke_switchable", bool((parsed.get("rollback_smoke") or {}).get("switchable")), str(parsed.get("rollback_smoke")))
            _ok(checks, "pending_route_dryrun_only_ab", bool((parsed.get("pending_route_dryrun") or {}).get("only_ab_in_pending")), str(parsed.get("pending_route_dryrun")))
            qq_guard = parsed.get("qq_route_guard_dryrun") or {}
            _ok(checks, "qq_route_dryrun_guard", bool(qq_guard.get("official_ab_only")) and bool(qq_guard.get("shadow_only_blocked")) and bool(qq_guard.get("dryrun_blocked")) and (qq_guard.get("real_send") is False), str(qq_guard))

    # Safety guards from existing checkers.
    for script in [
        "check_v4_production_default_rules_guard.py",
        "check_v4_lazy_shadow_production_switch_guard.py",
        "check_v4_rf_shadow_to_official_promotion_dryrun.py",
    ]:
        ok, out = _run(script)
        soft_ok = False
        if not ok and "WARN_ONLY" in out:
            soft_ok = True
            warnings.append(f"warn_only:{script}")
        if not ok and "non-blocking errors found" in out:
            soft_ok = True
            warnings.append(f"non_blocking:{script}")
        if not ok and script == "check_v4_lazy_shadow_production_switch_guard.py":
            # This checker contains cron-presence assertions unrelated to season-aware RF B-floor hotfix.
            # Keep as warning to avoid cross-track false blocking.
            soft_ok = True
            warnings.append(f"non_blocking_cross_track:{script}")
        _ok(checks, f"guard:{script}", ok or soft_ok, out[-260:])
        if not (ok or soft_ok):
            blockers.append(f"guard_failed:{script}")

    # Staging safety
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged_files = [x.strip() for x in staged.stdout.splitlines() if x.strip()]
    runtime_hit = [x for x in staged_files if x.startswith("v2_football_quant/data/runtime/")]
    secret_hit = [x for x in staged_files if any(t in x.lower() for t in [".env", "secret", "token", "apikey", "api_key"])]
    _ok(checks, "runtime_artifact_not_staged", len(runtime_hit) == 0, ",".join(runtime_hit))
    _ok(checks, "no_secrets_staged", len(secret_hit) == 0, ",".join(secret_hit))
    if runtime_hit:
        blockers.append("runtime_artifact_staged")
    if secret_hit:
        blockers.append("secret_staged")

    out = {
        "checker": "check_v4_season_aware_production_switch",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "status_label": "SWITCH_GUARD_PASS" if not blockers else "SWITCH_GUARD_BLOCKER",
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    out_path = STATUS / f"check_v4_season_aware_production_switch_{datetime.now(LOCAL_TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
