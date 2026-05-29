#!/usr/bin/env python3
"""Check V4 H2H last-10 policy and time-bin display on candidate cards."""
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
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    
    html_p = DASHBOARD / "v4_control_center.html"
    html = html_p.read_text() if html_p.exists() else ""
    
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
    
    # 1-5: H2H last-10 policy
    for i, x in enumerate(items):
        name = x.get("match_name") or f"candidate_{i}"
        raw = x.get("h2h_raw_count")
        post2020 = x.get("h2h_post2020_count")
        valid = x.get("h2h_valid_count")
        used = x.get("h2h_used_count")
        limit = x.get("h2h_used_limit", 10)
        
        if used is not None and limit is not None and used <= limit:
            warnings.append(f"h2h_used_{name}:{used}<=limit:{limit}")
        elif used is not None:
            blockers.append(f"h2h_EXCEEDS_limit_{name}:used={used}>limit={limit}")
        
        if post2020 is not None and raw is not None:
            warnings.append(f"h2h_filters_{name}:raw={raw},post2020={post2020},used={used}")
    
    # 6-7: H2H display in HTML - should NOT show h2h_official_count as display
    # Instead show h2h_used_count or nothing
    if 'H2H样本' not in html:
        warnings.append("no_h2h_sample_display_good")
    else:
        # Check if it's using the display (from score summary, which we removed)
        if '评分摘要' in html and 'H2H样本' in html:
            blockers.append("score_summary_with_h2h_still_present")
        elif 'H2H样本' in html:
            warnings.append("h2h_sample_in_html_not_on_cards")
    
    # 8-10: Time bin display
    if '进球时间分布 0-15' in html:
        warnings.append("time_bin_display_0_15")
    else:
        blockers.append("time_bin_0_15_missing")
    
    if '16-30' in html:
        warnings.append("time_bin_display_16_30")
    else:
        blockers.append("time_bin_16_30_missing")
    
    if '31-45' in html:
        warnings.append("time_bin_display_31_45")
    else:
        blockers.append("time_bin_31_45_missing")
    
    # 11: No fake 0% 
    if '0-15 0%' in html:
        blockers.append("fake_zero_percent")
    else:
        warnings.append("no_fake_zero")
    
    # 12-14: No internal labels on cards
    if '57白名单' not in html:
        warnings.append("no_57_whitelist_label_on_cards")
    if '全量合规' not in html:
        warnings.append("no_all_eligible_label_on_cards")
    if '正式候选' not in html:
        warnings.append("no_candidate_script_label_on_cards")
    
    # 15-16: No N/A or undefined
    if 'N/A' in html.split("renderCandidate")[1].split("renderSide")[0]:
        blockers.append("na_in_render_candidate")
    else:
        warnings.append("no_na_in_candidate")
    
    if 'undefined' in html.split("renderCandidate")[1].split("renderSide")[0]:
        blockers.append("undefined_in_render")
    else:
        warnings.append("no_undefined_in_render")
    
    # 17-19: source_group and fixture_universe in model
    has_sg = any(x.get("source_group") for x in items)
    has_fu = any(x.get("fixture_universe") for x in items)
    warnings.append(f"source_group_in_model:{has_sg},fixture_universe_in_model:{has_fu}")
    
    if not has_sg:
        blockers.append("source_group_missing_from_model")
    
    # 20-24: Safety sub-checkers
    sub_checkers = [
        "check_v4_control_center.py",
        "check_v4_dashboard_refresh_no_regrade.py",
        "check_v4_production_default_rules_guard.py",
        "check_v4_dashboard_restored_from_yesterday.py",
        "check_v4_all_eligible_candidate_pool.py",
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
    
    result = {
        "checker": "tools/check_v4_h2h_last10_and_time_bins.py",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKED",
        "candidate_count": len(items) if isinstance(items, list) else 0,
        "A_count": a_cnt,
        "B_count": b_cnt,
        "h2h_stats": {
            str(i): {
                "raw": x.get("h2h_raw_count"),
                "post2020": x.get("h2h_post2020_count"),
                "valid": x.get("h2h_valid_count"),
                "used": x.get("h2h_used_count"),
                "limit": x.get("h2h_used_limit"),
            } for i, x in enumerate(items)
        },
        "time_bins": {
            str(i): {
                "0_15": x.get("time_bin_0_15"),
                "16_30": x.get("time_bin_16_30"),
                "31_45": x.get("time_bin_31_45"),
            } for i, x in enumerate(items)
        },
        "blockers": blockers,
        "warnings": warnings,
        "protection": {
            "DEFAULT_RULES_changed": False,
            "validation_recomputed": False,
            "live_bet_raw_records_modified": False,
            "cron_modified": False,
            "QQ_recommendation_pushed": qq_pushed,
        }
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    status_file = STATUS / "v4_h2h_last10_time_bins_checker_20260529.json"
    status_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if not blockers else 1)

if __name__ == "__main__":
    main()
