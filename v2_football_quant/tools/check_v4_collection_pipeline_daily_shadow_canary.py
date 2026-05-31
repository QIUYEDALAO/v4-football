#!/usr/bin/env python3
from __future__ import annotations

import json
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


def _finish(result: dict[str, Any]) -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_collection_pipeline_daily_shadow_canary_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_collection_pipeline_daily_shadow_canary",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    runner = TOOLS / "run_v4_collection_pipeline_daily_shadow_canary.py"
    _ok(result["checks"], "daily_runner_exists", runner.exists(), str(runner))
    if not runner.exists():
        result["blockers"].append("daily_runner_missing")
        return _finish(result)

    src = runner.read_text(encoding="utf-8")
    _ok(result["checks"], "runner_forces_no_push_via_compare_tool", "run_v4_collection_pipeline_canary_compare.py" in src)
    _ok(result["checks"], "runner_no_cron_mutation", "cron" not in src.lower() or "not" in src.lower())
    _ok(result["checks"], "runner_no_validation_recompute", "validation_touched\": False" in src)
    _ok(result["checks"], "runner_no_livebet_mutation", "live_bet_touched\": False" in src)
    _ok(result["checks"], "runner_no_qq_push", "qq_pushed\": False" in src)
    _ok(result["checks"], "runner_runs_official_mode", "official_legacy" in src)
    _ok(result["checks"], "runner_runs_lazy_mode", "rf_lazy_shadow" in src)
    _ok(result["checks"], "runner_default_max_fixtures_15", "--max-fixtures" in src and "default=15" in src)

    daily_json = _latest("v4_collection_pipeline_daily_shadow_canary_*.json", ACCEPT)
    _ok(result["checks"], "daily_artifact_exists", daily_json is not None and daily_json.exists(), str(daily_json) if daily_json else "")
    if not daily_json:
        result["blockers"].append("daily_artifact_missing")
        return _finish(result)

    payload = json.loads(daily_json.read_text(encoding="utf-8"))
    _ok(result["checks"], "max_fixtures_eq_15", int(payload.get("max_fixtures") or 0) == 15, str(payload.get("max_fixtures")))
    _ok(result["checks"], "no_push_true", bool(payload.get("no_push")), str(payload.get("no_push")))
    _ok(result["checks"], "fixture_universe_whitelist", str(payload.get("fixture_universe")) == "whitelist", str(payload.get("fixture_universe")))
    _ok(result["checks"], "scan_engine_serial", str(payload.get("scan_engine")) == "serial", str(payload.get("scan_engine")))

    lazy = payload.get("rf_lazy_shadow") or {}
    off = payload.get("official_legacy") or {}
    cmpv = payload.get("comparison") or {}

    lazy_raw = int(lazy.get("raw_fixture_count") or 0)
    lazy_scout = int(lazy.get("scout_row_count") or 0)
    _ok(result["checks"], "lazy_scout_nonzero", not (lazy_raw > 0 and lazy_scout == 0), f"raw={lazy_raw},scout={lazy_scout}")

    mismatch = int(cmpv.get("official_grade_mismatch_count") or 0)
    _ok(result["checks"], "official_grade_mismatch_zero", mismatch == 0, str(mismatch))
    _ok(result["checks"], "official_fixture_covered_by_lazy", bool(cmpv.get("official_fixture_coverage_ok")), str(cmpv.get("official_fixture_coverage_ok")))
    _ok(result["checks"], "shadow_only_not_in_pending", int(cmpv.get("shadow_only_pending_hits") or 0) == 0, str(cmpv.get("shadow_only_pending_hits")))
    _ok(result["checks"], "validation_not_using_shadow_grade", not bool(cmpv.get("validation_touched")), str(cmpv.get("validation_touched")))
    _ok(result["checks"], "live_bet_not_using_shadow_grade", not bool(cmpv.get("live_bet_touched")), str(cmpv.get("live_bet_touched")))
    _ok(result["checks"], "qq_not_using_shadow_grade", not bool(cmpv.get("qq_pushed")), str(cmpv.get("qq_pushed")))

    if not result["checks"]["lazy_scout_nonzero"]["ok"]:
        result["blockers"].append("lazy_scout_zero")
    if not result["checks"]["official_grade_mismatch_zero"]["ok"]:
        result["blockers"].append("official_grade_mismatch")
    if not result["checks"]["official_fixture_covered_by_lazy"]["ok"]:
        result["blockers"].append("official_fixture_not_covered")
    if not result["checks"]["shadow_only_not_in_pending"]["ok"]:
        result["blockers"].append("shadow_pending_leak")

    ok_default, out_default = _run("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", ok_default, out_default[-260:])
    if not ok_default:
        result["blockers"].append("default_rules_guard_failed")

    ok_slim, out_slim = _run("check_v4_system_slim_and_whitelist_mode.py")
    _ok(result["checks"], "cron_guard_pass", ok_slim, out_slim[-260:])
    if not ok_slim:
        result["blockers"].append("cron_guard_failed")

    ok_dash, out_dash = _run("check_v4_rf_shadow_dashboard_review.py")
    _ok(result["checks"], "dashboard_shadow_guard_pass", ok_dash, out_dash[-260:])
    if not ok_dash:
        result["blockers"].append("dashboard_shadow_guard_failed")

    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    _ok(result["checks"], "qq_disabled", "V4_QQ_ENABLED = False" in brief_src)

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

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    result["summary"] = {
        "scan_date": payload.get("scan_date"),
        "official_raw": int(off.get("raw_fixture_count") or 0),
        "official_scout": int(off.get("scout_row_count") or 0),
        "lazy_raw": lazy_raw,
        "lazy_scout": lazy_scout,
        "mismatch": mismatch,
        "estimated_saved": int(lazy.get("estimated_expensive_calls_saved") or 0),
    }

    return _finish(result)


if __name__ == "__main__":
    raise SystemExit(main())
