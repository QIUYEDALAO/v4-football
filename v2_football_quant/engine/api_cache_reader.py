#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
CACHE_BASE = RUNTIME_DIR / "cache" / "api_snapshot"

SCHEMA_VERSION = "api_cache_reader.v1"

_SECRET_PATTERNS = [
    re.compile(r"(?i)x-apisports-key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)apifootball[_-]?key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)token\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{16,}"),
    re.compile(r"(?i)secret\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def get_runtime_root() -> Path:
    return RUNTIME_DIR


def get_cache_root(date_key: str) -> Path:
    clean = str(date_key).strip().replace("-", "")
    return CACHE_BASE / clean


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _secret_safe_text(text: str) -> bool:
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            return False
    return True


def load_bundle(date_key: str) -> dict[str, Any]:
    return _load_json(get_cache_root(date_key) / "bundle.json", {})


def load_real_ingest_marker(date_key: str) -> dict[str, Any]:
    marker = get_runtime_root() / "status" / f"api_controlled_ingest_real_{str(date_key).strip().replace('-', '')}.json"
    return _load_json(marker, {})


def load_real_ingest_snapshot(date_key: str, endpoint: str) -> dict[str, Any]:
    endpoint_name = endpoint.strip()
    snap = get_cache_root(date_key) / "real_ingest" / f"{endpoint_name}.json"
    return _load_json(snap, {})


def list_available_snapshots(date_key: str) -> list[Path]:
    real_dir = get_cache_root(date_key) / "real_ingest"
    if not real_dir.exists() or not real_dir.is_dir():
        return []
    return sorted([p for p in real_dir.glob("*.json") if p.is_file()])


def _detect_schema(record: dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    schema = str(record.get("schema_version", "")).strip()
    return bool(schema)


def _snapshot_meta(path: Path) -> dict[str, Any]:
    payload = _load_json(path, {})
    txt = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    endpoint = ""
    if isinstance(payload, dict):
        endpoint = str(payload.get("endpoint_name") or payload.get("endpoint") or path.stem)
    return {
        "endpoint": endpoint or path.stem,
        "path": str(path),
        "schema_detected": _detect_schema(payload),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "secret_safe": _secret_safe_text(txt),
    }


def read_cache_summary(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    cache_root = get_cache_root(clean)
    bundle_path = cache_root / "bundle.json"
    marker_path = get_runtime_root() / "status" / f"api_controlled_ingest_real_{clean}.json"
    snapshots = list_available_snapshots(clean)
    snapshot_rows = [_snapshot_meta(p) for p in snapshots]

    bundle = load_bundle(clean)
    marker = load_real_ingest_marker(clean)

    warnings: list[str] = []
    errors: list[str] = []
    if not bundle_path.exists():
        warnings.append("bundle_missing")
    if not marker_path.exists():
        warnings.append("real_ingest_marker_missing")

    if not cache_root.exists():
        errors.append("cache_root_missing")

    secret_safe = all(bool(x.get("secret_safe")) for x in snapshot_rows) if snapshot_rows else True
    if not secret_safe:
        errors.append("snapshot_secret_risk")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "date": clean,
        "mode": "read_only",
        "runtime_root": str(get_runtime_root()),
        "cache_root": str(cache_root),
        "production_dependency": False,
        "production_verified": False,
        "boundaries": {
            "no_api": True,
            "no_key_read": True,
            "no_push": True,
            "no_strategy_recompute": True,
            "no_cron": True,
        },
        "available": {
            "bundle": bundle_path.exists(),
            "real_ingest_marker": marker_path.exists(),
            "real_ingest_snapshot": len(snapshot_rows) > 0,
        },
        "snapshots": snapshot_rows,
        "snapshot_count": len(snapshot_rows),
        "bundle_schema_version": str(bundle.get("schema_version", "")) if isinstance(bundle, dict) else "",
        "real_ingest_status": str(marker.get("status", "")) if isinstance(marker, dict) else "",
        "secret_safe": secret_safe,
        "warnings": warnings,
        "errors": errors,
    }
    return summary


def validate_cache_read_boundary(summary: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    if str(summary.get("schema_version")) != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if str(summary.get("mode")) != "read_only":
        errors.append("mode_invalid")
    if bool(summary.get("production_dependency", True)):
        errors.append("production_dependency_not_false")
    if bool(summary.get("production_verified", True)):
        errors.append("production_verified_not_false")

    b = summary.get("boundaries", {}) if isinstance(summary.get("boundaries", {}), dict) else {}
    if not bool(b.get("no_api", False)):
        errors.append("no_api_false")
    if not bool(b.get("no_key_read", False)):
        errors.append("no_key_read_false")
    if not bool(b.get("no_push", False)):
        errors.append("no_push_false")
    if not bool(b.get("no_strategy_recompute", False)):
        errors.append("no_strategy_recompute_false")
    if not bool(b.get("no_cron", False)):
        errors.append("no_cron_false")

    if not str(summary.get("runtime_root", "")).endswith("/data/runtime"):
        warnings.append("runtime_root_not_project_data_runtime")

    snap_rows = summary.get("snapshots", []) if isinstance(summary.get("snapshots", []), list) else []
    for row in snap_rows:
        if not bool((row if isinstance(row, dict) else {}).get("secret_safe", False)):
            errors.append("snapshot_secret_unsafe")
            break

    if int(summary.get("snapshot_count", 0) or 0) != len(snap_rows):
        errors.append("snapshot_count_mismatch")

    return {
        "status": "PASS" if not errors else "FAIL",
        "warnings": warnings + (summary.get("warnings", []) if isinstance(summary.get("warnings", []), list) else []),
        "errors": errors + (summary.get("errors", []) if isinstance(summary.get("errors", []), list) else []),
    }
