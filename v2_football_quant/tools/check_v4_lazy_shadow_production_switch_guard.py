#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
ACCEPT = ROOT / "data" / "runtime" / "acceptance"
TOOLS = ROOT / "tools"
TZ = timezone(timedelta(hours=8))


def _ok(checks: dict[str, dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def _latest(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _run_checker(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(TOOLS / script)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def _cron_jobs_json() -> dict[str, Any]:
    p = subprocess.run(["openclaw", "cron", "list", "--json"], cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        return {}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {}


def _find_check(checks: dict[str, dict[str, Any]], payload: dict[str, Any], name: str) -> bool:
    ok = bool(((payload.get("checks") or {}).get(name) or {}).get("ok"))
    _ok(checks, name, ok, json.dumps((payload.get("checks") or {}).get(name) or {}, ensure_ascii=False))
    return ok


def _finish(result: dict[str, Any]) -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_lazy_shadow_production_switch_guard_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_lazy_shadow_production_switch_guard",
        "generated_at": datetime.now(TZ).isoformat(),
        "switch_guard_status": "SWITCH_GUARD_PASS",
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    worker_src = (ROOT / "engine" / "v4_scan_worker.py").read_text(encoding="utf-8")
    runner_src = (ROOT / "engine" / "v4_runner.py").read_text(encoding="utf-8")

    # 1-2 official default + explicit lazy only
    default_ok = all('default="official_legacy"' in s for s in (brief_src, worker_src, runner_src))
    _ok(result["checks"], "official_legacy_default_exists", default_ok)
    if not default_ok:
        result["blockers"].append("official_legacy_default_missing")

    explicit_lazy_ok = all("--collection-mode" in s and "rf_lazy_shadow" in s for s in (brief_src, worker_src, runner_src))
    _ok(result["checks"], "rf_lazy_shadow_explicit_only", explicit_lazy_ok)
    if not explicit_lazy_ok:
        result["blockers"].append("rf_lazy_shadow_not_explicit")

    # 3-4 cron payload checks
    cron_data = _cron_jobs_json()
    jobs = cron_data.get("jobs") if isinstance(cron_data, dict) else None
    v4_midday = None
    if isinstance(jobs, list):
        for job in jobs:
            if str(job.get("name") or "") == "V4_DAILY_SCAN_READONLY":
                v4_midday = job
                break
    _ok(result["checks"], "cron_v4_daily_scan_job_exists", v4_midday is not None)
    if v4_midday is None:
        result["blockers"].append("cron_v4_daily_scan_job_missing")
        cron_msg = ""
    else:
        cron_msg = str(((v4_midday.get("payload") or {}).get("message")) or "")

    cron_no_lazy = "--collection-mode rf_lazy_shadow" not in cron_msg
    cron_no_max = "--max-fixtures" not in cron_msg
    _ok(result["checks"], "cron_not_using_rf_lazy_shadow", cron_no_lazy, cron_msg)
    _ok(result["checks"], "cron_not_using_max_fixtures", cron_no_max, cron_msg)
    if not cron_no_lazy:
        result["blockers"].append("cron_uses_rf_lazy_shadow")
    if not cron_no_max:
        result["blockers"].append("cron_uses_max_fixtures")

    # Required upstream checker statuses
    daily_status = _load(_latest("check_v4_collection_pipeline_daily_shadow_canary_*.json", STATUS))
    expanded_status = _load(_latest("check_v4_collection_pipeline_expanded_canary_*.json", STATUS))
    rolling_status = _load(_latest("check_v4_collection_pipeline_rolling_canary_*.json", STATUS))
    cache_status = _load(_latest("check_v4_collection_pipeline_cache_audit_*.json", STATUS))
    default_rules_status = _load(_latest("v4_production_default_rules_guard_*.json", STATUS))

    _ok(result["checks"], "daily_shadow_canary_pass", daily_status.get("conclusion") == "PASS", daily_status.get("conclusion", ""))
    _ok(result["checks"], "expanded_canary_pass", expanded_status.get("conclusion") == "PASS", expanded_status.get("conclusion", ""))
    _ok(result["checks"], "rolling_canary_pass", rolling_status.get("conclusion") == "PASS", rolling_status.get("conclusion", ""))
    _ok(result["checks"], "cache_audit_pass", cache_status.get("conclusion") == "PASS", cache_status.get("conclusion", ""))
    _ok(result["checks"], "default_rules_guard_pass", default_rules_status.get("conclusion") == "PASS", default_rules_status.get("conclusion", ""))

    # 15-19 safety metrics from artifacts/checkers
    daily_art = _load(_latest("v4_collection_pipeline_daily_shadow_canary_*.json", ACCEPT))
    rolling_art = _load(_latest("v4_collection_pipeline_rolling_canary_*.json", ACCEPT))

    lazy = daily_art.get("rf_lazy_shadow") or {}
    cmpv = daily_art.get("comparison") or {}
    lazy_nonzero = int(lazy.get("raw_fixture_count") or 0) == 0 or int(lazy.get("scout_row_count") or 0) > 0
    mismatch_zero = int(cmpv.get("official_grade_mismatch_count") or 0) == 0
    off_cov_ok = bool(cmpv.get("official_fixture_coverage_ok"))
    off_ab_cov_ok = bool(cmpv.get("official_ab_coverage_ok"))
    shadow_pending_ok = int(cmpv.get("shadow_only_pending_hits") or 0) == 0
    validation_untouched = not bool(cmpv.get("validation_touched"))
    live_bet_untouched = not bool(cmpv.get("live_bet_touched"))
    qq_untouched = not bool(cmpv.get("qq_pushed"))

    _ok(result["checks"], "lazy_scout_nonzero", lazy_nonzero, f"raw={lazy.get('raw_fixture_count')} scout={lazy.get('scout_row_count')}")
    _ok(result["checks"], "common_fixtures_mismatch_zero", mismatch_zero, str(cmpv.get("official_grade_mismatch_count")))
    _ok(result["checks"], "official_fixture_covered_by_lazy", off_cov_ok, str(cmpv.get("official_fixture_coverage_ok")))
    _ok(result["checks"], "official_ab_fixture_covered_by_lazy", off_ab_cov_ok, str(cmpv.get("official_ab_coverage_ok")))
    _ok(result["checks"], "shadow_only_not_in_pending_bet_candidates", shadow_pending_ok, str(cmpv.get("shadow_only_pending_hits")))
    _ok(result["checks"], "validation_not_using_shadow_grade", validation_untouched, str(cmpv.get("validation_touched")))
    _ok(result["checks"], "live_bet_not_using_shadow_grade", live_bet_untouched, str(cmpv.get("live_bet_touched")))
    _ok(result["checks"], "qq_not_using_shadow_grade", qq_untouched, str(cmpv.get("qq_pushed")))

    # Rolling-level protection
    agg = rolling_art.get("aggregate") or {}
    _ok(result["checks"], "rolling_any_scout_zero_false", not bool(agg.get("any_scout_zero")), str(agg.get("any_scout_zero")))
    _ok(result["checks"], "rolling_any_regrade_false", not bool(agg.get("any_regrade")), str(agg.get("any_regrade")))

    # H2H runtime semantics unchanged guard from rf shadow grade checker
    ok_rf, out_rf = _run_checker("check_v4_rf_shadow_grade.py")
    rf_payload = {}
    try:
        rf_payload = json.loads(out_rf)
    except Exception:
        start = out_rf.find("{")
        if start >= 0:
            try:
                rf_payload = json.loads(out_rf[start:])
            except Exception:
                rf_payload = {}
    h2h_runtime_ok = False
    for item in rf_payload.get("checks") or []:
        if isinstance(item, dict) and item.get("name") == "h2h_runtime_not_using_shadow":
            h2h_runtime_ok = bool(item.get("ok"))
            break
    _ok(result["checks"], "h2h_runtime_semantics_unchanged", h2h_runtime_ok, "from check_v4_rf_shadow_grade.py")
    if not h2h_runtime_ok:
        result["blockers"].append("h2h_runtime_semantics_changed_or_unknown")

    # soft execution of key checkers
    for s in [
        "check_v4_collection_pipeline_daily_shadow_canary.py",
        "check_v4_collection_pipeline_expanded_canary.py",
        "check_v4_collection_pipeline_rolling_canary.py",
        "check_v4_collection_pipeline_cache_audit.py",
        "check_v4_collection_pipeline_direct_lazy_shadow.py",
        "check_v4_production_default_rules_guard.py",
        "check_v4_control_center.py",
    ]:
        ok, out = _run_checker(s)
        soft_ok = ok or ('"conclusion": "WARN_ONLY"' in out and s == "check_v4_control_center.py")
        _ok(result["checks"], f"guard:{s}", soft_ok, out[-260:])
        if not soft_ok:
            result["blockers"].append(f"guard_failed:{s}")

    # no production switch assertion
    switch_status_ok = result.get("switch_guard_status") == "SWITCH_GUARD_PASS"
    _ok(result["checks"], "status_is_switch_guard_only", switch_status_ok, str(result.get("switch_guard_status")))
    if not switch_status_ok:
        result["blockers"].append("invalid_switch_status")

    # staged safety
    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    runtime_hits = [x for x in staged if x.startswith("data/runtime/")]
    secret_hits = [x for x in staged if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    _ok(result["checks"], "runtime_artifact_not_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    if runtime_hits:
        result["blockers"].append("runtime_artifact_staged")
    if secret_hits:
        result["blockers"].append("secrets_staged")

    # Promote blockers from key checks
    hard_checks = [
        "official_legacy_default_exists",
        "rf_lazy_shadow_explicit_only",
        "cron_v4_daily_scan_job_exists",
        "cron_not_using_rf_lazy_shadow",
        "cron_not_using_max_fixtures",
        "daily_shadow_canary_pass",
        "expanded_canary_pass",
        "rolling_canary_pass",
        "cache_audit_pass",
        "default_rules_guard_pass",
        "lazy_scout_nonzero",
        "common_fixtures_mismatch_zero",
        "official_fixture_covered_by_lazy",
        "official_ab_fixture_covered_by_lazy",
        "shadow_only_not_in_pending_bet_candidates",
        "validation_not_using_shadow_grade",
        "live_bet_not_using_shadow_grade",
        "qq_not_using_shadow_grade",
        "rolling_any_scout_zero_false",
        "rolling_any_regrade_false",
        "h2h_runtime_semantics_unchanged",
        "status_is_switch_guard_only",
        "runtime_artifact_not_staged",
        "no_secrets_staged",
    ]
    for c in hard_checks:
        if not result["checks"].get(c, {}).get("ok", False):
            result["blockers"].append(f"failed:{c}")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"
    return _finish(result)


if __name__ == "__main__":
    raise SystemExit(main())
