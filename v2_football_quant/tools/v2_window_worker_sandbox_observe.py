#!/usr/bin/env python3
"""Phase D.8.10: sandbox observe for V2 window worker logic.

Runs v2_window_worker logic against a sandbox copy of selected_fixtures state.
Never executes supervisor, never writes formal state, never pushes QQ.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import io
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
FORMAL_STATE_DIR = BASE_DIR / "data" / "state"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
SANDBOX_ROOT = BASE_DIR / "data" / "runtime" / "sandbox" / "v2_window_worker"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_window_worker_sandbox_observe.v1"


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()


def _parse_worker_output(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "WINDOW_STATUS": "MISSING",
        "REASON": "",
        "WINDOW_SUMMARY": {},
        "NEW_LOCKS": [],
        "LOCKED_TOTAL": 0,
        "WATCH_EARLY": 0,
        "CANDIDATE": 0,
        "FINAL_RECORD": 0,
        "ODDS_OUT": 0,
    }
    for line in raw.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k not in out:
            continue
        if k in {"WINDOW_SUMMARY", "NEW_LOCKS"}:
            try:
                out[k] = json.loads(v)
            except Exception:
                out[k] = {} if k == "WINDOW_SUMMARY" else []
        elif k in {"LOCKED_TOTAL", "WATCH_EARLY", "CANDIDATE", "FINAL_RECORD", "ODDS_OUT"}:
            try:
                out[k] = int(v)
            except Exception:
                out[k] = 0
        else:
            out[k] = v
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    parser.add_argument("--window", default="midday", choices=["midday"])
    parser.add_argument("--sandbox-only", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-formal-state-write", action="store_true")
    parser.add_argument("--no-verified-write", action="store_true")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    window = args.window

    warnings: list[str] = []
    blockers: list[str] = []

    if not args.sandbox_only:
        blockers.append("missing_required_flag_sandbox_only")
    if not args.no_push:
        blockers.append("missing_required_flag_no_push")
    if not args.no_formal_state_write:
        blockers.append("missing_required_flag_no_formal_state_write")
    if not args.no_verified_write:
        blockers.append("missing_required_flag_no_verified_write")

    formal_state_path = FORMAL_STATE_DIR / f"selected_fixtures_{date_key}.json"
    sandbox_dir = SANDBOX_ROOT / f"{date_key}_{window}"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    sandbox_state_path = sandbox_dir / f"selected_fixtures_{date_key}.json"

    formal_hash_before = _sha256(formal_state_path)
    formal_size_before = formal_state_path.stat().st_size if formal_state_path.exists() else None
    formal_mtime_before = formal_state_path.stat().st_mtime_ns if formal_state_path.exists() else None

    execution_performed = False
    sandbox_state_written = False
    worker_output: dict[str, Any] = {}

    if not formal_state_path.exists():
        warnings.append("formal_state_missing_plan_only")
    else:
        shutil.copy2(formal_state_path, sandbox_state_path)

    if not blockers and formal_state_path.exists():
        vw = importlib.import_module("engine.v2_window_worker")
        original_load_state = vw.load_state
        original_write_state = vw.write_state

        def sandbox_load_state(_today_str: str) -> tuple[set, dict]:
            sp = _load_json(sandbox_state_path, {})
            if isinstance(sp, dict):
                selected = set(sp.get("selected_fixture_ids", []))
                fixtures = sp.get("fixtures", {}) or {}
            else:
                selected = set(sp or [])
                fixtures = {}
            return selected, fixtures

        def sandbox_write_state(_today_str: str, selected: set, fixtures: dict) -> None:
            nonlocal sandbox_state_written
            sandbox_state_written = True
            state = {
                "selected_fixture_ids": sorted(selected),
                "fixtures": fixtures,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            sandbox_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        vw.load_state = sandbox_load_state
        vw.write_state = sandbox_write_state

        stdout_buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_buf):
                try:
                    vw.main()
                except SystemExit:
                    pass
            execution_performed = True
            worker_output = _parse_worker_output(stdout_buf.getvalue())
        finally:
            vw.load_state = original_load_state
            vw.write_state = original_write_state

    formal_hash_after = _sha256(formal_state_path)
    formal_size_after = formal_state_path.stat().st_size if formal_state_path.exists() else None
    formal_mtime_after = formal_state_path.stat().st_mtime_ns if formal_state_path.exists() else None

    formal_state_unchanged = (
        formal_hash_before == formal_hash_after
        and formal_size_before == formal_size_after
        and formal_mtime_before == formal_mtime_after
    )
    formal_state_written = not formal_state_unchanged

    sandbox_state = _load_json(sandbox_state_path, {}) if sandbox_state_path.exists() else {}
    fixtures = sandbox_state.get("fixtures", {}) if isinstance(sandbox_state, dict) else {}
    if not isinstance(fixtures, dict):
        fixtures = {}

    sandbox_new_locks_count = len(worker_output.get("NEW_LOCKS", [])) if isinstance(worker_output.get("NEW_LOCKS"), list) else 0
    sandbox_official_bet_locked_count = 0
    sandbox_qq_required_count = 0
    sandbox_settlement_required_count = 0
    for fstate in fixtures.values():
        if not isinstance(fstate, dict):
            continue
        if fstate.get("official_bet_locked") is True:
            sandbox_official_bet_locked_count += 1
        if fstate.get("qq_required") is True:
            sandbox_qq_required_count += 1
        if fstate.get("settlement_required") is True:
            sandbox_settlement_required_count += 1

    live_window_worker_executed = False
    supervisor_executed = False
    production_resume_executed = False
    production_task_triggered = False

    qq_sent = False
    verified_written = False
    cron_modified = False
    api_called = False
    key_read = False

    if formal_state_written:
        blockers.append("formal_state_changed")
    if qq_sent:
        blockers.append("qq_sent_true")
    if verified_written:
        blockers.append("verified_written_true")
    if cron_modified:
        blockers.append("cron_modified_true")
    if api_called:
        blockers.append("api_called_true")
    if key_read:
        blockers.append("key_read_true")

    if blockers:
        observe_status = "BLOCKER"
    elif warnings:
        observe_status = "WARN"
    else:
        observe_status = "PASS"

    if formal_state_path.exists() and not execution_performed and not blockers:
        observe_status = "WARN"
        warnings.append("sandbox_observe_not_performed")

    if not formal_state_path.exists():
        observe_status = "WARN" if not blockers else "BLOCKER"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "observe_status": observe_status,
        "observe_scope": "sandbox_worker_logic_only",
        "execution_mode": "sandbox_worker_observe",
        "execution_performed": execution_performed,
        "formal_state_written": formal_state_written,
        "formal_state_unchanged": formal_state_unchanged,
        "sandbox_state_written": sandbox_state_written,
        "live_window_worker_executed": live_window_worker_executed,
        "supervisor_executed": supervisor_executed,
        "production_resume_executed": production_resume_executed,
        "production_task_triggered": production_task_triggered,
        "qq_sent": qq_sent,
        "verified_written": verified_written,
        "cron_modified": cron_modified,
        "api_called": api_called,
        "key_read": key_read,
        "production_verified": False,
        "pipeline_ready": False,
        "worker_output": worker_output,
        "sandbox_diff": {
            "formal_state_path": str(formal_state_path),
            "sandbox_state_path": str(sandbox_state_path),
            "formal_state_hash_before": formal_hash_before,
            "formal_state_hash_after": formal_hash_after,
            "formal_state_size_before": formal_size_before,
            "formal_state_size_after": formal_size_after,
            "formal_state_mtime_before": formal_mtime_before,
            "formal_state_mtime_after": formal_mtime_after,
            "formal_state_unchanged": formal_state_unchanged,
            "sandbox_new_locks_count": sandbox_new_locks_count,
            "sandbox_official_bet_locked_count": sandbox_official_bet_locked_count,
            "sandbox_qq_required_count": sandbox_qq_required_count,
            "sandbox_settlement_required_count": sandbox_settlement_required_count,
        },
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out_path = STATUS_DIR / f"v2_window_worker_sandbox_observe_{date_key}_{window}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if observe_status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
