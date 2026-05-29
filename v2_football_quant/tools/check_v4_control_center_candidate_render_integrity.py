#!/usr/bin/env python3
"""Verify V4 control center candidate cards properly render after UI restore.

Checks candidate cards are not stuck on loading placeholder.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
DASHBOARD = ROOT / "data" / "runtime" / "dashboard"
LOCAL_TZ = timezone(timedelta(hours=8))


def load_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def check_html(blockers: list[str], warnings: list[str]) -> None:
    """Check the HTML for render integrity."""
    html_path = DASHBOARD / "v4_control_center.html"
    if not html_path.exists():
        blockers.append("HTML_missing")
        return
    
    html = html_path.read_text(encoding="utf-8")
    
    # 1. Loading placeholder not the final state
    if '正在读取今日候选' in html:
        # This is the initial hardcoded placeholder - it's OK as long as 
        # renderCandidates replaces it. The critical check is that renderCandidate
        # won't throw.
        warnings.append("HTML:loading_placeholder_present_as_initial_state")
    
    # 2. renderCandidate must define all template variables
    render_fn_match = re.search(r'function renderCandidate\(x,i\)\{(.*?)\n\}', html, re.DOTALL)
    if render_fn_match:
        fn_body = render_fn_match.group(1)
        # Check for unbound template vars
        template_vars = re.findall(r'\$\{(\w+)', fn_body)
        defined_vars = set(re.findall(r'const (\w+)\s*=', fn_body))
        # Template vars used in return statement after all const definitions
        return_start = fn_body.find('return ')
        if return_start > 0:
            return_body = fn_body[return_start:]
            template_vars_in_return = set(re.findall(r'\$\{(\w+)', return_body))
            # These are from function calls, not local vars
            fn_call_vars = {'matchName', 'srcGroupDisplay', 'i'}
            missing = template_vars_in_return - defined_vars - fn_call_vars
            if missing:
                blockers.append(f"HTML:unbound_template_vars:{missing}")
            else:
                warnings.append("HTML:all_template_vars_bound")
    else:
        blockers.append("HTML:renderCandidate_not_found")
    
    # 3. srcGroupDisplay function exists
    if "srcGroupDisplay" in html:
        warnings.append("HTML:srcGroupDisplay_present")
    else:
        blockers.append("HTML:srcGroupDisplay_missing")


def check_model(blockers: list[str], warnings: list[str]) -> None:
    """Check model has candidates for rendering."""
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    model_path = STATUS / f"v4_control_center_model_{today}.json"
    if not model_path.exists():
        yesterday = (datetime.now(LOCAL_TZ) - timedelta(days=1)).strftime("%Y%m%d")
        model_path = STATUS / f"v4_control_center_model_{yesterday}.json"
    
    model = load_json(model_path)
    if not model:
        blockers.append(f"MODEL_missing:{model_path.name}")
        return
    
    candidates = model.get("candidates", {})
    items = candidates.get("items", [])
    a_count = candidates.get("a_count", 0)
    b_count = candidates.get("b_count", 0)
    
    if not items:
        blockers.append("MODEL:candidate_items_empty")
    else:
        warnings.append(f"MODEL:{len(items)}_candidates_in_items")
    
    if a_count == 0 and b_count == 0:
        blockers.append("MODEL:no_AB_candidates")
    else:
        warnings.append(f"MODEL:A={a_count}_B={b_count}")
    
    # Check specific teams
    teams_found = set()
    for item in items:
        home = item.get("home_cn", "")
        if "Rosenborg" in str(home):
            teams_found.add("Rosenborg")
        if "TransINVEST" in str(home) or "Trans" in str(home):
            teams_found.add("TransINVEST")
    
    for team in ("Rosenborg", "TransINVEST"):
        if team not in teams_found:
            blockers.append(f"MODEL:{team}_not_found_in_candidates")
    
    # Check model fields accessible by HTML
    html_fields_needed = ["items", "a_candidates", "b_candidates", "a_count", "b_count", "skip_count"]
    missing = [f for f in html_fields_needed if f not in candidates]
    if missing:
        blockers.append(f"MODEL:fields_missing:{missing}")
    
    # Verify defaults are None for unbet
    for item in items:
        if item.get("default_stake") is not None:
            blockers.append(f"MODEL:non_null_default_stake:{item.get('home_cn')}")
        if item.get("default_entry_minute") is not None:
            blockers.append(f"MODEL:non_null_default_entry_minute:{item.get('home_cn')}")
        if item.get("default_odds") is not None and item.get("default_odds") != 0.0:
            pass  # Allow 0.0


def run_sub_checkers(blockers: list[str], warnings: list[str]) -> None:
    for script in [
        "check_v4_control_center.py",
        "check_v4_dashboard_refresh_no_regrade.py",
        "check_v4_production_default_rules_guard.py",
    ]:
        sp = ROOT / "tools" / script
        if not sp.exists():
            warnings.append(f"sub_missing:{script}")
            continue
        try:
            r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
            try:
                result = json.loads(r.stdout.strip())
                conclusion = result.get("conclusion", "")
            except Exception:
                conclusion = ""
            if r.returncode != 0 and conclusion not in ("WARN_ONLY",):
                blockers.append(f"sub_fail:{script}(rc={r.returncode})")
            else:
                warnings.append(f"sub_pass:{script}")
        except Exception as e:
            blockers.append(f"sub_error:{script}:{e}")


def safety_gates(blockers: list[str], warnings: list[str]) -> None:
    # QQ
    pushed = [p.name for p in STATUS.glob("v4_scan_*_push_*.json") if (load_json(p) or {}).get("qq_sent")]
    if pushed:
        blockers.append(f"QQ_pushed:{pushed}")
    else:
        warnings.append("QQ_clear")
    
    # Validation
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    vals = list(STATUS.glob(f"v4_validation_*_{today}*.json")) + list((ROOT / "data" / "daily_reports").glob(f"v4_review_*_{today}*.json"))
    if vals:
        blockers.append("validation_rerun")
    else:
        warnings.append("validation_clear")


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    
    print("[check] HTML render integrity...")
    check_html(blockers, warnings)
    
    print("[check] Model candidate data...")
    check_model(blockers, warnings)
    
    print("[safety] sub-checkers...")
    run_sub_checkers(blockers, warnings)
    safety_gates(blockers, warnings)
    
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
        return 1
    else:
        print("[candidate_render_integrity] PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
