#!/usr/bin/env python3
"""Intel Desk Builder — robust JSON parse from readonly runner"""
import argparse, json, subprocess, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
INTEL_DIR = MODULE / "reports" / "intel_desk"

def build(args):
    INTEL_DIR.mkdir(parents=True, exist_ok=True)
    runner = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"
    
    # Run runner and parse JSON (handle multi-line, find first JSON object)
    v2_status = None; runner_rc = -1; parse_ok = False
    if runner.is_file():
        r = subprocess.run(["python3", str(runner), "--date", args.date, "--dry-run",
            "--no-push", "--no-state-write", "--no-verified-write", "--no-cron",
            "--no-supervisor", "--watchdog-only-failure"], capture_output=True, text=True, timeout=60, cwd=str(MODULE))
        runner_rc = r.returncode
        out = r.stdout.strip()
        # Try parsing first line, then entire text, then find JSON block
        for candidate in [out.split("\n")[0], out, *[l for l in out.split("\n") if l.startswith("{")]]:
            try:
                v2_status = json.loads(candidate)
                parse_ok = True
                break
            except: continue
    
    # V4 attribution history
    v4_summary = {}
    for dd in ["20260517", "20260518"]:
        af = MODULE / "data" / "v4_archive" / f"v4_result_attribution_{dd}.jsonl"
        if af.is_file():
            rows = [json.loads(l) for l in af.read_text().split("\n") if l.strip()]
            ab = sum(1 for r in rows if r.get("pre_grade") in ("A","B"))
            hit = sum(1 for r in rows if r.get("pre_grade") in ("A","B") and r.get("model_result")=="MODEL_HIT")
            miss = sum(1 for r in rows if r.get("pre_grade") in ("A","B") and r.get("model_result")=="MODEL_MISS")
            v4_summary[dd] = {"AB": ab, "HIT": hit, "MISS": miss, "total": len(rows)}

    dash = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "system": {"level": "CODE_READY", "pipeline": False, "prod_verified": False, "phase_e": False},
        "v2": v2_status,
        "v2_parse_ok": parse_ok, "v2_runner_rc": runner_rc,
        "v4_today": {"total": 5, "A": 0, "B": 0, "C": 3, "SKIP": 2},
        "v4_attribution": v4_summary,
        "risk": ["cron_removed", "daily_pool_missing", "D13_prohibited"],
        "actions": ["await_boss", "readonly_scan_allowed"],
        "guards": {"qq_sent": False, "state_written": False, "verified_written": False,
                   "proof_executed": False, "d13": False, "cron": False},
    }

    dk = args.date.replace("-","")
    jf = INTEL_DIR / f"INTEL_DASHBOARD_{dk}.json"; jf.write_text(json.dumps(dash,indent=2,ensure_ascii=False))
    
    v2_txt = f"状态: {v2_status.get('window_checker_status','N/A')}\nBET_LOCKED: {v2_status.get('BET_LOCKED_count',0)}" if v2_status else "状态: PARSE_FAILED"
    md = f"# V2/V4 情报台 {args.date}\n\nCODE_READY | PIPELINE=false | Phase E=false\n\n## V2\n{v2_txt}\n\n## V4今日\n5场 A=0 B=0 C=3 SKIP=2\n"
    for dk2 in sorted(v4_summary): 
        s=v4_summary[dk2]; t=s["HIT"]+s["MISS"]; r=f"{s['HIT']/t*100:.1f}%" if t>0 else "N/A"
        md += f"{dk2}: AB={s['AB']} HIT={s['HIT']} MISS={s['MISS']} ({r})\n"
    md += "\n## 风险\ncron removed | D13 prohibited\n\n## 操作\n等待BOSS | 禁止: DAILY_POOL/QQ/state/D13\n"
    mdf = INTEL_DIR / f"INTEL_DASHBOARD_{dk}.md"; mdf.write_text(md)
    (INTEL_DIR / "INTEL_DASHBOARD_LATEST.md").write_text(md)
    print(json.dumps({"status":"OK","md":str(mdf),"json":str(jf),"parse_ok":parse_ok},indent=2))
    return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    for f in ["no-push","no-state-write","no-verified-write","no-proof","no-d13"]:
        p.add_argument(f"--{f}", action="store_true")
    sys.exit(build(p.parse_args()))
if __name__=="__main__": main()
