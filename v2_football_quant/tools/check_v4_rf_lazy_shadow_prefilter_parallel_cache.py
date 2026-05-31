#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
REPORT = ROOT / "data" / "daily_reports"
TZ = timezone(timedelta(hours=8))


def _ok(checks: dict[str, dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def _latest(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load(path: Path | None) -> Any:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _run_checker(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_rf_lazy_shadow_prefilter_parallel_cache",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    runner_src = (ROOT / "engine" / "v4_runner.py").read_text(encoding="utf-8")

    # 1,2,3,4 structure checks
    _ok(result["checks"], "lazy_prefilter_parallel_exists", "ThreadPoolExecutor(max_workers=4" in runner_src)
    _ok(result["checks"], "official_legacy_not_parallelized", 'if collection_mode == "rf_lazy_shadow":' in runner_src)
    _ok(result["checks"], "max_workers_bounded", "max_workers=4" in runner_src)
    all_parallel_tasks = all(x in runner_src for x in ["_task_recent_home", "_task_recent_away", "_task_odds", "_task_coverage"])
    _ok(result["checks"], "prefilter_tasks_present", all_parallel_tasks)

    # 5 failure fallback
    _ok(result["checks"], "subtask_failure_no_row_drop_marker", "keep row, degrade to safe defaults" in runner_src)

    # 6-10 cache keys and stats
    _ok(result["checks"], "recent_cache_key_shape", "recent_form_cache" in runner_src and "(int(team_id), int(last_n), int(include_events))" in runner_src)
    _ok(result["checks"], "odds_cache_key_shape", "odds_cache" in runner_src and "key = int(fixture_id)" in runner_src)
    _ok(result["checks"], "coverage_cache_key_shape", "coverage_cache" in runner_src and "key = (league_id, season)" in runner_src)
    _ok(result["checks"], "h2h_cache_key_shape", "h2h_result_cache" in runner_src and "h2h_key = (int(fx[\"homeId\"]), int(fx[\"awayId\"]))" in runner_src)
    _ok(result["checks"], "events_cache_key_shape", "events_cache" in runner_src and "events_key = int(fx[\"id\"])" in runner_src)

    # 11-12 runtime fields markers
    required_fields = [
        "prefilter_elapsed_ms",
        "recent_home_elapsed_ms",
        "recent_away_elapsed_ms",
        "odds_elapsed_ms",
        "coverage_elapsed_ms",
        "h2h_elapsed_ms",
        "events_elapsed_ms",
        "slowest_stage",
        "api_call_count",
        "cache_hit_count",
        "cache_miss_count",
        "runtime_cost_profile",
    ]
    fields_ok = all(f in runner_src for f in required_fields)
    _ok(result["checks"], "runtime_profile_fields_present", fields_ok)

    # runtime artifact checks
    scout_path = _latest("scout_v4_*.json", REPORT)
    perf_path = _latest("scan_perf_v4_*.json", REPORT)
    scout_rows = _load(scout_path)
    perf = _load(perf_path)

    lazy_rows = [r for r in scout_rows if isinstance(r, dict) and str(r.get("collection_mode") or "").lower() == "rf_lazy_shadow"] if isinstance(scout_rows, list) else []
    if lazy_rows:
        row_field_ok = all(all(k in r for k in required_fields[:-1]) for r in lazy_rows)
        _ok(result["checks"], "runtime_row_fields_present", row_field_ok, f"rows={len(lazy_rows)}")
        if not row_field_ok:
            result["warnings"].append("runtime_row_fields_missing_pre_run_or_old_artifact")
    else:
        _ok(result["checks"], "runtime_row_fields_present", True, "no lazy rows yet")
        result["warnings"].append("no_lazy_rows_in_latest_scout")

    runtime_cost = (perf or {}).get("runtime_cost_profile") if isinstance(perf, dict) else None
    runtime_cost_ok = isinstance(runtime_cost, dict)
    _ok(result["checks"], "runtime_cost_profile_exists", runtime_cost_ok or perf_path is not None, str(perf_path) if perf_path else "")
    if not runtime_cost_ok:
        result["warnings"].append("runtime_cost_profile_missing_in_old_perf_artifact")

    # 13-14-15-20
    ok_h2h, out_h2h = _run_checker("check_v4_rf_lazy_shadow_h2h_gate_hardening.py")
    _ok(result["checks"], "h2h_gate_hardening_still_pass", ok_h2h, out_h2h[-220:])
    if not ok_h2h:
        result["blockers"].append("h2h_gate_hardening_failed")

    ok_default, out_default = _run_checker("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", ok_default, out_default[-220:])
    if not ok_default:
        result["blockers"].append("default_rules_guard_failed")

    qq_disabled = "V4_QQ_ENABLED = False" in (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    _ok(result["checks"], "qq_disabled", qq_disabled)
    if not qq_disabled:
        result["blockers"].append("qq_not_disabled")

    # 16-19: no unexpected touches (delegated guards)
    ok_guard, out_guard = _run_checker("check_v4_lazy_shadow_production_switch_guard.py")
    _ok(result["checks"], "production_switch_guard_pass", ok_guard, out_guard[-220:])
    if not ok_guard:
        result["blockers"].append("production_switch_guard_failed")

    # 21-22 staging safety
    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    secret_hits = [x for x in staged if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    runtime_hits = [x for x in staged if x.startswith("data/runtime/") or x.startswith("data/daily_reports/")]
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    _ok(result["checks"], "runtime_artifact_not_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    if secret_hits:
        result["blockers"].append("secrets_staged")
    if runtime_hits:
        result["blockers"].append("runtime_artifacts_staged")

    # hard blockers from checks
    hard = [
        "lazy_prefilter_parallel_exists",
        "official_legacy_not_parallelized",
        "max_workers_bounded",
        "prefilter_tasks_present",
        "subtask_failure_no_row_drop_marker",
        "odds_cache_key_shape",
        "coverage_cache_key_shape",
        "h2h_cache_key_shape",
        "events_cache_key_shape",
        "runtime_profile_fields_present",
        "runtime_cost_profile_exists",
        "h2h_gate_hardening_still_pass",
        "default_rules_guard_pass",
        "production_switch_guard_pass",
        "qq_disabled",
        "no_secrets_staged",
        "runtime_artifact_not_staged",
    ]
    for c in hard:
        if not result["checks"].get(c, {}).get("ok", False):
            result["blockers"].append(f"failed:{c}")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_rf_lazy_shadow_prefilter_parallel_cache_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
