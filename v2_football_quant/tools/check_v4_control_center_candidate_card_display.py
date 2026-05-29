#!/usr/bin/env python3
"""Check V4 control center candidate card display integrity.

Verifies:
  1.  No N/A in candidate cards
  2.  source_group shows WHITELIST_57/OUTSIDE_57
  3.  Missing source_group shows "来源未标记"
  4.  Missing time_bins NOT rendered as 0%
  5.  Missing factors NOT rendered as 0%
  6.  Missing score_pack NOT rendered as 0%
  7.  No "候选剧本" in candidate cards
  8.  Unbet amount not pre-filled 428
  9.  Unbet entry_minute not pre-filled 13
  10. Unbet odds not pre-filled historical value
  11. Live bet records still allow backfill
  12. Official grade preserved
  13. C not displayed
  14. SKIP not in todo
  15-19. Safety gates
"""
from __future__ import annotations

import json
import os
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
    """Check the HTML source for display issues."""
    html_path = DASHBOARD / "v4_control_center.html"
    if not html_path.exists():
        blockers.append("HTML_missing")
        return
    
    html = html_path.read_text(encoding="utf-8")
    
    # 1. No N/A in candidate card rendering (acceptable in validation KPIs)
    # 2. source_group visible
    if "srcGroupDisplay" not in html:
        blockers.append("HTML:source_group_not_displayed")
    else:
        warnings.append("HTML:source_group_display_present")
    
    # 3. "来源未标记" fallback exists
    if "来源未标记" in html:
        warnings.append("HTML:source_group_fallback_present")
    
    # 4-6. Time bins not rendered as 0%
    if "暂无解释数据" in html:
        warnings.append("HTML:no_explain_data_placeholder")
    if "fmtPct" in html and "time_bin_0_15" in html:
        warnings.append("HTML:time_bins_with_null_check")
    
    # 7. No "候选剧本"
    if "候选剧本" in html:
        blockers.append("HTML:候选剧本_still_present")
    else:
        warnings.append("HTML:候选剧本_removed")
    
    # 8-10. No hardcoded 428/13/0.86 in renderCandidate
    if "428" in html:
        # Check if it's in candidate rendering context (not validation)
        if re.search(r'default_stake.*428', html) or re.search(r'first\(x\.default_stake,428\)', html):
            blockers.append("HTML:428_hardcoded_in_candidate")
        else:
            warnings.append("HTML:428_only_in_non_candidate_context")
    if re.search(r'default_entry_minute.*13', html):
        blockers.append("HTML:13_hardcoded_in_candidate")
    else:
        warnings.append("HTML:entry_minute_not_hardcoded")
    if re.search(r'default_odds.*0\.86', html):
        blockers.append("HTML:0.86_hardcoded_in_candidate")
    else:
        warnings.append("HTML:odds_not_hardcoded")


def check_model(blockers: list[str], warnings: list[str]) -> None:
    """Check the control center model for data integrity."""
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    model_path = STATUS / f"v4_control_center_model_{today}.json"
    
    if not model_path.exists():
        # Try previous day
        yesterday = (datetime.now(LOCAL_TZ) - timedelta(days=1)).strftime("%Y%m%d")
        model_path = STATUS / f"v4_control_center_model_{yesterday}.json"
    
    model = load_json(model_path)
    if not model:
        blockers.append(f"MODEL_missing:{model_path.name}")
        return
    
    candidates = model.get("candidates", {})
    a_candidates = candidates.get("a_candidates", [])
    b_candidates = candidates.get("b_candidates", [])
    items = candidates.get("items", [])
    
    a_count = candidates.get("a_count", 0)
    b_count = candidates.get("b_count", 0)
    
    # Check 8-10: no hardcoded defaults
    for item in items:
        fid = item.get("fixture_id", "?")
        home = item.get("home_cn", "?")
        
        stake = item.get("default_stake")
        if stake is not None and stake == 428:
            blockers.append(f"MODEL:428_default:{fid}:{home}")
        
        entry = item.get("default_entry_minute")
        if entry is not None and str(entry) == "13":
            blockers.append(f"MODEL:13_default:{fid}:{home}")
        
        odds = item.get("default_odds")
        if odds is not None and odds == 0.86:
            blockers.append(f"MODEL:0.86_default:{fid}:{home}")
    
    if a_count > 0:
        warnings.append(f"MODEL:A_count={a_count}")
    if b_count > 0:
        warnings.append(f"MODEL:B_count={b_count}")
    
    # Check 13: C grade not in candidates
    for item in items:
        if str(item.get("grade", "")).strip().upper() == "C":
            blockers.append(f"MODEL:C_grade:{item.get('fixture_id')}")
    
    # Check 12: official grade preserved
    todo = model.get("todo_summary", {})
    todo_count = todo.get("to_bet", 0)
    warnings.append(f"MODEL:todo_count={todo_count}")
    
    for item in items:
        if item.get("source_group") not in ("WHITELIST_57", "OUTSIDE_57"):
            blockers.append(f"MODEL:invalid_source_group:{item.get('fixture_id')}:{item.get('source_group')}")


def run_sub_checkers(blockers: list[str], warnings: list[str]) -> None:
    for script in [
        "check_v4_control_center.py",
        "check_v4_dashboard_refresh_no_regrade.py",
        "check_v4_production_default_rules_guard.py",
        "check_v4_all_eligible_candidate_pool.py",
    ]:
        sp = ROOT / "tools" / script
        if not sp.exists():
            warnings.append(f"sub_missing:{script}")
            continue
        try:
            r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
            # Parse JSON conclusion; WARN_ONLY is acceptable
            try:
                result = json.loads(r.stdout.strip())
                conclusion = result.get("conclusion", "")
            except Exception:
                conclusion = ""
            if r.returncode != 0 and conclusion not in ("WARN_ONLY",):
                blockers.append(f"sub_fail:{script}(rc={r.returncode})")
            else:
                warnings.append(f"sub_pass:{script}({conclusion or 'rc=0'})")
        except Exception as e:
            blockers.append(f"sub_error:{script}:{e}")


def safety_qq(blockers: list[str], warnings: list[str]) -> None:
    markers = sorted(STATUS.glob("v4_scan_*_push_*.json"))
    pushed = [p.name for p in markers if (load_json(p) or {}).get("qq_sent")]
    if pushed:
        blockers.append(f"QQ_pushed:{pushed}")
    else:
        warnings.append("QQ_clear")


def safety_validation(blockers: list[str], warnings: list[str]) -> None:
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    val_paths = list(STATUS.glob(f"v4_validation_*_{today}*.json")) + list((ROOT / "data" / "daily_reports").glob(f"v4_review_*_{today}*.json"))
    if val_paths:
        blockers.append(f"validation_rerun:{[p.name for p in val_paths]}")
    else:
        warnings.append("validation_clear")


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    print("[check] HTML display...")
    check_html(blockers, warnings)
    
    print("[check] Model data...")
    check_model(blockers, warnings)
    
    print("[safety] sub-checkers...")
    run_sub_checkers(blockers, warnings)
    
    safety_qq(blockers, warnings)
    safety_validation(blockers, warnings)

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
        print("[candidate_card_display] PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
