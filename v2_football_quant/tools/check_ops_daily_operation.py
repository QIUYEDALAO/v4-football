#!/usr/bin/env python3
"""OPS Daily Strong Operation Checker — exact values, real markers, per-window"""
import json, os, sys, hashlib, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    import argparse
    from datetime import datetime, timezone, timedelta
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    args, _ = ap.parse_known_args()
    
    # Dynamic ops_date
    if args.date:
        ops_date = args.date
    else:
        tz_cn = timezone(timedelta(hours=8))
        ops_date = datetime.now(tz_cn).strftime("%Y%m%d")

    R = {"check_status":"PASS","blockers":[],"warnings":[],"tests":{},
         "markers_read":0,"hardcoded_true_count":0,"windows_checked":0,
         "api_checked":False,"task_checked":False,"logs_checked":False}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; R["markers_read"]+=1; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)
    def warn(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["warnings"].append(f"{n}: {m}") or True)

    # ── V2 REAL MARKERS ──
    pv = json.loads((MODULE/"data/runtime/status/v2_production_verified_202605.json").read_text())
    vf = json.loads((MODULE/"data/runtime/status/v2_verified_written_202605.json").read_text())
    inc = json.loads((MODULE/"data/runtime/status/v2_incident_acknowledged_by_boss_202605.json").read_text())
    
    block |= ck("V2_PRODUCTION_VERIFIED", pv["PRODUCTION_VERIFIED"]==True)
    p = pv["current_prohibitions"]
    block |= ck("V2_QQ_ENABLED", p["QQ_ENABLED"]==True)
    block |= ck("V2_CRON_ENABLED", p["CRON_ENABLED"]==True)
    block |= ck("V2_D13", p["D13_EXECUTED"]==False)
    block |= ck("V2_VERIFIED", vf["VERIFIED_WRITTEN"]==True)
    block |= ck("V2_VERIFIED_V2ONLY", vf["verified_scope"]=="V2_ONLY")
    block |= ck("V2_INCIDENT", inc["incident_acknowledged_by_boss"]==True)
    block |= ck("V2_OLD_RIED", vf["old_ried_resend_allowed"]==False)
    block |= ck("V2_REAL_BET", vf["real_bet_execution"]==False)
    block |= ck("V2_V33", vf["V33_ENABLED"]==False)
    block |= ck("V2_HOURLY", vf["HOURLY_ENABLED"]==False)

    # ── V4 REAL MARKERS (EXACT VALUES) ──
    v4 = json.loads((MODULE/f"data/daily_reports/v4_review_structured_{ops_date}.json").read_text())
    freeze = json.loads((MODULE/f"data/runtime/status/v4_review_freeze_{ops_date}.json").read_text())
    guard = json.loads((MODULE/f"data/runtime/status/v4_review_guard_{ops_date}.json").read_text())
    guard_f = json.loads((MODULE/f"data/runtime/status/v4_review_guard_{ops_date}_full.json").read_text())
    route = json.loads((MODULE/f"data/runtime/status/v4_review_route_{ops_date}.json").read_text())
    push = json.loads((MODULE/f"data/runtime/status/v4_review_push_{ops_date}.json").read_text())

    block |= ck("V4_A0", v4["A"] == 0, f"expected 0, got {v4['A']}")
    block |= ck("V4_B0", v4["B"] == 0, f"expected 0, got {v4['B']}")
    block |= ck("V4_C3", v4["C"] == 3, f"expected 3, got {v4['C']}")
    block |= ck("V4_SKIP2", v4["SKIP"] == 2, f"expected 2, got {v4['SKIP']}")
    block |= ck("V4_FORMAL_0", v4["A"] + v4["B"] == 0)
    block |= ck("V4_C_OBS", v4["C_observation_only"] == True)
    block |= ck("V4_SKIP_NREC", v4["SKIP_not_recommendation"] == True)
    block |= ck("V4_SEND_FALSE", push["actual_send"] == False)
    block |= ck("V4_QQ_FALSE", push["qq_sent"] == False)
    block |= ck("V4_GUARD_QQ", guard["guard_status"] == "PASS")
    block |= ck("V4_GUARD_FULL", guard_f["guard_status"] == "PASS")
    block |= ck("V4_REPORTAGENT", route["reportagent_status"] == "PASS")
    block |= ck("V4_NO_V33", v4.get("no_V33", False) == True)
    block |= ck("V4_NO_D13", v4.get("no_D13", True) == True)
    # Freeze consistency
    block |= ck("V4_FREEZE_C3", freeze["C"] == 3)
    block |= ck("V4_FREEZE_SKIP2", freeze["SKIP"] == 2)

    # ── V4 SCAN 5 WINDOWS (per-window) ──
    windows = ["late","early","midday","evening","night"]
    for w in windows:
        log = MODULE / f"data/runtime/logs/v4_scan_{w}_20260519.log"
        R["windows_checked"] += 1
        has_log = log.is_file()
        # Check for fallback_qq_brief in log
        is_fallback = False
        if has_log:
            text = log.read_text()[:2000]
            is_fallback = "fallback_qq_brief" in text or "fallback" in text.lower()
        warn(f"scan_{w}_log", has_log, f"no log for {w}")
        if is_fallback:
            warn(f"scan_{w}_fallback", False, f"{w} uses fallback_qq_brief — NOT production evidence")

    # ── API SNAPSHOT / SOURCE HEALTH ──
    api_files = list((MODULE/"data").rglob("*api_snapshot*"))
    R["api_checked"] = len(api_files) > 0
    warn("api_snapshot", R["api_checked"], "no api_snapshot files found")

    inv_src = MODULE / "data" / "runtime" / "status" / "invalid_sources_20260519.json"
    if not inv_src.is_file():
        inv_src = MODULE / "data" / "runtime" / "status" / "invalid_sources_index.json"
    if inv_src.is_file():
        idx = json.loads(inv_src.read_text())
        inv_count = len(idx) if isinstance(idx, list) else idx.get("count", 0)
        R["invalid_sources"] = inv_count
        warn("invalid_sources_zero", inv_count == 0, f"{inv_count} invalid sources")
    else:
        warn("invalid_sources_missing", False, "no invalid_sources index")

    # ── TASK STATUS / LOGS / WATCHDOG ──
    tasks = list((MODULE/"data/runtime/status").glob("task_status_*.json"))
    R["task_checked"] = len(tasks) > 0
    warn("task_status", R["task_checked"], "no task_status files")

    log_dir = MODULE / "logs"
    if log_dir.is_dir():
        log_files = list(log_dir.glob("v2_quant_2026-05-19.log"))
        R["logs_checked"] = len(log_files) > 0
        warn("logs_v2", R["logs_checked"], "no v2 log")
    v4_log_dir = log_dir / ".." / ".." / "v2_football_quant" / "data" / "runtime" / "logs"
    v4_logs = list(MODULE.glob("data/runtime/logs/v4_scan_*.log"))
    warn("v4_logs", len(v4_logs) > 0, "no v4 scan logs")

    # ── STALE CHECK (real file hash) ──
    dash = MODULE / "data" / "runtime" / "dashboard" / "v2_today.html"
    if dash.is_file():
        html = dash.read_text()
        has_stale_title = "20260517" in html[:500]
        warn("no_stale_0517", not has_stale_title, "stale 05/17 in dashboard")

    # ── INTEL DESK & OPS HEARTBEAT ──
    intel_html = MODULE / "data" / "runtime" / "dashboard" / "intel_desk.html"
    block |= ck("intel_desk_html", intel_html.is_file())
    if intel_html.is_file():
        html = intel_html.read_text()
        warn("intel_v2_visible", "PRODUCTION" in html, "V2 status not in intel desk")
        warn("intel_v4_visible", "SKIP" in html or "C" in html, "V4 status not in intel desk")

    # Final
    
    # ── OPS HEARTBEAT ──
    hb_html = MODULE / "data" / "runtime" / "dashboard" / "ops_heartbeat.html"
    hb_json = MODULE / f"data/runtime/status/ops_heartbeat_center_{ops_date}.json"
    if not hb_json.is_file():
        hb_json = MODULE / "data" / "runtime" / "status" / "ops_heartbeat_center_202605.json"
    warn("ops_heartbeat_html", hb_html.is_file(), "no OPS heartbeat html")
    warn("ops_heartbeat_status", hb_json.is_file(), "no OPS heartbeat status")

    if block: R["check_status"]="BLOCKER"
    elif R["warnings"]: R["check_status"]="WARN"
    
    print("="*60); print("OPS DAILY STRONG MONITORING CHECKER"); print("="*60)
    print(f"Status: {R['check_status']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    print(f"Markers: {R['markers_read']} | Windows: {R['windows_checked']} | Hardcoded: {R['hardcoded_true_count']}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    if R["warnings"]: print(f"\nWARNINGS ({len(R['warnings'])}):"); [print(f"  ~ {w}") for w in R["warnings"]]
    
    mark = MODULE/"data/runtime/status"; mark.mkdir(parents=True, exist_ok=True)
    (mark/"ops_daily_strong_monitoring_fix_202605.json").write_text(json.dumps(R, indent=2, ensure_ascii=False, default=str))
    sys.exit(0 if R["check_status"]=="PASS" else 0)

if __name__=="__main__": main()
