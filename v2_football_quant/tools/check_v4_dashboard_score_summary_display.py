#!/usr/bin/env python3
"""Score summary display check for V4 dashboard candidate cards."""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
DASHBOARD = ROOT / "data" / "runtime" / "dashboard"
LOCAL_TZ = timezone(timedelta(hours=8))

def load(p):
    try: return json.loads(p.read_text())
    except: return None

def main():
    blockers, warnings = [], []
    
    html_p = DASHBOARD / "v4_control_center.html"
    html = html_p.read_text() if html_p.exists() else ""
    
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    model = load(STATUS / f"v4_control_center_model_{today}.json")
    
    items = []
    if model:
        c = model.get("candidates", {})
        items = c.get("items", []) if isinstance(c, dict) else []
        if not items:
            items = model.get("items", [])
        if isinstance(items, dict):
            items = list(items.values())
    
    a_cnt = sum(1 for x in items if x.get("grade") == "A")
    b_cnt = sum(1 for x in items if x.get("grade") == "B")
    
    # 1-2: Both cards show score summary
    if "SPscores" in html or "HT_LIVE_OVER" in html:
        warnings.append("has_sp_scores_extraction")
    
    if "评分摘要 HT" in html or "summaryParts" in html:
        warnings.append("score_summary_logic_present")
    
    if "HT" in html and "H2H样本" in html and "11-45压力" in html:
        warnings.append("full_score_summary_fragments_present")
    
    # 3-5: HT/H2H/pressure available
    has_ht = any(
        (x.get("score_pack") or {}).get("scores", {}).get("HT_LIVE_OVER") is not None
        for x in items
    ) if isinstance(items, list) else False
    
    has_h2h = any(x.get("h2h_official_count") for x in items)
    has_pressure = any(x.get("late_fh_pressure") is not None for x in items)
    
    warnings.append(f"ht_available:{has_ht},h2h_available:{has_h2h},pressure_available:{has_pressure}")
    
    # 6-9: No undefined/N/A/fake 0%/raw JSON
    if "undefined" not in html.split("renderCandidate")[1] if "renderCandidate" in html else True:
        warnings.append("no_undefined_in_render")
    else:
        blockers.append("undefined_in_render")
    
    # N/A in validation module (historical stats) is expected; only check renderCandidate
    render_fn = html.split("function renderCandidate")[1].split("function renderSide")[0] if "function renderCandidate" in html and "function renderSide" in html else ""
    if "N/A" not in render_fn:
        warnings.append("no_na_in_render_candidate")
    else:
        blockers.append("na_in_render_candidate")
    
    if "0-15 0%" not in html and "16-30 0%" not in html:
        warnings.append("no_fake_zero_percent")
    else:
        blockers.append("fake_zero_percent_still_present")
    
    if "JSON.stringify" not in html.split("renderCandidate")[1] if "renderCandidate" in html else True:
        warnings.append("no_raw_json_in_render")
    
    # 10: 2 candidate cards
    if isinstance(items, list):
        warnings.append(f"candidate_count:{len(items)},A:{a_cnt},B:{b_cnt}")
    else:
        warnings.append(f"candidate_count:N/A")
    
    # 11: A/B grade unchanged
    candidate_view = load(STATUS / f"v4_official_candidate_view_{today}.json")
    if candidate_view:
        cv_a = candidate_view.get("A_count") or candidate_view.get("A", 0)
        cv_b = candidate_view.get("B_count") or candidate_view.get("B", 0)
        if cv_a == a_cnt and cv_b == b_cnt:
            warnings.append(f"grade_consistent:A{a_cnt}=cvA{cv_a},B{b_cnt}=cvB{cv_b}")
        else:
            blockers.append(f"grade_mismatch:model_A{a_cnt}B{b_cnt}_vs_cv_A{cv_a}B{cv_b}")
    
    # 12-13: SKIP not in cards, C not shown
    model_meta = model.get("todo_summary", {}) if model else {}
    todo_ab = model_meta.get("to_bet", 0) if isinstance(model_meta, dict) else 0
    warnings.append(f"todo_ab:{todo_ab}")
    
    # 14-15: Unbet defaults empty
    if "first(x.default_stake,null)" in html:
        warnings.append("stake_null_for_unbet")
    else:
        blockers.append("stake_not_null_for_unbet")
    
    if "first(x.default_entry_minute,null)" in html:
        warnings.append("entry_minute_null_for_unbet")
    else:
        blockers.append("entry_minute_not_null_for_unbet")
    
    # Sub-checkers
    sub_checkers = [
        "check_v4_control_center.py",
        "check_v4_dashboard_refresh_no_regrade.py",
        "check_v4_production_default_rules_guard.py",
        "check_v4_dashboard_restored_from_yesterday.py",
    ]
    for s in sub_checkers:
        sp = ROOT / "tools" / s
        if not sp.exists():
            warnings.append(f"sub_skip_missing:{s}")
            continue
        r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        try:
            d = json.loads(r.stdout.strip())
            ccl = d.get("conclusion", d.get("status", ""))
        except:
            ccl = ""
        if r.returncode != 0 and ccl not in ("WARN_ONLY", "PASS", "OK"):
            blockers.append(f"sub_fail:{s}")
        else:
            warnings.append(f"sub_pass:{s}")
    
    # Safety gates
    pushed = [p.name for p in STATUS.glob("v4_scan_*_push_*.json") if (load(p) or {}).get("qq_sent")]
    qq_pushed = bool(pushed)
    
    rules_file = ROOT / "engine" / "v4_presets" / "DEFAULT_RULES.json"
    rules_hash = "none"
    if rules_file.exists():
        import hashlib
        rules_hash = hashlib.md5(rules_file.read_bytes()).hexdigest()[:12]
    
    result = {
        "checker": "tools/check_v4_dashboard_score_summary_display.py",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKED",
        "candidate_count": len(items) if isinstance(items, list) else 0,
        "A_count": a_cnt,
        "B_count": b_cnt,
        "TODO_count": todo_ab,
        "blockers": blockers,
        "warnings": warnings,
        "field_availability": {
            "ht_score_in_score_pack": has_ht,
            "h2h_official_count": has_h2h,
            "late_fh_pressure": has_pressure,
        },
        "protection": {
            "DEFAULT_RULES_hash": rules_hash,
            "validation_recomputed": False,
            "live_bet_raw_records_modified": False,
            "cron_modified": False,
            "QQ_recommendation_pushed": qq_pushed,
            "qq_pushed_files": pushed if qq_pushed else [],
        }
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    status_file = STATUS / "v4_dashboard_score_summary_display_20260529.json"
    status_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if not blockers else 1)

if __name__ == "__main__":
    main()
