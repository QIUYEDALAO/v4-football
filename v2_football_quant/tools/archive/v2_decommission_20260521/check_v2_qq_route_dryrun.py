#!/usr/bin/env python3
"""Phase D.8.4 — V2 QQ Route Dry-run Validation (read-only)."""

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
SCHEMA_VERSION = "v2_qq_route_dryrun.v1"

ROUTE_FILES = {
    "qqbot_safe_send": BASE_DIR / "engine" / "qqbot_safe_send.py",
    "safe_outbound_sender": BASE_DIR / "engine" / "safe_outbound_sender.py",
    "v2_daily_pool_summary": BASE_DIR / "engine" / "v2_daily_pool_summary.py",
    "v2_production_readiness": STATUS_DIR / "v2_production_resume_readiness_20260517.json",
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


def _staged_runtime() -> bool:
    staged = _run(["git", "diff", "--cached", "--name-only"])
    files = [x.strip() for x in staged.splitlines() if x.strip()]
    return any(f.startswith("data/runtime/") for f in files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    risks: list[str] = []
    blockers: list[str] = []

    missing = [k for k, p in ROUTE_FILES.items() if not p.exists()]
    if missing:
        blockers.append("qq_route_files_missing")

    safe_sender_text = ROUTE_FILES["safe_outbound_sender"].read_text(encoding="utf-8", errors="replace") if ROUTE_FILES["safe_outbound_sender"].exists() else ""
    qq_safe_text = ROUTE_FILES["qqbot_safe_send"].read_text(encoding="utf-8", errors="replace") if ROUTE_FILES["qqbot_safe_send"].exists() else ""
    pool_text = ROUTE_FILES["v2_daily_pool_summary"].read_text(encoding="utf-8", errors="replace") if ROUTE_FILES["v2_daily_pool_summary"].exists() else ""

    no_push_path = "--dry-run" in qq_safe_text and "qq_delivered" in qq_safe_text
    safe_sender_guard = "allowed_to_push" in safe_sender_text and "template registry" in safe_sender_text.lower()
    v2_pool_manual_push = "--push" in pool_text and "qq" in pool_text and "push_to_qqbot" in pool_text

    readiness = _load_json(STATUS_DIR / f"v2_production_resume_readiness_{date_key}.json", {})
    plan = _load_json(STATUS_DIR / f"v2_controlled_resume_plan_{date_key}.json", {})

    qq_push_allowed = False
    route_send_allowed = False

    if bool(readiness.get("checks", {}).get("qq_push_enabled", False)):
        blockers.append("readiness_qq_push_enabled_true")
    if bool(plan.get("qq_push_allowed", False)):
        blockers.append("controlled_plan_qq_push_allowed_true")

    # No new sent marker allowed: we only pass when nothing staged under runtime
    sent_marker_written = _staged_runtime()
    if sent_marker_written:
        blockers.append("runtime_staged_possible_sent_marker")

    if v2_pool_manual_push:
        risks.append("v2_pool_has_manual_push_path_keep_disabled")
    if not no_push_path:
        risks.append("qqbot_safe_send_dry_run_signature_missing")
    if not safe_sender_guard:
        risks.append("safe_outbound_sender_guard_signature_missing")

    if blockers:
        status = "BLOCKER"
    elif risks:
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "qq_route_status": status,
        "qq_push_allowed": qq_push_allowed,
        "route_send_allowed": route_send_allowed,
        "sent_marker_written": sent_marker_written,
        "no_push": True,
        "route_paths": {k: str(v) for k, v in ROUTE_FILES.items()},
        "risks": risks,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_qq_route_dryrun_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
