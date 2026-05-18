#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
DASHBOARD_DIR = RUNTIME_DIR / "dashboard"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "phase_c_completion_check.v1"
TARGET_BRANCH = "codex/phase-c-api-snapshot-cache"

SECRET_PATTERNS = [
    re.compile(r"APIFOOTBALL_KEY", re.IGNORECASE),
    re.compile(r"OPENCLAW_APIFOOTBALL_KEY", re.IGNORECASE),
    re.compile(r"(?i)token\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{16,}"),
    re.compile(r"(?i)secret\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{10,}"),
]
FORBIDDEN_WORDING = [
    "生产验证通过",
    "V2已通过cache",
    "V4已通过cache",
    "PRODUCTION_VERIFIED true",
    "已接入生产",
    "可以替换正式API",
]


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _norm_status(value: Any) -> str:
    s = str(value or "MISSING").strip().upper()
    mapping = {
        "PASS": "PASS",
        "DONE": "PASS",
        "OK": "PASS",
        "CODE_READY": "PASS",
        "WARN": "WARN",
        "WARNING": "WARN",
        "PARTIAL": "WARN",
        "PARTIAL_DONE": "WARN",
        "FAIL": "FAIL",
        "FAILED": "FAIL",
        "ERROR": "FAIL",
        "BLOCKER": "BLOCKER",
        "MISSING": "MISSING",
        "NONE": "MISSING",
        "": "MISSING",
    }
    return mapping.get(s, "WARN")


def _combine(*vals: str) -> str:
    n = [_norm_status(v) for v in vals]
    if any(v == "BLOCKER" for v in n):
        return "BLOCKER"
    if any(v == "FAIL" for v in n):
        return "FAIL"
    if any(v == "WARN" for v in n):
        return "WARN"
    if any(v == "MISSING" for v in n):
        return "MISSING"
    return "PASS"


def _scan_secret(text: str) -> list[str]:
    hits: list[str] = []
    for idx, pat in enumerate(SECRET_PATTERNS):
        if pat.search(text):
            hits.append(f"secret_pattern_{idx}")
    return hits


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _collect_phase_statuses(date_key: str) -> tuple[dict[str, str], dict[str, Path], dict[str, dict[str, Any]], list[str]]:
    marker_files = {
        "c1_dashboard_status_card": STATUS_DIR / f"dashboard_api_cache_status_card_{date_key}.json",
        "c2_schema_checker": STATUS_DIR / f"api_snapshot_cache_check_{date_key}.json",
        "c3_controlled_sim_main": STATUS_DIR / f"api_controlled_ingest_sim_{date_key}.json",
        "c3_controlled_sim_check": STATUS_DIR / f"api_controlled_ingest_check_{date_key}.json",
        "c4_real_smoke_main": STATUS_DIR / f"api_controlled_ingest_real_{date_key}.json",
        "c4_real_smoke_check": STATUS_DIR / f"api_real_ingest_check_{date_key}.json",
        "c5_reader_main": STATUS_DIR / f"api_cache_reader_dryrun_{date_key}.json",
        "c5_reader_check": STATUS_DIR / f"api_cache_reader_check_{date_key}.json",
        "c6_shadow_read_main": STATUS_DIR / f"api_shadow_read_dryrun_{date_key}.json",
        "c6_shadow_read_check": STATUS_DIR / f"api_shadow_read_check_{date_key}.json",
        "c7_shadow_consumer_main": STATUS_DIR / f"api_shadow_consumer_dryrun_{date_key}.json",
        "c7_shadow_consumer_check": STATUS_DIR / f"api_shadow_consumer_check_{date_key}.json",
        "c8_gray_page": STATUS_DIR / f"dashboard_api_cache_gray_check_{date_key}.json",
        "c9_aux_display_main": STATUS_DIR / f"api_aux_display_dryrun_{date_key}.json",
        "c9_aux_display_check": STATUS_DIR / f"api_aux_display_check_{date_key}.json",
        "c10_aux_detail_main": STATUS_DIR / f"api_aux_detail_dryrun_{date_key}.json",
        "c10_aux_detail_check": STATUS_DIR / f"api_aux_detail_check_{date_key}.json",
        "c11_aux_explain_main": STATUS_DIR / f"api_aux_explain_dryrun_{date_key}.json",
        "c11_aux_explain_check": STATUS_DIR / f"api_aux_explain_check_{date_key}.json",
        "c12_health_main": STATUS_DIR / f"api_cache_health_summary_{date_key}.json",
        "c12_health_check": STATUS_DIR / f"api_cache_health_check_{date_key}.json",
    }

    loaded = {k: _load_json(p, {}) for k, p in marker_files.items()}
    missing = [k for k, p in marker_files.items() if not p.exists()]

    phases = {
        "c1_dashboard_status_card": _norm_status(loaded["c1_dashboard_status_card"].get("status", "MISSING")),
        "c2_schema_checker": _norm_status(loaded["c2_schema_checker"].get("status", "MISSING")),
        "c3_controlled_sim": _combine(loaded["c3_controlled_sim_main"].get("status"), loaded["c3_controlled_sim_check"].get("status")),
        "c4_real_smoke": _combine(loaded["c4_real_smoke_main"].get("status"), loaded["c4_real_smoke_check"].get("status")),
        "c5_reader": _combine(loaded["c5_reader_main"].get("status"), loaded["c5_reader_check"].get("status")),
        "c6_shadow_read": _combine(loaded["c6_shadow_read_main"].get("status"), loaded["c6_shadow_read_check"].get("status")),
        "c7_shadow_consumer": _combine(loaded["c7_shadow_consumer_main"].get("status"), loaded["c7_shadow_consumer_check"].get("status")),
        "c8_gray_page": _norm_status(loaded["c8_gray_page"].get("status", "MISSING")),
        "c9_aux_display": _combine(loaded["c9_aux_display_main"].get("status"), loaded["c9_aux_display_check"].get("status")),
        "c10_aux_detail": _combine(loaded["c10_aux_detail_main"].get("status"), loaded["c10_aux_detail_check"].get("status")),
        "c11_aux_explain": _combine(loaded["c11_aux_explain_main"].get("status"), loaded["c11_aux_explain_check"].get("status")),
        "c12_health_summary": _combine(loaded["c12_health_main"].get("status"), loaded["c12_health_check"].get("status")),
    }
    return phases, marker_files, loaded, missing


def _status_counts(phases: dict[str, str]) -> dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "MISSING": 0, "BLOCKER": 0}
    for s in phases.values():
        counts[_norm_status(s)] += 1
    return counts


def _overall_from_counts(counts: dict[str, int]) -> str:
    if counts["BLOCKER"] > 0:
        return "BLOCKER"
    if counts["FAIL"] > 0:
        return "FAIL"
    if counts["WARN"] > 0 or counts["MISSING"] > 0:
        return "WARN"
    return "PASS"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C completion checker")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = args.date.strip().replace("-", "")

    warnings: list[str] = []
    errors: list[str] = []

    branch = _run(["git", "branch", "--show-current"])
    if branch != TARGET_BRANCH:
        errors.append(f"branch_invalid:{branch}")
        status = "BLOCKER"
    else:
        status = "PASS"

    phases, marker_files, loaded, missing_markers = _collect_phase_statuses(date_key)
    if missing_markers:
        warnings.append("missing_markers:" + ",".join(sorted(missing_markers)))

    counts = _status_counts(phases)
    overall_status = _overall_from_counts(counts)

    # Boundary aggregation from all loaded markers
    all_markers = list(loaded.values())

    def _check_false(key: str) -> bool:
        return any(isinstance(m, dict) and bool(m.get(key, False)) for m in all_markers)

    def _check_true_with_exceptions(
        key: str,
        allowed_false_marker_keys: set[str] | None = None,
    ) -> bool:
        allowed_false_marker_keys = allowed_false_marker_keys or set()
        seen = False
        ok = True
        for mk, mv in loaded.items():
            if not isinstance(mv, dict) or key not in mv:
                continue
            seen = True
            val = bool(mv.get(key, False))
            if val:
                continue
            if mk in allowed_false_marker_keys:
                warnings.append(f"{mk}:{key}_false_allowed")
                continue
            ok = False
        if not seen:
            warnings.append(f"boundary_key_missing:{key}")
            return False
        return ok

    production_dependency = _check_false("production_dependency")
    production_verified = _check_false("production_verified")
    formal_v2_uses_cache = _check_false("formal_v2_uses_cache")
    formal_v4_uses_cache = _check_false("formal_v4_uses_cache")
    qq_uses_cache = _check_false("qq_uses_cache")
    raw_response_visible = _check_false("raw_response_visible")

    secret_flags = [bool(m.get("secret_safe", True)) for m in all_markers if isinstance(m, dict) and "secret_safe" in m]
    secret_safe = all(secret_flags) if secret_flags else False
    if not secret_flags:
        warnings.append("secret_safe_markers_missing")

    no_api = _check_true_with_exceptions("no_api", {"c4_real_smoke_main", "c4_real_smoke_check"})
    no_key_read = _check_true_with_exceptions("no_key_read")
    no_push = _check_true_with_exceptions("no_push")
    no_cron = _check_true_with_exceptions("no_cron")

    if production_dependency:
        errors.append("production_dependency_true_detected")
    if production_verified:
        errors.append("production_verified_true_detected")
    if formal_v2_uses_cache:
        errors.append("formal_v2_uses_cache_true_detected")
    if formal_v4_uses_cache:
        errors.append("formal_v4_uses_cache_true_detected")
    if qq_uses_cache:
        errors.append("qq_uses_cache_true_detected")
    if raw_response_visible:
        errors.append("raw_response_visible_true_detected")
    if not secret_safe:
        errors.append("secret_safe_false_detected")
    if not no_api:
        errors.append("no_api_not_all_true")
    if not no_key_read:
        errors.append("no_key_read_not_all_true")
    if not no_push:
        errors.append("no_push_not_all_true")
    if not no_cron:
        errors.append("no_cron_not_all_true")

    # Dashboard / PWA checks
    api_cache_page = DASHBOARD_DIR / "api_cache.html"
    index_page = DASHBOARD_DIR / "index.html"
    system_page = DASHBOARD_DIR / "system.html"
    sw_path = DASHBOARD_DIR / "service-worker.js"
    manifest_path = DASHBOARD_DIR / "manifest.json"

    page_found = api_cache_page.exists() and index_page.exists() and system_page.exists()
    if not page_found:
        errors.append("dashboard_pages_missing")

    index_txt = _read(index_page)
    api_txt = _read(api_cache_page)
    system_txt = _read(system_page)
    sw_txt = _read(sw_path)
    manifest_txt = _read(manifest_path)
    page_text = "\n".join([index_txt, api_txt, system_txt, sw_txt, manifest_txt])

    if "api_cache.html" not in index_txt:
        errors.append("index_api_cache_nav_missing")
    if "API Cache 每日健康摘要" not in api_txt:
        errors.append("api_cache_health_summary_section_missing")
    if "Cache Health" not in index_txt and "API Cache 每日健康摘要" not in index_txt:
        errors.append("index_health_summary_missing")
    if "Health Summary" not in system_txt and "Cache Health" not in system_txt:
        errors.append("system_health_summary_missing")

    pwa_valid = sw_path.exists() and ("v2v4-dashboard-phase-c8-v1" in sw_txt) and ("./api_cache.html" in sw_txt)
    if not pwa_valid:
        errors.append("pwa_invalid")
    if "v2v4-dashboard-phase1-v1" in sw_txt:
        errors.append("old_phase1_cache_name_detected")

    secret_hits = _scan_secret(page_text)
    if secret_hits:
        errors.append("secret_pattern_in_dashboard")

    if any(x in page_text for x in FORBIDDEN_WORDING):
        errors.append("forbidden_wording_detected")

    raw_response_tokens = ["raw_response", "response_body", "full_response", "body_preview"]
    # raw_response label is allowed as "不展示", so only fail when a suspicious full block appears.
    if "<pre" in api_txt and any(t in api_txt.lower() for t in ["response", "payload"]):
        errors.append("raw_response_block_visible")

    # Git staged artifact checks
    staged = _run(["git", "diff", "--cached", "--name-only"]).splitlines()
    staged = [s.strip() for s in staged if s.strip()]
    runtime_artifacts_staged = any(("/data/runtime/" in p) or p.startswith("data/runtime/") or p.startswith("v2_football_quant/data/runtime/") for p in staged)
    dashboard_html_staged = any(p.endswith(".html") and ("dashboard/" in p or "/dashboard/" in p) for p in staged)
    raw_snapshot_staged = any("real_ingest" in p or "/cache/api_snapshot/" in p or p.endswith(".zip") for p in staged)
    env_staged = any(p.endswith(".env") or "/.env" in p for p in staged)

    if runtime_artifacts_staged:
        errors.append("runtime_artifacts_staged")
    if dashboard_html_staged:
        errors.append("dashboard_html_staged")
    if raw_snapshot_staged:
        errors.append("raw_snapshot_staged")
    if env_staged:
        errors.append("env_file_staged")

    if status != "BLOCKER":
        if errors:
            status = "FAIL"
        else:
            status = "WARN" if overall_status == "WARN" else "PASS"

    result = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "current_branch": branch,
        "phase_statuses": phases,
        "overall_status": overall_status,
        "phase_c_code_ready": status in {"PASS", "WARN"},
        "pipeline_ready": False,
        "production_verified": False,
        "production_dependency": False,
        "formal_v2_uses_cache": formal_v2_uses_cache,
        "formal_v4_uses_cache": formal_v4_uses_cache,
        "qq_uses_cache": qq_uses_cache,
        "secret_safe": secret_safe,
        "no_api": no_api,
        "no_key_read": no_key_read,
        "no_push": no_push,
        "no_cron": no_cron,
        "raw_response_visible": raw_response_visible,
        "runtime_artifacts_staged": runtime_artifacts_staged,
        "dashboard_html_staged": dashboard_html_staged,
        "raw_snapshot_staged": raw_snapshot_staged,
        "pwa_valid": pwa_valid,
        "pass_count": counts["PASS"],
        "warn_count": counts["WARN"],
        "fail_count": counts["FAIL"],
        "missing_count": counts["MISSING"],
        "blocker_count": counts["BLOCKER"],
        "marker_paths": {k: str(v) for k, v in marker_files.items()},
        "warnings": warnings,
        "errors": errors,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path = STATUS_DIR / f"phase_c_completion_check_{date_key}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    merge_ready = (
        status in {"PASS", "WARN"}
        and branch == TARGET_BRANCH
        and not runtime_artifacts_staged
        and not dashboard_html_staged
        and not raw_snapshot_staged
        and secret_safe
        and not production_dependency
        and not production_verified
        and not formal_v2_uses_cache
        and not formal_v4_uses_cache
        and not qq_uses_cache
        and not raw_response_visible
    )
    merge_marker = {
        "status": "READY" if merge_ready else "NOT_READY",
        "schema_version": "phase_c_merge_readiness.v1",
        "date": date_key,
        "current_branch": branch,
        "merge_to_main_allowed_now": False,
        "merge_ready_for_boss_review": bool(merge_ready),
        "overall_status": overall_status,
        "phase_c_completion_status": status,
        "production_dependency": False,
        "production_verified": False,
        "formal_v2_uses_cache": formal_v2_uses_cache,
        "formal_v4_uses_cache": formal_v4_uses_cache,
        "qq_uses_cache": qq_uses_cache,
        "raw_response_visible": raw_response_visible,
        "secret_safe": secret_safe,
        "runtime_artifacts_staged": runtime_artifacts_staged,
        "dashboard_html_staged": dashboard_html_staged,
        "raw_snapshot_staged": raw_snapshot_staged,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    merge_path = STATUS_DIR / f"phase_c_merge_readiness_{date_key}.json"
    merge_path.write_text(json.dumps(merge_marker, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] in {"FAIL", "BLOCKER"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
