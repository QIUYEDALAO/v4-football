#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.api_cache_reader import (
    get_runtime_root,
    load_bundle,
    load_real_ingest_marker,
    read_cache_summary,
)

SCHEMA_VERSION = "api_shadow_read.v1"


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def compare_reader_vs_bundle(date_key: str) -> dict[str, Any]:
    summary = read_cache_summary(date_key)
    bundle = load_bundle(date_key)
    if not isinstance(bundle, dict) or not bundle:
        return {
            "name": "reader_vs_bundle",
            "status": "MISSING",
            "details": {"reason": "bundle_missing"},
        }

    details: dict[str, Any] = {
        "reader_bundle_found": bool((summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}).get("bundle", False)),
        "bundle_schema_version": str(bundle.get("schema_version", "")),
        "reader_bundle_schema_version": str(summary.get("bundle_schema_version", "")),
        "reader_snapshot_count": _safe_int(summary.get("snapshot_count", 0)),
        "bundle_mode": str(bundle.get("mode", "")),
    }
    ok = True
    if details["bundle_schema_version"] != "api_snapshot_cache.v1":
        ok = False
    if details["reader_bundle_schema_version"] and details["reader_bundle_schema_version"] != details["bundle_schema_version"]:
        ok = False
    if bool(bundle.get("production_dependency", True)):
        ok = False
    if details["bundle_mode"] != "dry_run":
        # Not a hard fail for history, but mark not comparable.
        return {
            "name": "reader_vs_bundle",
            "status": "NOT_COMPARABLE",
            "details": {**details, "reason": "bundle_mode_not_dry_run"},
        }

    return {
        "name": "reader_vs_bundle",
        "status": "MATCH" if ok else "MISMATCH",
        "details": details,
    }


def compare_reader_vs_real_ingest(date_key: str) -> dict[str, Any]:
    summary = read_cache_summary(date_key)
    marker = load_real_ingest_marker(date_key)
    if not isinstance(marker, dict) or not marker:
        return {
            "name": "reader_vs_real_ingest",
            "status": "MISSING",
            "details": {"reason": "real_ingest_marker_missing"},
        }

    avail = summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}
    snapshots = summary.get("snapshots", []) if isinstance(summary.get("snapshots", []), list) else []
    req = marker.get("request", {}) if isinstance(marker.get("request", {}), dict) else {}
    details: dict[str, Any] = {
        "reader_real_marker_found": bool(avail.get("real_ingest_marker", False)),
        "reader_real_snapshot_found": bool(avail.get("real_ingest_snapshot", False)),
        "reader_snapshot_count": _safe_int(summary.get("snapshot_count", 0)),
        "marker_request_count": _safe_int(req.get("request_count", 0)),
        "marker_status": str(marker.get("status", "")),
        "marker_mode": str(marker.get("mode", "")),
    }

    if details["marker_mode"] != "controlled_real_smoke":
        return {
            "name": "reader_vs_real_ingest",
            "status": "NOT_COMPARABLE",
            "details": {**details, "reason": "real_ingest_mode_not_controlled_smoke"},
        }

    if not snapshots:
        return {
            "name": "reader_vs_real_ingest",
            "status": "MISSING",
            "details": {**details, "reason": "reader_snapshot_missing"},
        }

    endpoint = str(req.get("endpoint_name", ""))
    matched_endpoint = any(str((s if isinstance(s, dict) else {}).get("endpoint", "")) == endpoint for s in snapshots)
    ok = (
        details["reader_real_marker_found"]
        and details["reader_real_snapshot_found"]
        and details["marker_request_count"] <= 1
        and not bool(marker.get("production_dependency", True))
        and not bool(marker.get("production_verified", True))
        and matched_endpoint
    )
    details["endpoint_match"] = matched_endpoint

    return {
        "name": "reader_vs_real_ingest",
        "status": "MATCH" if ok else "MISMATCH",
        "details": details,
    }


def summarize_shadow_status(report: dict[str, Any]) -> dict[str, int]:
    counts = {"matched": 0, "mismatch": 0, "missing": 0, "not_comparable": 0}
    comps = report.get("comparisons", []) if isinstance(report.get("comparisons", []), list) else []
    for c in comps:
        s = str((c if isinstance(c, dict) else {}).get("status", "MISSING")).upper()
        if s == "MATCH":
            counts["matched"] += 1
        elif s == "MISMATCH":
            counts["mismatch"] += 1
        elif s == "NOT_COMPARABLE":
            counts["not_comparable"] += 1
        else:
            counts["missing"] += 1
    return counts


def validate_shadow_boundary(report: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    if str(report.get("schema_version", "")) != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if str(report.get("mode", "")) != "shadow_read":
        errors.append("mode_invalid")
    if bool(report.get("production_dependency", True)):
        errors.append("production_dependency_not_false")
    if bool(report.get("production_verified", True)):
        errors.append("production_verified_not_false")
    b = report.get("boundaries", {}) if isinstance(report.get("boundaries", {}), dict) else {}
    for k in ("no_api", "no_key_read", "no_push", "no_strategy_recompute", "no_cron", "production_path_untouched"):
        if not bool(b.get(k, False)):
            errors.append(f"{k}_false")
    scope = report.get("business_scope", {}) if isinstance(report.get("business_scope", {}), dict) else {}
    if bool(scope.get("v2_production_compared", True)):
        errors.append("v2_production_compared_not_false")
    if bool(scope.get("v4_production_compared", True)):
        errors.append("v4_production_compared_not_false")

    for comp in report.get("comparisons", []) if isinstance(report.get("comparisons", []), list) else []:
        s = str((comp if isinstance(comp, dict) else {}).get("status", "")).upper()
        if s not in {"MATCH", "MISMATCH", "NOT_COMPARABLE", "MISSING"}:
            errors.append("comparison_status_invalid")
            break

    if report.get("summary", {}).get("mismatch", 0) if isinstance(report.get("summary", {}), dict) else 0:
        warnings.append("shadow_mismatch_detected")
    if report.get("summary", {}).get("not_comparable", 0) if isinstance(report.get("summary", {}), dict) else 0:
        warnings.append("shadow_not_comparable_present")
    return {"status": "PASS" if not errors else "FAIL", "warnings": warnings, "errors": errors}


def build_shadow_read_report(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    summary = read_cache_summary(clean)
    comp_bundle = compare_reader_vs_bundle(clean)
    comp_real = compare_reader_vs_real_ingest(clean)

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "date": clean,
        "mode": "shadow_read",
        "runtime_root": str(get_runtime_root()),
        "production_dependency": False,
        "production_verified": False,
        "boundaries": {
            "no_api": True,
            "no_key_read": True,
            "no_push": True,
            "no_strategy_recompute": True,
            "no_cron": True,
            "production_path_untouched": True,
        },
        "inputs": {
            "reader_summary_found": bool(summary),
            "bundle_found": bool((summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}).get("bundle", False)),
            "real_ingest_marker_found": bool((summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}).get("real_ingest_marker", False)),
            "real_ingest_snapshot_found": bool((summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}).get("real_ingest_snapshot", False)),
        },
        "comparisons": [comp_bundle, comp_real],
        "business_scope": {
            "v2_production_compared": False,
            "v4_production_compared": False,
            "reason": "C6 only compares cache metadata/snapshot availability; V2/V4 production linkage is forbidden",
        },
        "summary": {},
        "warnings": [],
        "errors": [],
    }
    report["summary"] = summarize_shadow_status(report)
    boundary = validate_shadow_boundary(report)
    report["warnings"] = boundary.get("warnings", [])
    report["errors"] = boundary.get("errors", [])
    return report

