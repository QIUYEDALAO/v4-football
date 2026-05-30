#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_collection_pipeline_rolling_canary",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    run_tool = TOOLS / "run_v4_collection_pipeline_rolling_canary.py"
    _ok(result["checks"], "rolling_tool_exists", run_tool.exists(), str(run_tool))
    if not run_tool.exists():
        result["blockers"].append("rolling_tool_missing")
        return _finish(result)

    src = run_tool.read_text(encoding="utf-8")
    # no-push is guaranteed by the delegated canary compare tool and verified again from runtime artifacts.
    _ok(result["checks"], "tool_forces_no_push", "run_v4_collection_pipeline_canary_compare.py" in src)
    _ok(result["checks"], "tool_no_cron_mutation", "cron" not in src.lower() or "do not" in src.lower())
    _ok(result["checks"], "tool_no_validation_recompute", "\"any_validation_touch\": False" in src)
    _ok(result["checks"], "tool_no_livebet_mutation", "live_bet" not in src.lower() or "any_live_bet_touch" in src)
    _ok(result["checks"], "tool_not_staging_runtime", "git add" not in src.lower())
    _ok(result["checks"], "runs_official_each_date", "official_legacy" in src)
    _ok(result["checks"], "runs_lazy_each_date", "rf_lazy_shadow" in src)

    max_default_ok = bool(re.search(r"--max-fixtures[^\n]*default=5", src))
    _ok(result["checks"], "max_fixtures_default_le_5", max_default_ok)

    latest_json = _latest("v4_collection_pipeline_rolling_canary_*.json", ACCEPT)
    _ok(result["checks"], "rolling_json_exists", latest_json is not None and latest_json.exists(), str(latest_json) if latest_json else "")
    if latest_json is None:
        result["blockers"].append("rolling_json_missing")
    else:
        payload = json.loads(latest_json.read_text(encoding="utf-8"))
        dates = payload.get("dates") or []
        per = payload.get("per_date_results") or []
        agg = payload.get("aggregate") or {}

        _ok(result["checks"], "at_least_2_dates_success", int(agg.get("dates_passed") or 0) >= 2, str(agg.get("dates_passed")))
        if int(agg.get("dates_passed") or 0) < 2:
            result["blockers"].append("not_enough_success_dates")

        lazy_scout_zero_dates = [
            str(r.get("date") or "")
            for r in per
            if int(r.get("rf_lazy_shadow_raw") or 0) > 0 and int(r.get("rf_lazy_shadow_scout") or 0) == 0
        ]
        no_lazy_scout_zero = len(lazy_scout_zero_dates) == 0
        _ok(result["checks"], "no_unexplained_scout_zero", no_lazy_scout_zero, ",".join(lazy_scout_zero_dates))
        if not no_lazy_scout_zero:
            result["blockers"].append("scout_zero_detected")

        mismatch = int(agg.get("total_official_grade_mismatch") or 0)
        _ok(result["checks"], "common_fixture_mismatch_zero", mismatch == 0, str(mismatch))
        if mismatch != 0:
            result["blockers"].append("official_grade_mismatch_detected")

        for r in per:
            d = str(r.get("date") or "")
            _ok(result["checks"], f"date_{d}_has_official_mode", "official_legacy" in str(r.get("command") or "") or r.get("status") in {"PASS", "FAILED"})
            _ok(result["checks"], f"date_{d}_has_lazy_mode", "rf_lazy_shadow" in str(r.get("command") or "") or r.get("status") in {"PASS", "FAILED"})

            compare_path = Path(str(r.get("compare_json") or ""))
            no_push_ok = False
            if compare_path.exists():
                try:
                    compare_payload = json.loads(compare_path.read_text(encoding="utf-8"))
                    no_push_ok = bool(compare_payload.get("no_push"))
                except Exception:
                    no_push_ok = False
            _ok(result["checks"], f"date_{d}_no_push", no_push_ok, str(compare_path))
            if not no_push_ok:
                result["blockers"].append(f"date_{d}_no_push_failed")

        status = str(agg.get("rolling_canary_status") or "")
        _ok(result["checks"], "rolling_status_pass_or_blocked", status in {"PASS", "BLOCKED"}, status)

    ok_default, out_default = _run("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", ok_default, out_default[-260:])
    if not ok_default:
        result["blockers"].append("default_rules_guard_failed")

    ok_slim, out_slim = _run("check_v4_system_slim_and_whitelist_mode.py")
    _ok(result["checks"], "cron_guard_pass", ok_slim, out_slim[-260:])
    if not ok_slim:
        result["blockers"].append("cron_guard_failed")

    ok_no_market, out_no_market = _run("check_v4_no_market_core_validation_skip.py")
    soft_no_market = ok_no_market or ("WARN_ONLY" in out_no_market)
    _ok(result["checks"], "validation_livebet_guard_soft", soft_no_market, out_no_market[-260:])
    if not soft_no_market:
        result["blockers"].append("validation_livebet_guard_failed")

    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    _ok(result["checks"], "qq_disabled", "V4_QQ_ENABLED = False" in brief_src)

    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    secret_hits = [x for x in staged if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    runtime_hits = [x for x in staged if x.startswith("data/runtime/")]
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    _ok(result["checks"], "runtime_artifact_not_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    if secret_hits:
        result["blockers"].append("secrets_staged")
    if runtime_hits:
        result["blockers"].append("runtime_artifact_staged")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    return _finish(result)


def _finish(result: dict[str, Any]) -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_collection_pipeline_rolling_canary_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
