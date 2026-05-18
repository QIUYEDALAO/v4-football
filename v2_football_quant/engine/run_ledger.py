#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from engine.state_machine import normalize_status
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.state_machine import normalize_status


BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
AUDIT_DIR = RUNTIME_DIR / "audit"
LEDGER_DIR = RUNTIME_DIR / "ledger"
DAILY_REPORT_DIR = BASE_DIR / "data" / "daily_reports"

CN_TZ = timezone(timedelta(hours=8))


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _review_due_time(date_key: str) -> str:
    base = datetime.strptime(date_key, "%Y%m%d").replace(tzinfo=CN_TZ)
    due = (base + timedelta(days=1)).replace(hour=12, minute=35, second=0, microsecond=0)
    return due.isoformat()


def _detect_path_mismatch(date_key: str) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    parent_runtime = BASE_DIR.parent / "data" / "runtime"
    if not parent_runtime.exists():
        return warnings
    checks = [
        f"status/v2_daily_status_push_{date_key}.json",
        f"status/dashboard_v4_scan_guard_{date_key}.json",
        f"status/dashboard_v4_review_phase2a_status_{date_key}.json",
    ]
    for rel in checks:
        p_in = RUNTIME_DIR / rel
        p_out = parent_runtime / rel
        if p_in.exists() and p_out.exists():
            warnings.append(
                {
                    "type": "path_mismatch",
                    "message": "project/runtime 与 workspace-root/runtime 同名文件并存",
                    "project_path": str(p_in),
                    "workspace_root_path": str(p_out),
                }
            )
    return warnings


def build_ledger(date_key: str) -> dict[str, Any]:
    now = datetime.now(CN_TZ)

    v2_daily_status = _load_json(STATUS_DIR / f"v2_daily_status_push_{date_key}.json", {})
    v2_missed = _load_json(AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json", {})
    v2_pool_task = _load_json(STATUS_DIR / "task_status_v2_daily_pool.json", {})
    v2_settle_task = _load_json(STATUS_DIR / "task_status_v2_daily_settle.json", {})

    v4_scan_guard = _load_json(STATUS_DIR / f"dashboard_v4_scan_guard_{date_key}.json", {})
    v4_scan_closure = _load_json(STATUS_DIR / f"dashboard_v4_scan_reading_mode_closure_{date_key}.json", {})
    v4_scan_phase = _load_json(STATUS_DIR / f"dashboard_v4_scan_phase2a_status_{date_key}.json", {})

    v4_review_phase = _load_json(STATUS_DIR / f"dashboard_v4_review_phase2a_status_{date_key}.json", {})
    v4_review_guard = _load_json(STATUS_DIR / f"dashboard_v4_review_guard_{date_key}.json", {})
    v4_review_route = _load_json(STATUS_DIR / f"v4_review_route_{date_key}.json", {})
    v4_review_sent = _load_json(STATUS_DIR / f"v4_review_push_{date_key}.json", {})

    review_due_iso = str(v4_review_phase.get("review_due_time") or _review_due_time(date_key))
    try:
        due_dt = datetime.fromisoformat(review_due_iso)
        due_reached = now >= due_dt
    except Exception:
        due_reached = False

    review_status = "WAITING_DUE_TIME" if not due_reached else "MISSING"
    if due_reached and str(v4_review_guard.get("guard_status", "")).upper() == "PASS":
        review_status = "DONE"

    production_evidence_windows: list[str] = []
    wr = v4_scan_guard.get("window_results", {})
    if isinstance(wr, dict):
        for k, v in wr.items():
            if isinstance(v, dict) and _bool(v.get("production_evidence")):
                production_evidence_windows.append(k)

    v2_status = str(v2_daily_status.get("status") or "UNKNOWN").upper()
    v2_official_locked = _to_int(v2_daily_status.get("official_bet_locked"), 0)
    v2_missed_count = _to_int(v2_daily_status.get("missed_candidates"), _to_int(v2_missed.get("candidate_count"), 0))
    v2_prod_pushed = _bool(v2_daily_status.get("production_recommendation"))
    v2_receipt_pushed = _bool(v2_daily_status.get("pushed"))
    v2_settlement_required = _bool(v2_daily_status.get("settlement_required"))
    v2_settlement_objects = 1 if v2_settlement_required else 0

    if v2_settlement_required:
        settle_status = normalize_status(v2_settle_task.get("status"), kind="runtime")
    else:
        settle_status = "NO_OBJECTS"

    issues = {
        "p0": [
            "P0_PRODUCTION_FACT_SOURCE_MISSING",
            "P0_REPLAY_CAPABILITY_MISSING",
        ],
        "p1": [
            "P1_API_SLOW_IMPACTS_CRON",
            "P1_CRON_FRAGMENTATION",
            "P1_RUNTIME_PATH_INCONSISTENCY",
            "P1_V2_LOCK_STAGE_OWNERSHIP_CONFLICT",
            "P1_V4_SCAN_WINDOW_EVIDENCE_GAP",
            "P1_V4_REVIEW_CHAIN_NATURAL_VALIDATION_GAP",
            "P1_REPORT_DASHBOARD_QQ_INCONSISTENCY",
        ],
        "p2": [
            "P2_DASHBOARD_INTERNAL_PUBLIC_NOT_SPLIT",
            "P2_GITHUB_MAIN_LOCAL_WORKSPACE_DRIFT",
            "P2_STATE_TERMS_INCONSISTENT",
            "P2_MARKER_SCHEMA_INCONSISTENT",
        ],
        "p3": [
            "P3_NAME_NORMALIZER_ALIAS_BACKFILL",
            "P3_UI_POLISH_PUBLIC_DASHBOARD",
        ],
    }

    path_mismatch = _detect_path_mismatch(date_key)

    ledger = {
        "date": date_key,
        "generated_at": now.isoformat(),
        "source_root": str(RUNTIME_DIR),
        "warnings": path_mismatch,
        "v2": {
            "status": v2_status,
            "daily_pool_status": normalize_status(v2_pool_task.get("status"), kind="runtime"),
            "official_bet_locked": v2_official_locked,
            "missed_candidates": v2_missed_count,
            "qq_recommendation_pushed": v2_prod_pushed,
            "status_receipt_pushed": v2_receipt_pushed,
            "settlement_objects": v2_settlement_objects,
            "settlement_status": settle_status,
            "evidence": {
                "daily_status_push": str(STATUS_DIR / f"v2_daily_status_push_{date_key}.json"),
                "missed_audit": str(AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json"),
                "lock_rule": "official_bet_locked=true + lock_owner=window_checker + status=BET_LOCKED",
                "selected_fixtures_used_for_lock_decision": False,
            },
        },
        "v4_scan": {
            "reading_status": str(v4_scan_closure.get("reading_status") or "MISSING").upper(),
            "render_status": str(v4_scan_guard.get("render_status") or "MISSING").upper(),
            "data_guard_status": str(v4_scan_guard.get("data_guard_status") or "MISSING").upper(),
            "production_verified": False,
            "production_evidence_windows": production_evidence_windows,
            "windows": {
                "late": v4_scan_guard.get("window_results", {}).get("late", {}),
                "early": v4_scan_guard.get("window_results", {}).get("early", {}),
                "midday": v4_scan_guard.get("window_results", {}).get("midday", {}),
                "evening": v4_scan_guard.get("window_results", {}).get("evening", {}),
                "night": v4_scan_guard.get("window_results", {}).get("night", {}),
            },
            "readable_summary": v4_scan_closure.get("readable_summary", {}),
            "evidence": {
                "scan_guard_file": str(STATUS_DIR / f"dashboard_v4_scan_guard_{date_key}.json"),
                "scan_phase_status_file": str(STATUS_DIR / f"dashboard_v4_scan_phase2a_status_{date_key}.json"),
                "scan_reading_closure_file": str(STATUS_DIR / f"dashboard_v4_scan_reading_mode_closure_{date_key}.json"),
                "fallback_used_not_production_evidence": True,
            },
        },
        "v4_review": {
            "review_date": date_key,
            "due_time": review_due_iso,
            "status": review_status,
            "nine_step": str(v4_review_phase.get("nine_step_display") or ("WAITING_TRIGGER" if not due_reached else "UNKNOWN")),
            "production_verified": False,
            "evidence": {
                "review_phase_file": str(STATUS_DIR / f"dashboard_v4_review_phase2a_status_{date_key}.json"),
                "review_guard_file": str(STATUS_DIR / f"dashboard_v4_review_guard_{date_key}.json"),
                "review_route_file": str(STATUS_DIR / f"v4_review_route_{date_key}.json"),
                "review_sent_file": str(STATUS_DIR / f"v4_review_push_{date_key}.json"),
                "guard_status": str(v4_review_guard.get("guard_status") or "MISSING").upper(),
                "route_allowed_to_push": _bool(v4_review_route.get("allowed_to_push")),
                "sent_status": str(v4_review_sent.get("status") or "MISSING").upper(),
            },
        },
        "dashboard": {
            "render_status": str(v4_scan_guard.get("render_status") or "MISSING").upper(),
            "reading_status": str(v4_scan_closure.get("reading_status") or "MISSING").upper(),
            "data_guard_status": str(v4_scan_guard.get("data_guard_status") or "MISSING").upper(),
            "pwa_local": (BASE_DIR / "data" / "runtime" / "dashboard" / "index.html").exists(),
            "production_verified": False,
            "ledger_source": "present",
        },
        "notifications": {
            "qq_enabled": False,
            "cron_enabled": False,
            "push_sent": False,
        },
        "issues": issues,
        "final_status": {
            "status": "CODE_READY",
            "production_verified": False,
            "strategy_changed": False,
            "api_called": False,
            "qq_pushed": False,
            "cron_enabled": False,
        },
    }
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Daily Run Ledger v1")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = args.date.strip().replace("-", "")
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    ledger = build_ledger(date_key)
    out = LEDGER_DIR / f"{date_key}.json"
    out.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "date": date_key, "ledger": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
