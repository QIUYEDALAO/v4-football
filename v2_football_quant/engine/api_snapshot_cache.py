#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
AUDIT_DIR = RUNTIME_DIR / "audit"
CACHE_DIR = RUNTIME_DIR / "cache"
LEDGER_DIR = RUNTIME_DIR / "ledger"
DAILY_REPORT_DIR = BASE_DIR / "data" / "daily_reports"

CN_TZ = timezone(timedelta(hours=8))

SUPPORTED_MODULES = {"v2", "v4_scan", "v4_review", "dashboard", "ledger"}


def canonical_runtime_root() -> Path:
    return RUNTIME_DIR


def runtime_root_policy() -> dict[str, Any]:
    return {
        "canonical_runtime_root": str(canonical_runtime_root()),
        "project_runtime_used_as_primary": True,
        "workspace_root_runtime_allowed_as_primary": False,
        "path_mismatch_warning_only": True,
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _ensure_under_runtime(path: Path) -> bool:
    try:
        path.resolve().relative_to(RUNTIME_DIR.resolve())
        return True
    except Exception:
        return False


def _detect_path_mismatch(date_key: str) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    parent_runtime = BASE_DIR.parent / "data" / "runtime"
    if not parent_runtime.exists():
        return warnings
    checks = [
        f"status/v2_daily_status_push_{date_key}.json",
        f"status/dashboard_v4_scan_guard_{date_key}.json",
        f"status/dashboard_v4_review_phase2a_status_{date_key}.json",
        f"ledger/{date_key}.json",
    ]
    for rel in checks:
        p_in = RUNTIME_DIR / rel
        p_out = parent_runtime / rel
        if p_in.exists() and p_out.exists():
            warnings.append(
                {
                    "type": "path_mismatch",
                    "project_path": str(p_in),
                    "workspace_root_path": str(p_out),
                }
            )
    return warnings


def discover_sources(module: str, date_key: str) -> list[Path]:
    if module not in SUPPORTED_MODULES:
        return []
    if module == "v2":
        return [
            STATUS_DIR / f"v2_daily_status_push_{date_key}.json",
            AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json",
            STATUS_DIR / "task_status_v2_daily_pool.json",
            STATUS_DIR / "task_status_v2_daily_settle.json",
        ]
    if module == "v4_scan":
        return [
            STATUS_DIR / f"dashboard_v4_scan_guard_{date_key}.json",
            STATUS_DIR / f"dashboard_v4_scan_reading_mode_closure_{date_key}.json",
            STATUS_DIR / f"dashboard_v4_scan_phase2a_status_{date_key}.json",
            STATUS_DIR / f"v4_scan_push_{date_key}_midday.json",
            STATUS_DIR / f"v4_scan_push_{date_key}_latest.json",
            DAILY_REPORT_DIR / f"v4_openclaw_brief_qq_{date_key}.txt",
        ]
    if module == "v4_review":
        return [
            STATUS_DIR / f"dashboard_v4_review_phase2a_status_{date_key}.json",
            STATUS_DIR / f"dashboard_v4_review_guard_{date_key}.json",
            STATUS_DIR / f"v4_review_route_{date_key}.json",
            STATUS_DIR / f"v4_review_push_{date_key}.json",
        ]
    if module == "dashboard":
        return [
            RUNTIME_DIR / "dashboard" / "index.html",
            RUNTIME_DIR / "dashboard" / "v2_today.html",
            RUNTIME_DIR / "dashboard" / "v4_scan.html",
            RUNTIME_DIR / "dashboard" / "v4_review.html",
            RUNTIME_DIR / "dashboard" / "system.html",
            RUNTIME_DIR / "status" / f"system_rearchitecture_phase_ab1_{date_key}.json",
        ]
    if module == "ledger":
        return [
            LEDGER_DIR / f"{date_key}.json",
        ]
    return []


def snapshot_module(module: str, date_key: str) -> dict[str, Any]:
    now = datetime.now(CN_TZ).isoformat()
    srcs = discover_sources(module, date_key)
    items: list[dict[str, Any]] = []
    for p in srcs:
        exists = p.exists()
        in_runtime = _ensure_under_runtime(p) or str(p).startswith(str(DAILY_REPORT_DIR))
        items.append(
            {
                "path": str(p),
                "exists": exists,
                "size_bytes": p.stat().st_size if exists and p.is_file() else 0,
                "sha256": _sha256_file(p) if exists and p.is_file() else None,
                "is_allowed_source": bool(in_runtime),
            }
        )
    missing = [x["path"] for x in items if not x["exists"]]
    disallowed = [x["path"] for x in items if not x["is_allowed_source"]]
    status = "PASS" if not missing and not disallowed else ("WARN" if (not disallowed) else "FAIL")
    return {
        "module": module,
        "date": date_key,
        "generated_at": now,
        "status": status,
        "source_count": len(items),
        "missing_count": len(missing),
        "disallowed_source_count": len(disallowed),
        "sources": items,
        "missing_sources": missing,
        "disallowed_sources": disallowed,
    }


def build_snapshot_bundle(date_key: str, modules: list[str]) -> dict[str, Any]:
    chosen = [m for m in modules if m in SUPPORTED_MODULES]
    if not chosen:
        chosen = sorted(SUPPORTED_MODULES)
    module_snaps = {m: snapshot_module(m, date_key) for m in chosen}
    mismatch = _detect_path_mismatch(date_key)
    return {
        "date": date_key,
        "generated_at": datetime.now(CN_TZ).isoformat(),
        "runtime_root_policy": runtime_root_policy(),
        "path_mismatch_warnings": mismatch,
        "modules": module_snaps,
        "safety": {
            "no_api": True,
            "no_push": True,
            "no_strategy_recompute": True,
            "no_cron": True,
            "production_verified": False,
        },
    }


def write_snapshot_bundle(bundle: dict[str, Any]) -> Path:
    date_key = str(bundle.get("date"))
    out_dir = CACHE_DIR / "api_snapshot" / date_key
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "bundle.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

