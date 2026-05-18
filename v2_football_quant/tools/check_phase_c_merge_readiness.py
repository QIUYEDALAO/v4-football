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
SCHEMA_VERSION = "phase_c_merge_readiness_check.v1"
TARGET_BRANCH = "codex/phase-c-api-snapshot-cache"

FORBIDDEN_WORDING = [
    "生产验证通过",
    "V2已通过cache",
    "V4已通过cache",
    "cache已生产接入",
    "可以替换正式API",
    "PRODUCTION_VERIFIED=true",
    "PRODUCTION_VERIFIED true",
]

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)APIFOOTBALL_KEY\\s*[:=]\\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)OPENCLAW_APIFOOTBALL_KEY\\s*[:=]\\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)x-apisports-key\\s*[:=]\\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)Bearer\\s+[A-Za-z0-9_\-\\.=]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\\.[A-Za-z0-9_\-]{8,}\\.[A-Za-z0-9_\-]{8,}"),
]


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()


def _run_ok(cmd: list[str]) -> bool:
    return subprocess.run(cmd, cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _contains_sensitive(text: str) -> bool:
    return any(p.search(text) for p in SENSITIVE_PATTERNS)


def _scan_sensitive() -> tuple[bool, list[str]]:
    offenders: list[str] = []
    for sub in [BASE_DIR / "engine", BASE_DIR / "tools", BASE_DIR / "docs"]:
        if not sub.exists():
            continue
        for p in sub.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".pdf", ".xlsx", ".xls"}:
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if _contains_sensitive(txt):
                offenders.append(str(p))
    return len(offenders) == 0, offenders


def _is_negated_context(text: str, idx: int) -> bool:
    window = text[max(0, idx - 10) : idx]
    neg_tokens = ["不", "不得", "不能", "禁止", "勿", "非"]
    return any(tok in window for tok in neg_tokens)


def _scan_wording(paths: list[Path]) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for p in paths:
        if not p.exists() or not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for phrase in FORBIDDEN_WORDING:
            start = 0
            while True:
                idx = txt.find(phrase, start)
                if idx == -1:
                    break
                if not _is_negated_context(txt, idx):
                    hits.append(f"{p}:{phrase}")
                start = idx + len(phrase)
    return len(hits) == 0, hits


def _staged_paths() -> list[str]:
    out = _run(["git", "diff", "--cached", "--name-only"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def _is_forbidden_staged(path: str) -> dict[str, bool]:
    norm = path.replace("\\", "/")
    return {
        "runtime": norm.startswith("data/runtime/"),
        "dashboard_html": norm.startswith("data/runtime/dashboard/") and norm.endswith(".html"),
        "raw_snapshot": "data/runtime/cache/api_snapshot/" in norm,
        "zip": norm.endswith(".zip"),
        "env": norm.endswith(".env") or norm.endswith("/.env") or norm == ".env",
    }


def _phase_markers(date_key: str) -> dict[str, Path]:
    return {
        "api_snapshot_cache_dryrun": STATUS_DIR / f"api_snapshot_cache_dryrun_{date_key}.json",
        "api_snapshot_cache_check": STATUS_DIR / f"api_snapshot_cache_check_{date_key}.json",
        "api_controlled_ingest_sim": STATUS_DIR / f"api_controlled_ingest_sim_{date_key}.json",
        "api_controlled_ingest_check": STATUS_DIR / f"api_controlled_ingest_check_{date_key}.json",
        "api_controlled_ingest_real": STATUS_DIR / f"api_controlled_ingest_real_{date_key}.json",
        "api_real_ingest_check": STATUS_DIR / f"api_real_ingest_check_{date_key}.json",
        "api_cache_reader_dryrun": STATUS_DIR / f"api_cache_reader_dryrun_{date_key}.json",
        "api_cache_reader_check": STATUS_DIR / f"api_cache_reader_check_{date_key}.json",
        "api_shadow_read_dryrun": STATUS_DIR / f"api_shadow_read_dryrun_{date_key}.json",
        "api_shadow_read_check": STATUS_DIR / f"api_shadow_read_check_{date_key}.json",
        "api_shadow_consumer_dryrun": STATUS_DIR / f"api_shadow_consumer_dryrun_{date_key}.json",
        "api_shadow_consumer_check": STATUS_DIR / f"api_shadow_consumer_check_{date_key}.json",
        "dashboard_api_cache_gray_check": STATUS_DIR / f"dashboard_api_cache_gray_check_{date_key}.json",
        "api_aux_display_dryrun": STATUS_DIR / f"api_aux_display_dryrun_{date_key}.json",
        "api_aux_display_check": STATUS_DIR / f"api_aux_display_check_{date_key}.json",
        "api_aux_detail_dryrun": STATUS_DIR / f"api_aux_detail_dryrun_{date_key}.json",
        "api_aux_detail_check": STATUS_DIR / f"api_aux_detail_check_{date_key}.json",
        "api_aux_explain_dryrun": STATUS_DIR / f"api_aux_explain_dryrun_{date_key}.json",
        "api_aux_explain_check": STATUS_DIR / f"api_aux_explain_check_{date_key}.json",
        "api_cache_health_summary": STATUS_DIR / f"api_cache_health_summary_{date_key}.json",
        "api_cache_health_check": STATUS_DIR / f"api_cache_health_check_{date_key}.json",
        "phase_c_completion_check": STATUS_DIR / f"phase_c_completion_check_{date_key}.json",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C merge readiness checker")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = args.date.strip().replace("-", "")

    warnings: list[str] = []
    errors: list[str] = []

    branch = _run(["git", "branch", "--show-current"])
    if branch != TARGET_BRANCH:
        errors.append(f"branch_invalid:{branch}")

    upstream_ok = _run_ok(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if not upstream_ok:
        warnings.append("branch_upstream_missing")

    main_visible = _run_ok(["git", "show-ref", "--verify", "--quiet", "refs/heads/main"])
    origin_main_visible = _run_ok(["git", "show-ref", "--verify", "--quiet", "refs/remotes/origin/main"])
    if not main_visible:
        errors.append("main_branch_missing")
    if not origin_main_visible:
        errors.append("origin_main_missing")

    phase_branch_remote_ref = f"refs/remotes/origin/{TARGET_BRANCH}"
    phase_branch_pushed = _run_ok(["git", "show-ref", "--verify", "--quiet", phase_branch_remote_ref])
    if not phase_branch_pushed:
        warnings.append("phase_branch_remote_ref_missing")

    markers = _phase_markers(date_key)
    missing_markers = [k for k, p in markers.items() if not p.exists()]
    if missing_markers:
        warnings.append("missing_markers:" + ",".join(sorted(missing_markers)))

    completion = _load_json(markers["phase_c_completion_check"], {})
    completion_status = str(completion.get("status", "MISSING")).upper()
    completion_overall = str(completion.get("overall_status", "MISSING")).upper()

    health_summary = _load_json(markers["api_cache_health_summary"], {})
    health_check = _load_json(markers["api_cache_health_check"], {})
    health_overall_status = str(health_summary.get("overall_status", health_summary.get("status", "MISSING"))).upper()

    fail_count = int(health_summary.get("fail_count", 0) or 0)
    blocker_count = int(health_summary.get("blocker_count", 0) or 0)

    production_dependency = bool(completion.get("production_dependency", False))
    production_verified = bool(completion.get("production_verified", False))
    formal_v2_uses_cache = bool(completion.get("formal_v2_uses_cache", False))
    formal_v4_uses_cache = bool(completion.get("formal_v4_uses_cache", False))
    qq_uses_cache = bool(completion.get("qq_uses_cache", False))
    raw_response_visible = bool(completion.get("raw_response_visible", False))
    secret_safe = bool(completion.get("secret_safe", False))

    no_api = bool(completion.get("no_api", False))
    no_key_read = bool(completion.get("no_key_read", False))
    no_push = bool(completion.get("no_push", False))
    no_cron = bool(completion.get("no_cron", False))
    pwa_valid = bool(completion.get("pwa_valid", False))

    runtime_artifacts_staged = bool(completion.get("runtime_artifacts_staged", False))
    dashboard_html_staged = bool(completion.get("dashboard_html_staged", False))
    raw_snapshot_staged = bool(completion.get("raw_snapshot_staged", False))

    if completion_status not in {"PASS", "WARN"}:
        errors.append(f"completion_status_invalid:{completion_status}")
    if completion_overall not in {"PASS", "WARN"}:
        errors.append(f"completion_overall_invalid:{completion_overall}")

    if health_overall_status not in {"PASS", "WARN"}:
        errors.append(f"health_overall_invalid:{health_overall_status}")
    if fail_count > 0:
        errors.append("health_fail_count_gt_zero")
    if blocker_count > 0:
        errors.append("health_blocker_count_gt_zero")

    if not bool(health_check.get("secret_safe", True)):
        errors.append("health_secret_safe_false")
    if not bool(health_check.get("limitations_valid", True)):
        errors.append("health_limitations_invalid")

    staged = _staged_paths()
    staged_runtime = False
    staged_dashboard_html = False
    staged_snapshot = False
    staged_zip = False
    staged_env = False
    for p in staged:
        flags = _is_forbidden_staged(p)
        staged_runtime = staged_runtime or flags["runtime"]
        staged_dashboard_html = staged_dashboard_html or flags["dashboard_html"]
        staged_snapshot = staged_snapshot or flags["raw_snapshot"]
        staged_zip = staged_zip or flags["zip"]
        staged_env = staged_env or flags["env"]

    runtime_artifacts_staged = runtime_artifacts_staged or staged_runtime
    dashboard_html_staged = dashboard_html_staged or staged_dashboard_html
    raw_snapshot_staged = raw_snapshot_staged or staged_snapshot

    if runtime_artifacts_staged:
        errors.append("runtime_artifacts_staged_true")
    if dashboard_html_staged:
        errors.append("dashboard_html_staged_true")
    if raw_snapshot_staged:
        errors.append("raw_snapshot_staged_true")
    if staged_zip:
        errors.append("zip_staged_true")
    if staged_env:
        errors.append("env_staged_true")

    if production_dependency:
        errors.append("production_dependency_true")
    if production_verified:
        errors.append("production_verified_true")
    if formal_v2_uses_cache:
        errors.append("formal_v2_uses_cache_true")
    if formal_v4_uses_cache:
        errors.append("formal_v4_uses_cache_true")
    if qq_uses_cache:
        errors.append("qq_uses_cache_true")
    if raw_response_visible:
        errors.append("raw_response_visible_true")
    if not secret_safe:
        errors.append("secret_safe_false")
    if not no_api:
        errors.append("no_api_false")
    if not no_key_read:
        errors.append("no_key_read_false")
    if not no_push:
        errors.append("no_push_false")
    if not no_cron:
        errors.append("no_cron_false")
    if not pwa_valid:
        errors.append("pwa_valid_false")

    # Dashboard/PWA checks
    api_cache_page = DASHBOARD_DIR / "api_cache.html"
    index_page = DASHBOARD_DIR / "index.html"
    system_page = DASHBOARD_DIR / "system.html"
    sw_path = DASHBOARD_DIR / "service-worker.js"

    if not api_cache_page.exists():
        errors.append("api_cache_page_missing")
    if not index_page.exists():
        errors.append("index_page_missing")
    if not system_page.exists():
        errors.append("system_page_missing")
    if not sw_path.exists():
        errors.append("service_worker_missing")

    page_paths = [api_cache_page, index_page, system_page]
    wording_paths = [BASE_DIR / "tools" / "generate_mobile_dashboard.py", BASE_DIR / "docs" / "PHASE_C_API_SNAPSHOT_CACHE.md", BASE_DIR / "docs" / "PHASE_C_COMPLETION_REPORT.md"] + page_paths

    wording_safe, wording_hits = _scan_wording(wording_paths)
    if not wording_safe:
        errors.append("wording_violation")
        warnings.extend([f"wording_hit:{h}" for h in wording_hits])

    secret_safe_files, secret_offenders = _scan_sensitive()
    if not secret_safe_files:
        errors.append("secret_pattern_detected_in_source")
        warnings.extend([f"secret_source:{p}" for p in secret_offenders])

    # html text explicit secret names / raw response exposure
    html_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in page_paths
        if p.exists()
    )
    for bad in ["APIFOOTBALL_KEY", "OPENCLAW_APIFOOTBALL_KEY", "x-apisports-key"]:
        if bad in html_text:
            errors.append(f"html_contains_{bad.lower()}")
            break

    sw_text = sw_path.read_text(encoding="utf-8", errors="replace") if sw_path.exists() else ""
    pwa_valid = pwa_valid and ("v2v4-dashboard-phase-c8-v1" in sw_text) and ("api_cache.html" in sw_text)
    if not pwa_valid:
        errors.append("pwa_assets_invalid")

    if branch != TARGET_BRANCH:
        status = "BLOCKER"
    elif errors:
        status = "FAIL"
    elif completion_status == "WARN" or health_overall_status == "WARN" or warnings:
        status = "WARN"
    else:
        status = "PASS"

    merge_ready_for_boss_review = status in {"PASS", "WARN"}

    output = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "current_branch": branch,
        "main_visible": main_visible,
        "origin_main_visible": origin_main_visible,
        "phase_branch_pushed": phase_branch_pushed,
        "phase_c_completion_status": completion_status,
        "health_overall_status": health_overall_status,
        "merge_ready_for_boss_review": merge_ready_for_boss_review,
        "merge_to_main_allowed_now": False,
        "pipeline_ready": False,
        "production_verified": False,
        "production_dependency": False,
        "formal_v2_uses_cache": formal_v2_uses_cache,
        "formal_v4_uses_cache": formal_v4_uses_cache,
        "qq_uses_cache": qq_uses_cache,
        "runtime_artifacts_staged": runtime_artifacts_staged,
        "dashboard_html_staged": dashboard_html_staged,
        "raw_snapshot_staged": raw_snapshot_staged,
        "zip_staged": staged_zip,
        "env_staged": staged_env,
        "secret_safe": secret_safe and secret_safe_files,
        "wording_safe": wording_safe,
        "warnings": warnings,
        "errors": errors,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path = STATUS_DIR / f"phase_c_merge_readiness_check_{date_key}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
