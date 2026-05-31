#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
STATUS = ROOT / "data" / "runtime" / "status"
TZ = timezone(timedelta(hours=8))


def _ok(checks: dict[str, dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def _run(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(TOOLS / script)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        pass
    i = text.find("{")
    while i >= 0:
        chunk = text[i:]
        try:
            return json.loads(chunk)
        except Exception:
            i = text.find("{", i + 1)
    return {}


def _finish(result: dict[str, Any]) -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_collection_pipeline_cache_audit_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] in {"PASS", "REVIEW_REQUIRED"} else 1


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_collection_pipeline_cache_audit",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "review_required": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    audit_tool = TOOLS / "audit_v4_collection_pipeline_cache.py"
    _ok(result["checks"], "checker_exists", Path(__file__).exists(), str(Path(__file__).resolve()))
    _ok(result["checks"], "audit_tool_exists", audit_tool.exists(), str(audit_tool))
    if not audit_tool.exists():
        result["blockers"].append("audit_tool_missing")
        result["conclusion"] = "BLOCKER"
        return _finish(result)

    ok_audit, out_audit = _run("audit_v4_collection_pipeline_cache.py")
    audit = _extract_json(out_audit)
    _ok(result["checks"], "audit_tool_runs", ok_audit, out_audit[-260:])
    if not ok_audit or not audit:
        result["blockers"].append("audit_tool_failed")
        result["conclusion"] = "BLOCKER"
        return _finish(result)

    payload = audit.get("cache_audit_result") or {}
    team_recent = payload.get("team_recent_form_cache") or {}
    pair_h2h = payload.get("pair_h2h_cache") or {}
    market = payload.get("opening_market_cache") or {}
    events = payload.get("events_cache") or {}
    cpl = payload.get("cpl_cache") or {}
    lazy = payload.get("lazy_skip_effect") or {}
    safety = payload.get("safety") or {}

    _ok(result["checks"], "recent_form_cache_audit_exists", bool(team_recent), json.dumps(team_recent, ensure_ascii=False))
    _ok(result["checks"], "pair_h2h_cache_audit_exists", bool(pair_h2h), json.dumps(pair_h2h, ensure_ascii=False))
    _ok(result["checks"], "opening_market_cache_audit_exists", bool(market), json.dumps(market, ensure_ascii=False))
    _ok(result["checks"], "events_cache_audit_exists", bool(events), json.dumps(events, ensure_ascii=False))
    _ok(result["checks"], "cpl_placeholder_cache_audit_exists", bool(cpl), json.dumps(cpl, ensure_ascii=False))

    _ok(result["checks"], "h2h_required_false_skips_h2h", bool(lazy.get("h2h_required_false_skips_h2h")), json.dumps(lazy, ensure_ascii=False))
    _ok(result["checks"], "events_required_false_skips_events", bool(lazy.get("events_required_false_skips_events")), json.dumps(lazy, ensure_ascii=False))
    _ok(result["checks"], "cpl_required_false_skips_cpl", bool(lazy.get("cpl_required_false_skips_cpl")), json.dumps(lazy, ensure_ascii=False))

    _ok(result["checks"], "cache_not_overwrite_official_grade", bool(safety.get("official_grade_unchanged")), json.dumps(safety, ensure_ascii=False))
    _ok(result["checks"], "cache_not_touch_validation", bool(safety.get("validation_untouched")), json.dumps(safety, ensure_ascii=False))
    _ok(result["checks"], "cache_not_touch_live_bet", bool(safety.get("live_bet_untouched")), json.dumps(safety, ensure_ascii=False))
    _ok(result["checks"], "cache_not_push_qq", bool(safety.get("qq_not_pushed")), json.dumps(safety, ensure_ascii=False))

    ok_direct, out_direct = _run("check_v4_collection_pipeline_direct_lazy_shadow.py")
    _ok(result["checks"], "direct_lazy_shadow_guard_pass", ok_direct, out_direct[-260:])
    if not ok_direct:
        result["blockers"].append("direct_lazy_shadow_checker_failed")

    ok_default, out_default = _run("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", ok_default, out_default[-260:])
    if not ok_default:
        result["blockers"].append("default_rules_guard_failed")

    ok_ctrl, out_ctrl = _run("check_v4_control_center.py")
    _ok(result["checks"], "control_center_guard_soft_pass", ok_ctrl or ("WARN_ONLY" in out_ctrl), out_ctrl[-260:])
    if not ok_ctrl and "WARN_ONLY" not in out_ctrl:
        result["blockers"].append("control_center_checker_failed")

    # Staged safety checks
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged_files = [x.strip() for x in staged.splitlines() if x.strip()]
    runtime_hits = [x for x in staged_files if x.startswith("data/runtime/")]
    secret_hits = [x for x in staged_files if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    _ok(result["checks"], "runtime_artifact_not_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    if runtime_hits:
        result["blockers"].append("runtime_artifact_staged")
    if secret_hits:
        result["blockers"].append("secrets_staged")

    # REVIEW_REQUIRED if cache entry missing but safety is still intact.
    for name, cache_entry in (
        ("team_recent_form_cache", team_recent),
        ("pair_h2h_cache", pair_h2h),
        ("opening_market_cache", market),
        ("events_cache", events),
    ):
        if not bool(cache_entry.get("exists", False)):
            result["review_required"].append(f"{name}_missing")

    for check_name in (
        "recent_form_cache_audit_exists",
        "pair_h2h_cache_audit_exists",
        "opening_market_cache_audit_exists",
        "events_cache_audit_exists",
        "cpl_placeholder_cache_audit_exists",
        "h2h_required_false_skips_h2h",
        "events_required_false_skips_events",
        "cpl_required_false_skips_cpl",
        "cache_not_overwrite_official_grade",
        "cache_not_touch_validation",
        "cache_not_touch_live_bet",
        "cache_not_push_qq",
    ):
        if not result["checks"][check_name]["ok"]:
            result["blockers"].append(f"failed:{check_name}")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"
    elif result["review_required"]:
        result["conclusion"] = "REVIEW_REQUIRED"
    else:
        result["conclusion"] = "PASS"

    result["audit_source"] = {
        "audit_status_file": str((STATUS / f"v4_collection_pipeline_cache_audit_{datetime.now(TZ).strftime('%Y%m%d')}.json")),
        "audit_conclusion": audit.get("conclusion"),
    }
    return _finish(result)


if __name__ == "__main__":
    raise SystemExit(main())
