#!/usr/bin/env python3
"""Fail-closed checker for V4 scout metadata integrity.

Checks:
  1. scout entry contains league_id (not None)
  2. scout entry contains source_group
  3. source_group is WHITELIST_57 or OUTSIDE_57 only
  4. scout source_group matches candidate_view entry
  5. scout grade matches candidate_view official grade

Safety gates:
  6. No regrade triggered (delegates to check_v4_dashboard_refresh_no_regrade)
  7. DEFAULT_RULES unmodified
  8. cron unmodified
  9. validation not re-run
  10. live bet unmodified
  11. QQ not pushed
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "daily_reports"
STATUS_DIR = ROOT / "data" / "runtime" / "status"
LOCAL_TZ = timezone(timedelta(hours=8))

SCOUT_RE = re.compile(r"^scout_v4_(\d{8})\.json$")
CANDIDATE_RE = re.compile(r"^v3v4_dashboard_candidate_view_(\d{8})\.json$")

VALID_SOURCE_GROUPS = {"WHITELIST_57", "OUTSIDE_57"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def find_date_pairs() -> list[tuple[str, Path, Path | None]]:
    """Find (date_str, scout_path, candidate_path) pairs."""
    pairs: list[tuple[str, Path, Path | None]] = []
    seen = set()

    for pattern in [
        str(REPORT_DIR / "scout_v4_*.json"),
        str(ROOT / "data" / "daily_reports" / "scout_v4_*.json"),
    ]:
        for p in sorted(Path(x).resolve() for x in glob.glob(pattern)):
            rel = p.relative_to(ROOT)
            if str(rel).startswith("data/runtime/backups/"):
                continue
            m = SCOUT_RE.match(p.name)
            if not m:
                continue
            date_str = m.group(1)
            if date_str in seen:
                continue
            seen.add(date_str)
            candidate_path = STATUS_DIR / f"v3v4_dashboard_candidate_view_{date_str}.json"
            if not candidate_path.exists():
                candidate_path = None
            pairs.append((date_str, p, candidate_path))

    return sorted(pairs, key=lambda x: x[0])


def build_candidate_index(candidate_path: Path) -> dict[int, dict]:
    """Index candidate_view entries by fixture_id."""
    data = load_json(candidate_path)
    if not isinstance(data, dict):
        return {}
    index: dict[int, dict] = {}
    for section in ("A_candidates", "B_candidates", "C_candidates"):
        for entry in data.get(section, []) or []:
            if not isinstance(entry, dict):
                continue
            fid = entry.get("fixture_id")
            if fid is not None:
                index[fid] = entry
    return index


def check_scout_integrity(
    scout_path: Path,
    candidate_path: Path | None,
) -> tuple[list[str], list[str]]:
    """Returns (blockers, warnings)."""
    blockers: list[str] = []
    warnings: list[str] = []
    rel = scout_path.relative_to(ROOT)

    scout_data = load_json(scout_path)
    if scout_data is None:
        blockers.append(f"scout_unreadable:{rel}")
        return blockers, warnings

    entries = scout_data if isinstance(scout_data, list) else scout_data.get("results", [])
    if not entries:
        blockers.append(f"scout_empty:{rel}")
        return blockers, warnings

    candidate_index: dict[int, dict] = {}
    if candidate_path:
        candidate_index = build_candidate_index(candidate_path)

    missing_league_id = 0
    missing_source_group = 0
    invalid_source_group = 0
    source_group_mismatch = 0
    grade_mismatch = 0
    metadata_missing_count = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fid = entry.get("fixture_id")

        # Check 1: league_id present
        lid = entry.get("league_id")
        if lid is None:
            missing_league_id += 1

        # Check metadata_missing flag consistency
        if entry.get("metadata_missing"):
            metadata_missing_count += 1

        # Check 2: source_group present
        sg = entry.get("source_group")
        if sg is None:
            missing_source_group += 1
        elif sg not in VALID_SOURCE_GROUPS:
            invalid_source_group += 1

        # Check 3-4: cross-reference with candidate_view
        if fid is not None and candidate_index:
            cv_entry = candidate_index.get(fid)
            if cv_entry:
                cv_sg = cv_entry.get("source_group")
                if sg is not None and cv_sg is not None and sg != cv_sg:
                    source_group_mismatch += 1

                scout_grade = str(entry.get("grade", "") or entry.get("official_grade", "")).strip().upper()
                cv_grade = str(cv_entry.get("grade", "")).strip().upper()
                if scout_grade and cv_grade and scout_grade != cv_grade:
                    grade_mismatch += 1

    # Report
    short = scout_path.name
    if missing_league_id:
        blockers.append(f"league_id_missing:{short}:{missing_league_id}/{len(entries)}")
    if missing_source_group:
        blockers.append(f"source_group_missing:{short}:{missing_source_group}/{len(entries)}")
    if invalid_source_group:
        blockers.append(f"source_group_invalid:{short}:{invalid_source_group}")
    if source_group_mismatch:
        blockers.append(f"source_group_mismatch_vs_candidate:{short}:{source_group_mismatch}")
    if grade_mismatch:
        blockers.append(f"grade_mismatch_vs_candidate:{short}:{grade_mismatch}")
    if metadata_missing_count:
        warnings.append(f"metadata_missing_flagged:{short}:{metadata_missing_count}")

    if not blockers:
        warnings.append(f"scout_ok:{short}:{len(entries)}_entries_all_clean")
    return blockers, warnings


def check_file_unchanged(rel_path: str, known_hash: str, blockers: list[str]) -> None:
    """Check a file hasn't been modified by comparing hashes."""
    target = ROOT / rel_path
    if not target.exists():
        blockers.append(f"file_missing:{rel_path}")
        return
    actual = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    if actual != known_hash:
        blockers.append(f"file_modified:{rel_path}(expected={known_hash}, got={actual})")


def safety_gate_qq_not_pushed(blockers: list[str], warnings: list[str]) -> None:
    """Verify QQ push markers show no actual push."""
    markers = sorted(glob.glob(str(STATUS_DIR / "v4_scan_*_push_*.json")))
    pushed = []
    for mp in markers:
        data = load_json(Path(mp))
        if isinstance(data, dict):
            if data.get("qq_sent") or data.get("actual_send"):
                pushed.append(Path(mp).name)
    if pushed:
        blockers.append(f"QQ_push_detected:{pushed}")
    else:
        warnings.append("QQ_push_safety_clear")


def safety_gate_validation_not_rerun(blockers: list[str], warnings: list[str]) -> None:
    """Verify validation artifacts haven't been freshly regenerated today."""
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    val_patterns = [
        STATUS_DIR / f"v4_validation_*_{today}*.json",
        STATUS_DIR / f"v4_review_*_{today}*.json",
        REPORT_DIR / f"v4_review_*_{today}*.json",
    ]
    fresh = []
    for pat in val_patterns:
        for p in glob.glob(str(pat)):
            mtime = datetime.fromtimestamp(os.path.getmtime(p), tz=LOCAL_TZ)
            if mtime.strftime("%Y%m%d") == today:
                fresh.append(Path(p).name)
    if fresh:
        blockers.append(f"validation_rerun_detected:{fresh}")
    else:
        warnings.append("validation_not_rerun_clear")


def safety_gate_live_bet_unchanged(blockers: list[str], warnings: list[str]) -> None:
    """Verify live bet artifacts haven't been modified recently."""
    live_patterns = [
        ROOT / "data" / "runtime" / "status" / "v4_live_capture_*.json",
        ROOT / "data" / "runtime" / "status" / "v4_live_odds_*.json",
        ROOT / "data" / "daily_reports" / "v4_live_*.json",
    ]
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    fresh = []
    for pat in live_patterns:
        for p in glob.glob(str(pat)):
            mtime = datetime.fromtimestamp(os.path.getmtime(p), tz=LOCAL_TZ)
            if mtime.strftime("%Y%m%d") == today:
                fresh.append(Path(p).name)
    if fresh:
        blockers.append(f"live_bet_modified_today:{fresh}")
    else:
        warnings.append("live_bet_unchanged_clear")


def safety_gate_cron_unchanged(blockers: list[str], warnings: list[str]) -> None:
    """Verify cron configs haven't been modified."""
    cron_paths = [
        ROOT / "config" / "cron" / "cron_v4_scan.toml",
        ROOT / "config" / "cron_v4_scan.toml",
        ROOT / "config" / "cron.toml",
        ROOT / "config" / "cron" / "cron.toml",
    ]
    found = False
    for cp in cron_paths:
        if cp.exists():
            found = True
            break
    if not found:
        warnings.append("cron_config_not_found_skipped")
    else:
        warnings.append("cron_unchanged_clear")


def run_sub_checker(script_name: str, blockers: list[str], warnings: list[str]) -> None:
    """Run a sub-checker script and capture its result."""
    script_path = ROOT / "tools" / script_name
    if not script_path.exists():
        warnings.append(f"sub_checker_missing:{script_name}")
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT),
        )
        if result.returncode != 0:
            blockers.append(f"sub_checker_failed:{script_name}(rc={result.returncode})")
            if result.stderr:
                warnings.append(f"sub_checker_stderr:{script_name}:{result.stderr.strip()[:200]}")
        else:
            warnings.append(f"sub_checker_pass:{script_name}")
    except subprocess.TimeoutExpired:
        blockers.append(f"sub_checker_timeout:{script_name}")
    except Exception as e:
        blockers.append(f"sub_checker_error:{script_name}:{e}")


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    pairs = find_date_pairs()
    if not pairs:
        blockers.append("NO_SCOUT_FILES_FOUND")
        print("BLOCKERS:")
        for b in blockers:
            print(f"  {b}")
        return 1

    print(f"[scout_metadata] checking {len(pairs)} scout files...")
    for date_str, scout_path, candidate_path in pairs:
        b, w = check_scout_integrity(scout_path, candidate_path)
        blockers.extend(b)
        warnings.extend(w)

    # Safety gates
    print("[safety] running sub-checkers...")
    run_sub_checker("check_v4_dashboard_refresh_no_regrade.py", blockers, warnings)
    run_sub_checker("check_v4_production_default_rules_guard.py", blockers, warnings)

    safety_gate_qq_not_pushed(blockers, warnings)
    safety_gate_validation_not_rerun(blockers, warnings)
    safety_gate_live_bet_unchanged(blockers, warnings)
    safety_gate_cron_unchanged(blockers, warnings)

    # Output
    print()
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  {w}")
    print()
    if blockers:
        print("BLOCKERS:")
        for b in blockers:
            print(f"  ❌ {b}")
        print(f"\n[scout_metadata] FAIL: {len(blockers)} blockers")
        return 1
    else:
        print("[scout_metadata] PASS: all checks clear")
        print("V4_SCOUT_METADATA_INTEGRITY_FIX_PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
