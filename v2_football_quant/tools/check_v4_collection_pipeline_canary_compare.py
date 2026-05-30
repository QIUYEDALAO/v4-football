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
STATUS = ROOT / "data" / "runtime" / "status"
ACCEPT = ROOT / "data" / "runtime" / "acceptance"
TZ = timezone(timedelta(hours=8))


def _latest(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ok(checks: dict[str, dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def _run(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(TOOLS / script)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_collection_pipeline_canary_compare",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    run_tool = TOOLS / "run_v4_collection_pipeline_canary_compare.py"
    _ok(result["checks"], "canary_tool_exists", run_tool.exists(), str(run_tool))
    if not run_tool.exists():
        result["blockers"].append("canary_tool_missing")
        return _finish(result)

    src = run_tool.read_text(encoding="utf-8")

    _ok(result["checks"], "tool_forces_no_push", "--no-push" in src)
    _ok(result["checks"], "tool_uses_serial", "--scan-engine" in src and "serial" in src)
    _ok(result["checks"], "tool_runs_official_mode", "--collection-mode" in src and "official_legacy" in src)
    _ok(result["checks"], "tool_runs_lazy_mode", "--collection-mode" in src and "rf_lazy_shadow" in src)
    _ok(result["checks"], "tool_supports_max_fixtures", "--max-fixtures" in src)

    max_default_ok = bool(re.search(r"--max-fixtures[^\n]*default=5", src))
    _ok(result["checks"], "max_fixtures_default_le_5", max_default_ok)

    if "engine/v4_scan_and_brief.py" in src and "--no-push" not in src:
        result["blockers"].append("canary_tool_may_push")

    compare_json = _latest("v4_collection_pipeline_canary_compare_*.json", ACCEPT)
    _ok(result["checks"], "compare_json_exists", compare_json is not None and compare_json.exists(), str(compare_json) if compare_json else "")
    if compare_json is None:
        result["blockers"].append("compare_json_missing")
    else:
        payload = _read_json(compare_json)
        off = payload.get("official_legacy") or {}
        lazy = payload.get("rf_lazy_shadow") or {}
        cmpv = payload.get("comparison") or {}

        _ok(result["checks"], "official_scout_row_positive_or_explained", int(off.get("scout_row_count") or 0) > 0, str(off.get("scout_row_count")))
        _ok(result["checks"], "lazy_scout_row_positive_or_explained", int(lazy.get("scout_row_count") or 0) > 0, str(lazy.get("scout_row_count")))
        _ok(result["checks"], "lazy_no_scout_zero", bool((cmpv.get("no_scout_zero") or {}).get("ok")), json.dumps(cmpv.get("no_scout_zero") or {}, ensure_ascii=False))
        _ok(result["checks"], "official_grade_not_overwritten", bool((cmpv.get("no_regrade") or {}).get("ok")), json.dumps(cmpv.get("no_regrade") or {}, ensure_ascii=False))

        if int(off.get("scout_row_count") or 0) <= 0:
            result["warnings"].append("official_scout_zero")
        if int(lazy.get("scout_row_count") or 0) <= 0:
            result["blockers"].append("lazy_scout_zero")
        if not bool((cmpv.get("no_regrade") or {}).get("ok")):
            result["blockers"].append("regrade_detected")

    ok_default, out_default = _run("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", ok_default, out_default[-260:])
    if not ok_default:
        result["blockers"].append("default_rules_guard_failed")

    ok_slim, out_slim = _run("check_v4_system_slim_and_whitelist_mode.py")
    _ok(result["checks"], "cron_whitelist_guard_pass", ok_slim, out_slim[-260:])
    if not ok_slim:
        result["blockers"].append("cron_whitelist_guard_failed")

    ok_no_market, out_no_market = _run("check_v4_no_market_core_validation_skip.py")
    soft_no_market = ok_no_market or ("WARN_ONLY" in out_no_market)
    _ok(result["checks"], "validation_livebet_soft_guard", soft_no_market, out_no_market[-260:])
    if not soft_no_market:
        result["blockers"].append("validation_livebet_guard_failed")

    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    _ok(result["checks"], "qq_disabled", "V4_QQ_ENABLED = False" in brief_src)

    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    secret_hits = [x for x in staged if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    runtime_hits = [x for x in staged if x.startswith("data/runtime/")]
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    _ok(result["checks"], "runtime_artifacts_not_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    if secret_hits:
        result["blockers"].append("secrets_staged")
    if runtime_hits:
        result["blockers"].append("runtime_artifact_staged")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    return _finish(result)


def _finish(result: dict[str, Any]) -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_collection_pipeline_canary_compare_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
