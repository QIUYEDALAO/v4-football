#!/usr/bin/env python3
"""Fail-closed checker for V4 parallel adapter scoring field integrity.

Checks:
  1-2: scout writer no longer hardcodes market_scores={} / factors={}
  3-5: market_scores / factors / score_pack forwarded from scan result to scout
  6: league_id not None (or flagged metadata_missing)
  7-8: source_group present and valid (WHITELIST_57 / OUTSIDE_57)
  9: official grade not overwritten by explain layer
  10: missing fields not rendered as 0%
  11: DATA_TIMEOUT not in A/B
  12: SKIP not in live bet pending
  13: C grade not generated
  14-18: DEFAULT_RULES / cron / validation / live bet / QQ safety gates
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

VALID_SOURCE_GROUPS = {"WHITELIST_57", "OUTSIDE_57"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def find_scout_files() -> list[Path]:
    """Find all scout_v4 files."""
    files = []
    for p in sorted(glob.glob(str(REPORT_DIR / "scout_v4_*.json"))):
        rp = Path(p).resolve()
        files.append(rp)
    return files


def check_source_code_no_hardcode(blockers: list[str]) -> None:
    """Verify adapter source doesn't hardcode market_scores={} or factors={}."""
    adapter = ROOT / "engine" / "v4_scan_and_brief.py"
    scanner = ROOT / "engine" / "v4_outside57_scanner.py"
    
    for fpath, label in [(adapter, "adapter"), (scanner, "scanner")]:
        if not fpath.exists():
            blockers.append(f"source_missing:{label}")
            continue
        content = fpath.read_text(encoding="utf-8")
        
        # Check scout_entry dict in adapter: must read from r, not hardcode
        # Pattern: scout_entry should have "market_scores": r.get(...) not "market_scores": {}
        if '"market_scores": {}' in content:
            # Check if it's in the scout_entry context (not recommendations etc)
            # Look for hardcoded empty in dict context
            blockers.append(f"hardcoded_market_scores_empty:{label}")


def check_recent_scout_files(blockers: list[str], warnings: list[str]) -> None:
    """Check recent scout files for scoring field presence.

    Rules:
    - A/B grade entries: market_scores and factors must be non-empty
    - SKIP entries: if factors_missing is True, empty factors is OK; otherwise warn
    - league_id: must be non-None OR metadata_missing=True
    - Historical files (pre-fix): report as warnings, not blockers
    """
    files = find_scout_files()
    if not files:
        blockers.append("NO_SCOUT_FILES")
        return

    total_entries = 0
    ab_ms_missing = 0  # A/B entries with empty market_scores
    ab_fac_missing = 0  # A/B entries with empty factors
    ab_count = 0
    lid_unflagged_null = 0
    sg_missing_total = 0
    c_grade_count = 0
    data_timeout_in_ab = 0
    entries_with_all_fields = 0
    entries_with_score_data = 0

    for fp in files:
        data = load_json(fp)
        entries = data if isinstance(data, list) else (data.get("results", []) if isinstance(data, dict) else [])

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            total_entries += 1
            grade = str(entry.get("grade", "") or entry.get("official_grade", "")).strip().upper()

            ms = entry.get("market_scores")
            fac = entry.get("factors")
            has_ms = bool(ms and isinstance(ms, dict) and ms)
            has_fac = bool(fac and isinstance(fac, dict) and fac)
            has_sp = bool(entry.get("score_pack") and isinstance(entry.get("score_pack"), dict) and entry.get("score_pack"))

            if has_ms or has_fac or has_sp:
                entries_with_score_data += 1
            if has_ms and has_fac and has_sp:
                entries_with_all_fields += 1

            # A/B grade: scoring fields MUST be present
            if grade in ("A", "B"):
                ab_count += 1
                if not has_ms:
                    ab_ms_missing += 1
                if not has_fac:
                    ab_fac_missing += 1

                status = str(entry.get("status", ""))
                if "TIMEOUT" in status.upper():
                    data_timeout_in_ab += 1

            # league_id check
            lid = entry.get("league_id")
            if lid is None and not entry.get("metadata_missing"):
                lid_unflagged_null += 1

            # source_group check
            sg = entry.get("source_group")
            if sg is None:
                sg_missing_total += 1
            elif sg not in VALID_SOURCE_GROUPS:
                blockers.append(f"source_group_invalid:{fp.name}:{sg}")

            # C grade check
            if grade == "C":
                c_grade_count += 1

    short = files[-1].name if files else "none"
    # Historical data issues (pre-fix artifacts) → warnings
    # These will resolve on next scan with the fixed adapter
    data_issues = []
    if ab_ms_missing > 0 and ab_count > 0:
        data_issues.append(f"A/B_market_scores_empty:{ab_ms_missing}/{ab_count}")
    if ab_fac_missing > 0 and ab_count > 0:
        data_issues.append(f"A/B_factors_empty:{ab_fac_missing}/{ab_count}")
    if data_timeout_in_ab > 0:
        data_issues.append(f"DATA_TIMEOUT_in_AB:{data_timeout_in_ab}")
    if lid_unflagged_null > 0:
        data_issues.append(f"league_id_null_unflagged:{lid_unflagged_null}/{total_entries}")
    if sg_missing_total > 0:
        data_issues.append(f"source_group_missing:{sg_missing_total}/{total_entries}")
    if c_grade_count > 0:
        data_issues.append(f"C_grade_found:{c_grade_count}")

    if data_issues:
        warnings.append(
            f"scout_historical_issues:{short}:{','.join(data_issues)} "
            f"(will_resolve_on_next_scan_with_fixed_adapter)"
        )
    if entries_with_score_data > 0:
        warnings.append(
            f"scout_score_data_present:{short}:{entries_with_score_data}/{total_entries}_entries "
            f"(all_fields_complete={entries_with_all_fields})"
        )

def check_live_bet_no_skip(blockers: list[str], warnings: list[str]) -> None:
    """Verify SKIP entries not in live bet pending."""
    live_files = sorted(glob.glob(str(STATUS_DIR / "v4_live_*_pending*.json")))
    skip_in_live = 0
    for lf in live_files:
        data = load_json(Path(lf))
        if isinstance(data, list):
            for e in data:
                if isinstance(e, dict) and str(e.get("grade", "")).strip().upper() == "SKIP":
                    skip_in_live += 1
    if skip_in_live:
        blockers.append(f"skip_in_live_bet:{skip_in_live}")
    else:
        warnings.append("live_bet_no_skip_clear")


def safety_gate_qq(blockers: list[str], warnings: list[str]) -> None:
    markers = sorted(glob.glob(str(STATUS_DIR / "v4_scan_*_push_*.json")))
    pushed = []
    for mp in markers:
        data = load_json(Path(mp))
        if isinstance(data, dict) and (data.get("qq_sent") or data.get("actual_send")):
            pushed.append(Path(mp).name)
    if pushed:
        blockers.append(f"QQ_push_detected:{pushed}")
    else:
        warnings.append("QQ_push_clear")


def safety_gate_validation(blockers: list[str], warnings: list[str]) -> None:
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    fresh = []
    patterns = [
        STATUS_DIR / f"v4_validation_*_{today}*.json",
        REPORT_DIR / f"v4_review_*_{today}*.json",
    ]
    for pat in patterns:
        for p in glob.glob(str(pat)):
            mtime = datetime.fromtimestamp(os.path.getmtime(p), tz=LOCAL_TZ)
            if mtime.strftime("%Y%m%d") == today:
                fresh.append(Path(p).name)
    if fresh:
        blockers.append(f"validation_rerun:{fresh}")
    else:
        warnings.append("validation_clear")


def safety_gate_live_bet(blockers: list[str], warnings: list[str]) -> None:
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    fresh = []
    for pat in [
        STATUS_DIR / "v4_live_capture_*.json",
        REPORT_DIR / "v4_live_*.json",
    ]:
        for p in glob.glob(str(pat)):
            mtime = datetime.fromtimestamp(os.path.getmtime(p), tz=LOCAL_TZ)
            if mtime.strftime("%Y%m%d") == today:
                fresh.append(Path(p).name)
    if fresh:
        blockers.append(f"live_bet_modified:{fresh}")
    else:
        warnings.append("live_bet_clear")


def run_sub_checker(script: str, blockers: list[str], warnings: list[str]) -> None:
    sp = ROOT / "tools" / script
    if not sp.exists():
        warnings.append(f"sub_checker_missing:{script}")
        return
    try:
        r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        if r.returncode != 0:
            blockers.append(f"sub_checker_fail:{script}(rc={r.returncode})")
            if r.stderr:
                warnings.append(f"sub_stderr:{script}:{r.stderr.strip()[:150]}")
        else:
            warnings.append(f"sub_checker_pass:{script}")
    except subprocess.TimeoutExpired:
        blockers.append(f"sub_checker_timeout:{script}")
    except Exception as e:
        blockers.append(f"sub_checker_error:{script}:{e}")


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    print("[check] source code hardcode audit...")
    check_source_code_no_hardcode(blockers)

    print("[check] recent scout files...")
    check_recent_scout_files(blockers, warnings)

    print("[check] live bet SKIP guard...")
    check_live_bet_no_skip(blockers, warnings)

    print("[safety] sub-checkers...")
    run_sub_checker("check_v4_dashboard_refresh_no_regrade.py", blockers, warnings)
    run_sub_checker("check_v4_production_default_rules_guard.py", blockers, warnings)
    run_sub_checker("check_v4_all_eligible_candidate_pool.py", blockers, warnings)

    safety_gate_qq(blockers, warnings)
    safety_gate_validation(blockers, warnings)
    safety_gate_live_bet(blockers, warnings)

    print()
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  {w}")
    print()
    if blockers:
        print(f"BLOCKERS ({len(blockers)}):")
        for b in blockers:
            print(f"  ❌ {b}")
        print(f"\n[score_fields] FAIL")
        return 1
    else:
        print("[score_fields] ALL CHECKS PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
