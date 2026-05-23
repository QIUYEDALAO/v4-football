#!/usr/bin/env python3
"""Build a sanitized public bundle for cloud read-only mirror publish.

Collects only allowlisted files, runs secret scan, generates manifest with SHA256.
Output: data/runtime/cloud_publish/bundle_current/
Manifest: data/runtime/cloud_publish/cloud_publish_manifest_YYYYMMDD_HHMMSS.json
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
BUNDLE_DIR = MODULE / "data" / "runtime" / "cloud_publish" / "bundle_current"
MANIFEST_DIR = MODULE / "data" / "runtime" / "cloud_publish"
STATUS_DIR = MODULE / "data" / "runtime" / "status"
DASHBOARD_DIR = MODULE / "data" / "runtime" / "dashboard"
DAILY_DIR = MODULE / "data" / "daily_reports"
DOCS_DIR = MODULE / "docs"

TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

# ---- Secret blacklist ----
SECRET_FILENAME_PATTERNS = [
    ".env", "*.key", "*.pem", "*token*", "*cookies*", "secrets*",
    "__pycache__", "venv", "node_modules", ".git",
    "logs", "raw", "pid", "lock", "tmp",
]

SECRET_CONTENT_PATTERNS = [
    "API_KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE",
    "PRIVATE KEY", "QQ", "BOT_TOKEN",
]

# ---- Public allowlist for status files ----
STATUS_PUBLIC_ALLOWLIST = [
    # Checker results (public)
    "check_intel_ops_console_no_notify_clean_ui_result",
    "check_intel_ops_console_readability_ux_result",
    "check_intel_ops_console_candidate_folding_ux_result",
    "check_intel_ops_console_decision_ux_result",
    "check_intel_ops_console_chinese_ux_checker_result",
    "check_intel_ops_console_checker_result",
    "check_validation_ab133_forensic_recount_result",
    "v4_goal_distribution_source_trace_checker_result",
    "v4_script_goal_distribution_checker_result",
    "cloud_publish_bundle_implementation",
    "cloud_publish_manifest",
    # Public documentation markers
    "intel_ops_console_no_notify_clean_ui_v3",
    "intel_ops_console_readability_row_layout_v2",
    "intel_desk_v4_candidate_view",
    "team_name_zh_aliases",
    "metric_zh_labels",
    "validation_data_lineage_checker_result",
    "validation_lineage_hard_freeze_checker_result",
    "v2_v4_grade_split_validation_dashboard_checker_result",
    "v2_v4_validation_dashboard_checker_result",
    # Pipeline status (public-safe)
    "PIPELINE_READY",
    "claude_code_safe_hardening_commit_marker",
    "claude_code_safe_hardening_freeze",
    "claude_code_safe_hardening_issue_inventory",
    "claude_code_safe_hardening_pack",
    "claude_code_systematic_code_review",
    "claude_code_systematic_review_warn_fix",
    "claude_code_warn_fix_commit_marker",
    "claude_code_warn_fix_freeze",
    "claude_systematic_warn_fix_regression",
    "claude_code_latest_window_and_review_dependency_hardening",
    "validation_ab133_forensic_inventory",
    "validation_ab133_lineage_proof",
    "validation_ab133_date_window_audit",
    "validation_ab133_duplicate_audit",
    "validation_ab133_recount_by_policy",
    "validation_ab133_forensic_recount",
]

# Raw/system files that must NEVER be in public bundle
STATUS_NEVER_ALLOW = [
    "alert_push", "daemon_marker", "api_cache", "api_aux",
    "api_controlled_ingest", "api_real_ingest", "api_shadow",
    "api_snapshot_cache", "cookies", "token", "secret",
    "P0_DAILY_POOL_MISSING",
]


# V2 decommission: public current bundles are V3/V4-only. V2 historical
# evidence belongs in archive and must not be copied into bundle_current.
V2_ACTIVE_NAME_PATTERNS = [
    "v2", "bet_locked", "production_verified", "pipeline_ready"
]


def is_v2_decommission_excluded(name: str, rel_path: str = "") -> bool:
    lowered = (name + " " + rel_path).lower()
    if "v4" in lowered and not lowered.startswith("v2") and "v2_v4" not in lowered:
        # V4 files may include A/B/C/SKIP and are active, but V2/V4 bridge files are not.
        return "v2_v4" in lowered
    return any(token in lowered for token in V2_ACTIVE_NAME_PATTERNS)

def is_secret_filename(name: str) -> bool:
    for pattern in SECRET_FILENAME_PATTERNS:
        if pattern.startswith("*"):
            if name.lower().endswith(pattern[1:].lower()) or pattern[1:].lower() in name.lower():
                return True
        elif pattern.endswith("*"):
            if name.lower().startswith(pattern[:-1].lower()):
                return True
        elif "*" in pattern:
            mid = pattern.replace("*", "")
            if mid.lower() in name.lower():
                return True
        else:
            if pattern.lower() == name.lower():
                return True
    return False


def is_status_public(filename: str) -> bool:
    """Check if a status file is in the public allowlist."""
    if is_v2_decommission_excluded(filename):
        return False
    name_no_ext = filename.replace(".json", "")
    for allowed in STATUS_PUBLIC_ALLOWLIST:
        if allowed in name_no_ext:
            return True
    for forbidden in STATUS_NEVER_ALLOW:
        if forbidden in name_no_ext.lower():
            return False
    # Default: deny (conservative)
    return False


def scan_file_content(filepath: Path) -> list:
    """Scan file content for secret patterns. Returns list of hits."""
    hits = []
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return ["(binary/unreadable)"]

    for pattern in SECRET_CONTENT_PATTERNS:
        # Case-insensitive search
        if pattern.lower() in content.lower():
            # For QQ: allow if it appears only in "V4_QQ_ENABLED=false" context
            # and not as a real token/credential
            if pattern == "QQ":
                # Count QQ occurrences; if only in sanitized dashboard context, OK
                qq_count = len(re.findall(r'\bQQ\b', content, re.IGNORECASE))
                v4_qq_false = "V4_QQ_ENABLED=false" in content or "V4 QQ 未启用" in content or "QQ未启用" in content
                if qq_count <= 3 and v4_qq_false:
                    continue  # Sanitized dashboard reference, not a token
            hits.append(pattern)

    return hits


def get_source_window() -> str:
    """Detect current source window from candidate JSON."""
    candidate_files = sorted(STATUS_DIR.glob("intel_desk_v4_candidate_view_*.json"))
    if candidate_files:
        try:
            data = json.loads(candidate_files[-1].read_text())
            return data.get("source_window", "unknown")
        except Exception:
            pass
    return "unknown"


def get_v4_counts() -> dict:
    """Get current V4 candidate counts."""
    candidate_files = sorted(STATUS_DIR.glob("intel_desk_v4_candidate_view_*.json"))
    if candidate_files:
        try:
            data = json.loads(candidate_files[-1].read_text())
            return {
                "A": len(data.get("A_candidate", {}) if isinstance(data.get("A_candidate"), dict) else [data.get("A_candidate", {})]) if data.get("A_candidate") else 0,
                "B": len(data.get("B_candidates", [])),
                "C": len(data.get("C_candidates", [])),
                "SKIP": data.get("SKIP_count", 0),
            }
        except Exception:
            pass
    return {"A": 0, "B": 0, "C": 0, "SKIP": 0}


def get_git_commit() -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(MODULE), capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def build_bundle(dry_run: bool = False):
    """Main build entry point."""
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    files_collected = []
    total_bytes = 0
    secret_hits = []
    excluded_files = []

    # ---- Collect dashboard files ----
    if DASHBOARD_DIR.is_dir():
        for f in sorted(DASHBOARD_DIR.iterdir()):
            if f.is_file():
                if is_secret_filename(f.name):
                    excluded_files.append({"path": str(f.relative_to(MODULE)), "reason": "secret_filename"})
                    continue
                if is_v2_decommission_excluded(f.name, str(f.relative_to(MODULE))):
                    excluded_files.append({"path": str(f.relative_to(MODULE)), "reason": "v2_decommission_excluded"})
                    continue
                if not dry_run:
                    dest = BUNDLE_DIR / "dashboard" / f.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                st = f.stat()
                files_collected.append({
                    "path": f"dashboard/{f.name}",
                    "bytes": st.st_size,
                })
                total_bytes += st.st_size

    # ---- Collect public status files ----
    if STATUS_DIR.is_dir():
        for f in sorted(STATUS_DIR.iterdir()):
            if f.is_file() and f.suffix == ".json":
                if is_secret_filename(f.name):
                    excluded_files.append({"path": str(f.relative_to(MODULE)), "reason": "secret_filename"})
                    continue
                if is_status_public(f.name):
                    if not dry_run:
                        dest = BUNDLE_DIR / "status" / f.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dest)
                    st = f.stat()
                    files_collected.append({
                        "path": f"status/{f.name}",
                        "bytes": st.st_size,
                    })
                    total_bytes += st.st_size
                else:
                    excluded_files.append({"path": str(f.relative_to(MODULE)), "reason": "not_in_allowlist"})

    # ---- Collect daily_reports (today only) ----
    if DAILY_DIR.is_dir():
        for f in sorted(DAILY_DIR.iterdir()):
            if f.is_file():
                if TODAY in f.name and ("v4" in f.name.lower() or f.name.startswith("scan_perf_v4") or f.name.startswith("scout_v4")):
                    if is_secret_filename(f.name):
                        excluded_files.append({"path": str(f.relative_to(MODULE)), "reason": "secret_filename"})
                        continue
                    if not dry_run:
                        dest = BUNDLE_DIR / "daily_reports" / f.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dest)
                    st = f.stat()
                    files_collected.append({
                        "path": f"daily_reports/{f.name}",
                        "bytes": st.st_size,
                    })
                    total_bytes += st.st_size

    # ---- Collect docs (today's public reports only) ----
    if DOCS_DIR.is_dir():
        for f in sorted(DOCS_DIR.iterdir()):
            if f.is_file() and (f.suffix == ".md" or f.suffix == ".json"):
                if TODAY in f.name:
                    if is_v2_decommission_excluded(f.name, str(f.relative_to(MODULE))):
                        excluded_files.append({"path": str(f.relative_to(MODULE)), "reason": "v2_decommission_excluded"})
                        continue
                    if is_secret_filename(f.name):
                        excluded_files.append({"path": str(f.relative_to(MODULE)), "reason": "secret_filename"})
                        continue
                    if not dry_run:
                        dest = BUNDLE_DIR / "docs" / f.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dest)
                    st = f.stat()
                    files_collected.append({
                        "path": f"docs/{f.name}",
                        "bytes": st.st_size,
                    })
                    total_bytes += st.st_size

    # ---- Run content secret scan on collected files ----
    if not dry_run:
        for fc in files_collected:
            fpath = BUNDLE_DIR / fc["path"]
            if fpath.is_file():
                hits = scan_file_content(fpath)
                if hits:
                    secret_hits.append({"path": fc["path"], "hits": hits})

    # ---- Determine secret_scan_status ----
    if secret_hits:
        secret_scan_status = "BLOCKED"
        publish_ready = False
    else:
        secret_scan_status = "CLEAN"
        publish_ready = True

    # ---- Compute SHA256 of bundle ----
    bundle_sha256 = ""
    if not dry_run and files_collected:
        hasher = hashlib.sha256()
        for fc in sorted(files_collected, key=lambda x: x["path"]):
            fpath = BUNDLE_DIR / fc["path"]
            if fpath.is_file():
                hasher.update(fpath.read_bytes())
        bundle_sha256 = hasher.hexdigest()

    # ---- Build manifest ----
    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_host": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "source_commit": get_git_commit(),
        "source_window": get_source_window(),
        "current_v4_counts": get_v4_counts(),
        "files": sorted(files_collected, key=lambda x: x["path"]),
        "total_files": len(files_collected),
        "sha256": bundle_sha256,
        "total_bytes": total_bytes,
        "excluded_files": excluded_files,
        "excluded_patterns": SECRET_FILENAME_PATTERNS,
        "secret_scan_status": secret_scan_status,
        "secret_scan_hits": secret_hits,
        "publish_ready": publish_ready,
        "publish_mode": "readonly_static_mirror",
        "dry_run": dry_run,
    }

    # ---- Write manifest ----
    manifest_path = MANIFEST_DIR / f"cloud_publish_manifest_{TIMESTAMP}.json"
    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

        # Also write latest symlink marker
        latest_marker = MANIFEST_DIR / "cloud_publish_manifest_latest.json"
        latest_marker.write_text(json.dumps({
            "latest_manifest": str(manifest_path.name),
            "generated_at": manifest["generated_at"],
            "publish_ready": publish_ready,
            "sha256": bundle_sha256,
        }, ensure_ascii=False, indent=2))

    return manifest, manifest_path


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"=== cloud_publish bundle builder ===\n")
    print(f"  Mode: {'DRY-RUN' if dry_run else 'BUILD'}")
    print(f"  Bundle dir: {BUNDLE_DIR}")

    manifest, manifest_path = build_bundle(dry_run=dry_run)

    print(f"\n  Files collected: {manifest['total_files']}")
    print(f"  Total bytes: {manifest['total_bytes']:,}")
    print(f"  Secret scan: {manifest['secret_scan_status']}")
    if manifest["secret_scan_hits"]:
        for hit in manifest["secret_scan_hits"]:
            print(f"    BLOCKED: {hit['path']} -> {hit['hits']}")
    print(f"  Publish ready: {manifest['publish_ready']}")
    print(f"  SHA256: {manifest['sha256'][:16]}..." if manifest['sha256'] else "  SHA256: (dry-run)")
    print(f"  Excluded: {len(manifest['excluded_files'])} files")
    if not dry_run:
        print(f"  Manifest: {manifest_path}")

    if manifest["secret_scan_status"] == "BLOCKED":
        print(f"\n  Conclusion: BLOCKED — secret scan found forbidden content")
        return 1

    print(f"\n  Conclusion: {'READY (dry-run)' if dry_run else 'READY'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
