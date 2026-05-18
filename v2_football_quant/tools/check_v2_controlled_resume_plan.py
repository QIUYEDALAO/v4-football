#!/usr/bin/env python3
"""Phase D.8.1 — V2 Controlled Resume Plan checker (read-only)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_controlled_resume_plan.v1"

SECRET_PAT = re.compile(r"sk-[A-Za-z0-9]{20,}|x-apisports-key\s*[:=]\s*[\"'][^\"']+[\"']", re.IGNORECASE)



def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()



def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default



def _staged_flags() -> dict[str, bool]:
    staged = _run(["git", "diff", "--cached", "--name-only"])
    files = [x.strip() for x in staged.splitlines() if x.strip()]
    return {
        "runtime_artifacts_staged": any(f.startswith("data/runtime/") for f in files),
        "paper_trading_staged": any(f.startswith("data/paper_trading/") for f in files),
    }



def _secret_safe(paths: list[Path]) -> bool:
    for p in paths:
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        if SECRET_PAT.search(txt):
            return False
    return True



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    readiness_path = STATUS_DIR / f"v2_production_resume_readiness_{date_key}.json"
    preflight_path = STATUS_DIR / f"v2_settlement_preflight_{date_key}.json"
    preflight_check_path = STATUS_DIR / f"v2_settlement_preflight_check_{date_key}.json"
    wrapper_path = STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json"
    shadow_path = STATUS_DIR / f"v2_settlement_shadow_guard_{date_key}.json"
    completion_path = STATUS_DIR / f"phase_d_completion_check_{date_key}.json"

    readiness = _load_json(readiness_path, {})
    preflight = _load_json(preflight_path, {})
    preflight_check = _load_json(preflight_check_path, {})
    wrapper = _load_json(wrapper_path, {})
    shadow = _load_json(shadow_path, {})
    completion = _load_json(completion_path, {})

    warnings: list[str] = []
    risks: list[str] = []
    blockers: list[str] = []

    current_branch = _run(["git", "branch", "--show-current"])
    staged = _staged_flags()

    d8_readiness_exists = readiness_path.exists()
    d8_status = str(readiness.get("readiness_status", "")).upper()
    d8_readiness_status_ok = d8_status in {"READY_FOR_BOSS_REVIEW", "WARN"}

    preflight_gate_installed = bool(
        readiness.get("checks", {}).get("preflight_gate_installed", False)
        if isinstance(readiness.get("checks"), dict)
        else False
    ) or bool(preflight.get("settlement_allowed") is False)

    wrapper_block_test_passed = bool(
        readiness.get("checks", {}).get("wrapper_block_test_passed", False)
        if isinstance(readiness.get("checks"), dict)
        else False
    ) or str(wrapper.get("status", "")).upper() == "PASS"

    verified_unchanged_proven = bool(
        readiness.get("checks", {}).get("verified_unchanged_proven", False)
        if isinstance(readiness.get("checks"), dict)
        else False
    ) or bool(
        wrapper.get("verified_hash_unchanged", False)
        and wrapper.get("verified_mtime_unchanged", False)
        and wrapper.get("verified_size_unchanged", False)
    )

    preflight_blocks_20260517 = bool(preflight.get("settlement_allowed") is False and preflight.get("fail_closed") is True)

    settlement_shadow_fail_preserved = bool(
        readiness.get("checks", {}).get("settlement_shadow_fail_preserved", False)
        if isinstance(readiness.get("checks"), dict)
        else False
    ) or str(shadow.get("status", "")).upper() == "FAIL"

    phase_d_complete = bool(
        readiness.get("checks", {}).get("phase_d_complete", False)
        if isinstance(readiness.get("checks"), dict)
        else False
    ) or bool(completion.get("phase_d_engineering_complete", False))

    known_historical_fail_archived = bool(
        readiness.get("checks", {}).get("known_historical_fail_archived", False)
        if isinstance(readiness.get("checks"), dict)
        else False
    ) or bool(completion.get("known_historical_fail", False))

    production_verified_written = bool(
        readiness.get("production_verified", False)
        or readiness.get("checks", {}).get("production_verified_written", False)
        or preflight.get("production_verified", False)
        or preflight_check.get("production_verified", False)
        or wrapper.get("production_verified", False)
        or shadow.get("production_verified", False)
        or completion.get("production_verified", False)
    )

    secret_safe = _secret_safe(
        [
            readiness_path,
            preflight_path,
            preflight_check_path,
            wrapper_path,
            shadow_path,
            completion_path,
        ]
    )

    if current_branch != "main":
        blockers.append("current_branch_not_main")
    if not d8_readiness_exists:
        blockers.append("d8_readiness_missing")
    if production_verified_written:
        blockers.append("production_verified_written_true")
    if staged["runtime_artifacts_staged"]:
        blockers.append("runtime_artifacts_staged_true")
    if staged["paper_trading_staged"]:
        blockers.append("paper_trading_staged_true")
    if not secret_safe:
        blockers.append("secret_safe_false")

    if d8_readiness_exists and not d8_readiness_status_ok:
        risks.append("d8_readiness_status_not_ok")
    if not preflight_gate_installed:
        risks.append("preflight_gate_not_installed")
    if not wrapper_block_test_passed:
        risks.append("wrapper_block_test_not_passed")
    if not verified_unchanged_proven:
        risks.append("verified_unchanged_not_proven")
    if not preflight_blocks_20260517:
        risks.append("preflight_not_blocking_20260517")

    if not phase_d_complete:
        warnings.append("phase_d_complete_false")
    if not known_historical_fail_archived:
        warnings.append("known_historical_fail_not_archived")
    if not settlement_shadow_fail_preserved:
        warnings.append("settlement_shadow_fail_not_preserved")

    if blockers:
        plan_status = "BLOCKER"
    elif risks:
        plan_status = "NOT_READY"
    elif warnings:
        plan_status = "WARN"
    else:
        plan_status = "READY_FOR_BOSS_REVIEW"

    checks = {
        "phase_d_complete": phase_d_complete,
        "known_historical_fail_archived": known_historical_fail_archived,
        "preflight_gate_installed": preflight_gate_installed,
        "wrapper_block_test_passed": wrapper_block_test_passed,
        "verified_unchanged_proven": verified_unchanged_proven,
        "preflight_blocks_20260517": preflight_blocks_20260517,
        "settlement_shadow_fail_preserved": settlement_shadow_fail_preserved,
        "formal_v2_uses_cache": False,
        "shadow_affects_formal": False,
        "cron_enabled": False,
        "qq_push_enabled": False,
        "production_verified_written": production_verified_written,
        "runtime_artifacts_staged": staged["runtime_artifacts_staged"],
        "paper_trading_staged": staged["paper_trading_staged"],
        "secret_safe": secret_safe,
    }

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "resume_execution_allowed": False,
        "cron_change_allowed": False,
        "qq_push_allowed": False,
        "boss_approval_required": True,
        "plan_status": plan_status,
        "preconditions": {
            "d8_readiness_exists": d8_readiness_exists,
            "d8_readiness_status_ok": d8_readiness_status_ok,
            "preflight_gate_required": True,
            "wrapper_block_test_required": True,
            "known_historical_fail_archived": known_historical_fail_archived,
            "no_runtime_staged": not staged["runtime_artifacts_staged"],
            "no_paper_trading_staged": not staged["paper_trading_staged"],
            "secret_safe": secret_safe,
        },
        "checks": checks,
        "resume_steps": [
            "D.8.1 approve plan only",
            "D.8.2 controlled cron dry-run validation",
            "D.8.3 controlled no-push production dry-run",
            "D.8.4 controlled QQ dry-run route validation",
            "D.8.5 single-window live observe with no settlement write",
            "D.8.6 settlement preflight live guard observe",
            "D.8.7 BOSS approval for limited production resume",
        ],
        "rollback_plan": {
            "disable_cron_immediately": True,
            "keep_preflight_fail_closed": True,
            "no_manual_kill_retry": True,
            "report_watchdog_only": True,
            "preserve_logs": True,
        },
        "forbidden_now": {
            "enable_cron": True,
            "send_qq": True,
            "write_verified": True,
            "write_production_verified": True,
            "enter_phase_e": True,
        },
        "risks": risks,
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"v2_controlled_resume_plan_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if plan_status == "BLOCKER":
        raise SystemExit(2)
    if plan_status == "NOT_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
