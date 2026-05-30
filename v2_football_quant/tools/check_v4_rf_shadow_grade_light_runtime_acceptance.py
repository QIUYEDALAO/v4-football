#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ACCEPT_DIR = ROOT / "data" / "runtime" / "acceptance"
STATUS_DIR = ROOT / "data" / "runtime" / "status"
TZ = timezone(timedelta(hours=8))

RF_SHADOW_FIELDS = [
    "rf_shadow_grade",
    "rf_shadow_score",
    "rf_shadow_route",
    "rf_shadow_reason",
    "rf_shadow_confidence",
    "rf_entry_rule",
    "rf_recent10_gate_status",
    "rf_recent5_grade_status",
    "rf_heating_exception",
    "rf_heating_exception_reason",
]
TEAM_BALANCE_FIELDS = [
    "rf_balance_status",
    "rf_balance_driver_side",
    "rf_balance_driver_level",
    "rf_balance_weak_side_status",
    "rf_balance_adjustment",
    "rf_balance_reason",
]
H2H_BONUS_FIELDS = [
    "h2h_recent5_support_status",
    "h2h_recent5_bonus_level",
    "h2h_recent5_bonus_reason",
]
OPENING_MARKET_FIELDS = [
    "opening_market_support_status",
    "opening_market_reason",
    "market_adjusted_shadow_grade",
    "market_adjustment_reason",
]


def _latest_artifact() -> Path | None:
    files = sorted(ACCEPT_DIR.glob("v4_rf_shadow_grade_light_acceptance_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ok(checks: list[dict], name: str, cond: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(cond), "detail": detail})


def _run_tool(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def _field_group_ok(coverage: dict[str, Any], fields: list[str], row_count: int) -> tuple[bool, str]:
    missing: list[str] = []
    for f in fields:
        stat = coverage.get(f) or {}
        if int(stat.get("present_count", 0)) < row_count:
            missing.append(f)
    return (len(missing) == 0, ",".join(missing))


def main() -> int:
    checks: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []

    artifact = _latest_artifact()
    _ok(checks, "acceptance_artifact_exists", artifact is not None and artifact.exists(), str(artifact) if artifact else "")
    if artifact is None:
        blockers.append("artifact_missing")
        return _finish(checks, warnings, blockers)

    payload = _load_json(artifact)
    source_scout = payload.get("source_scout_path")
    source_count = int(payload.get("source_row_count") or 0)
    enriched_count = int(payload.get("enriched_row_count") or 0)
    coverage = payload.get("rf_shadow_field_coverage") or {}
    no_regrade = payload.get("no_regrade_check") or {}
    rules = payload.get("rule_sample_results") or []
    candidate_like = payload.get("candidate_view_like_rows") or {}
    dashboard_like = payload.get("dashboard_model_like_rows") or {}

    _ok(checks, "source_scout_path_exists", bool(source_scout) and Path(source_scout).exists(), str(source_scout))
    _ok(checks, "source_row_count_positive", source_count > 0, str(source_count))
    _ok(checks, "enriched_row_count_positive", enriched_count > 0, str(enriched_count))
    if source_count <= 0:
        blockers.append("source_row_count_zero")
    if enriched_count <= 0:
        blockers.append("enriched_row_count_zero")

    ok_rf, miss_rf = _field_group_ok(coverage, RF_SHADOW_FIELDS, enriched_count)
    ok_bal, miss_bal = _field_group_ok(coverage, TEAM_BALANCE_FIELDS, enriched_count)
    ok_h2h, miss_h2h = _field_group_ok(coverage, H2H_BONUS_FIELDS, enriched_count)
    ok_mkt, miss_mkt = _field_group_ok(coverage, OPENING_MARKET_FIELDS, enriched_count)
    _ok(checks, "rf_shadow_fields_covered", ok_rf, miss_rf)
    _ok(checks, "team_balance_fields_covered", ok_bal, miss_bal)
    _ok(checks, "h2h_bonus_fields_covered", ok_h2h, miss_h2h)
    _ok(checks, "opening_market_fields_covered", ok_mkt, miss_mkt)
    for name, ok in [
        ("rf_shadow_fields_covered", ok_rf),
        ("team_balance_fields_covered", ok_bal),
        ("h2h_bonus_fields_covered", ok_h2h),
        ("opening_market_fields_covered", ok_mkt),
    ]:
        if not ok:
            blockers.append(name)

    ab_like_count = len(candidate_like.get("A_candidates") or []) + len(candidate_like.get("B_candidates") or []) + len(candidate_like.get("C_candidates") or []) + len(candidate_like.get("SKIP_candidates") or [])
    dashboard_items = ((dashboard_like.get("candidates") or {}).get("items") or [])
    _ok(checks, "candidate_view_like_generated", ab_like_count > 0, str(ab_like_count))
    _ok(checks, "dashboard_model_like_generated", len(dashboard_items) > 0, str(len(dashboard_items)))
    if ab_like_count <= 0:
        blockers.append("candidate_view_like_empty")
    if len(dashboard_items) <= 0:
        blockers.append("dashboard_model_like_empty")

    no_regrade_pass = bool(no_regrade.get("pass"))
    _ok(checks, "no_regrade_pass", no_regrade_pass, f"violation_count={no_regrade.get('violation_count', 'NA')}")
    if not no_regrade_pass:
        blockers.append("no_regrade_failed")

    all_rules_pass = bool(rules) and all(bool(x.get("pass")) for x in rules if isinstance(x, dict))
    _ok(checks, "rule_sample_results_all_pass", all_rules_pass, f"total={len(rules)}")
    if not all_rules_pass:
        blockers.append("rule_samples_failed")

    _ok(checks, "tool_no_api_calls", payload.get("api_calls_made") is False, str(payload.get("api_calls_made")))
    _ok(checks, "tool_no_formal_scan", payload.get("formal_scan_executed") is False, str(payload.get("formal_scan_executed")))
    if payload.get("api_calls_made") is not False:
        blockers.append("api_calls_detected")
    if payload.get("formal_scan_executed") is not False:
        blockers.append("formal_scan_detected")

    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    artifact_staged = [x for x in staged if x.startswith("data/runtime/acceptance/")]
    _ok(checks, "acceptance_artifact_not_staged", len(artifact_staged) == 0, ",".join(artifact_staged))
    if artifact_staged:
        blockers.append("acceptance_artifact_staged")

    secret_staged = [x for x in staged if any(t in x.lower() for t in [".env", "secret", "token", "api_key", "apikey"])]
    _ok(checks, "no_secrets_staged", len(secret_staged) == 0, ",".join(secret_staged))
    if secret_staged:
        blockers.append("secrets_staged")

    guard_ok, guard_out = _run_tool("check_v4_production_default_rules_guard.py")
    _ok(checks, "default_rules_guard_pass", guard_ok, guard_out[-300:])
    if not guard_ok:
        blockers.append("default_rules_guard_failed")

    no_market_ok, no_market_out = _run_tool("check_v4_no_market_core_validation_skip.py")
    soft_no_market = no_market_ok or ("WARN_ONLY" in no_market_out)
    _ok(checks, "validation_livebet_guard_pass", soft_no_market, no_market_out[-300:])
    if not soft_no_market:
        blockers.append("validation_livebet_guard_failed")

    slim_ok, slim_out = _run_tool("check_v4_system_slim_and_whitelist_mode.py")
    _ok(checks, "whitelist_cron_guard_pass", slim_ok, slim_out[-300:])
    if not slim_ok:
        blockers.append("whitelist_cron_guard_failed")

    if not guard_ok:
        warnings.append("default_rules_guard_failed")
    if not slim_ok:
        warnings.append("slim_checker_failed")

    return _finish(checks, warnings, blockers)


def _finish(checks: list[dict], warnings: list[str], blockers: list[str]) -> int:
    out = {
        "checker": "check_v4_rf_shadow_grade_light_runtime_acceptance",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STATUS_DIR / f"check_v4_rf_shadow_grade_light_runtime_acceptance_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
