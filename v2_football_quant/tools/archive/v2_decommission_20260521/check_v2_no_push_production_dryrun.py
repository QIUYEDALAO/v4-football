#!/usr/bin/env python3
"""Phase D.8.3 — Controlled No-push Production Dry-run (read-only validation)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_no_push_production_dryrun.v1"


REQUIRED_PATHS = {
    "daily_pool_entry": BASE_DIR / "engine" / "v2_daily_pool_summary.py",
    "window_checker_entry": BASE_DIR / "engine" / "v2_window_checker_with_watchdog.py",
    "settlement_entry": BASE_DIR / "engine" / "v2_settle_with_watchdog.py",
    "preflight_guard": BASE_DIR / "engine" / "v2_settlement_preflight_guard.py",
    "qq_sender_entry": BASE_DIR / "engine" / "qqbot_safe_send.py",
}


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
        "runtime_staged": any(f.startswith("data/runtime/") for f in files),
        "paper_staged": any(f.startswith("data/paper_trading/") for f in files),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    warnings: list[str] = []
    blockers: list[str] = []

    missing_paths = [k for k, p in REQUIRED_PATHS.items() if not p.exists()]
    if missing_paths:
        blockers.append("core_entry_paths_missing")

    settle_text = REQUIRED_PATHS["settlement_entry"].read_text(encoding="utf-8", errors="replace") if REQUIRED_PATHS["settlement_entry"].exists() else ""
    preflight_text = REQUIRED_PATHS["preflight_guard"].read_text(encoding="utf-8", errors="replace") if REQUIRED_PATHS["preflight_guard"].exists() else ""
    pool_text = REQUIRED_PATHS["daily_pool_entry"].read_text(encoding="utf-8", errors="replace") if REQUIRED_PATHS["daily_pool_entry"].exists() else ""

    preflight_required = "build_v2_settlement_preflight" in settle_text and "settlement_allowed" in settle_text
    verify_date_call_present = "verify_date(" in settle_text

    no_bet_locked_write = ("locked_stage" not in pool_text) and ("lock_owner" not in pool_text)
    qq_push_blockable = ("--push" in pool_text) and ("push_to_qqbot" in pool_text)

    preflight = _load_json(STATUS_DIR / f"v2_settlement_preflight_{date_key}.json", {})
    preflight_check = _load_json(STATUS_DIR / f"v2_settlement_preflight_check_{date_key}.json", {})
    wrapper = _load_json(STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json", {})
    completion = _load_json(STATUS_DIR / f"phase_d_completion_check_{date_key}.json", {})

    no_push = bool(preflight_check.get("no_push", False))
    no_verified_write = bool(preflight_check.get("no_verified_write", False)) and bool(wrapper.get("verified_hash_unchanged", False))
    no_settlement_rerun = bool(completion.get("no_settlement_rerun", False))
    formal_v2_uses_cache = bool(completion.get("formal_v2_uses_cache", False))
    shadow_affects_formal = bool(completion.get("shadow_affects_formal", False))
    settlement_allowed = preflight.get("settlement_allowed")

    if not preflight_required:
        blockers.append("preflight_not_wired_in_settlement_entry")
    if not verify_date_call_present:
        warnings.append("verify_date_call_not_found_in_settlement_wrapper")
    if settlement_allowed is not False:
        blockers.append("preflight_not_blocking_20260517")
    if not no_push:
        blockers.append("no_push_not_proven")
    if not no_verified_write:
        blockers.append("no_verified_write_not_proven")
    if not no_settlement_rerun:
        warnings.append("no_settlement_rerun_flag_missing_in_completion")
    if formal_v2_uses_cache:
        blockers.append("formal_v2_uses_cache_true")
    if shadow_affects_formal:
        blockers.append("shadow_affects_formal_true")

    if not no_bet_locked_write:
        blockers.append("daily_pool_can_write_bet_locked_risk")

    if qq_push_blockable:
        warnings.append("qq_push_path_exists_must_remain_disabled")

    staged = _staged_flags()
    if staged["runtime_staged"]:
        blockers.append("runtime_artifacts_staged")
    if staged["paper_staged"]:
        blockers.append("paper_trading_staged")

    if blockers:
        status = "BLOCKER" if any(x.endswith("missing") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "dryrun_status": status,
        "production_execution_allowed": False,
        "no_push": True,
        "no_verified_write": bool(no_verified_write),
        "no_bet_locked_write": bool(no_bet_locked_write),
        "no_settlement_rerun": bool(no_settlement_rerun),
        "preflight_required": bool(preflight_required),
        "formal_v2_uses_cache": bool(formal_v2_uses_cache),
        "shadow_affects_formal": bool(shadow_affects_formal),
        "findings": {
            "required_paths": {k: str(v) for k, v in REQUIRED_PATHS.items()},
            "missing_paths": missing_paths,
            "settlement_allowed": settlement_allowed,
            "qq_push_path_blockable": qq_push_blockable,
            "verify_date_call_present": verify_date_call_present,
        },
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_no_push_production_dryrun_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
