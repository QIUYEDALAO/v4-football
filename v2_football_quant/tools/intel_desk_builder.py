#!/usr/bin/env python3
"""Intel Desk Local Builder — no QQ, no state, no verified"""
import argparse, json, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
INTEL_DIR = MODULE / "reports" / "intel_desk"
MANUAL_DIR = MODULE / "reports" / "manual_review"

def build(args):
    INTEL_DIR.mkdir(parents=True, exist_ok=True)

    # Gather V4 attribution summary
    v4_summary = {}
    for d in ["20260517", "20260518"]:
        af = MODULE / "data" / "v4_archive" / f"v4_result_attribution_{d}.jsonl"
        if af.is_file():
            rows = []
            for line in af.read_text().split("\n"):
                if line.strip():
                    rows.append(json.loads(line))
            ab = sum(1 for r in rows if r.get("pre_grade") in ("A","B"))
            hit = sum(1 for r in rows if r.get("pre_grade") in ("A","B") and r.get("model_result")=="MODEL_HIT")
            miss = sum(1 for r in rows if r.get("pre_grade") in ("A","B") and r.get("model_result")=="MODEL_MISS")
            v4_summary[d] = {"AB": ab, "HIT": hit, "MISS": miss, "total": len(rows)}

    # V2 window status
    v2_status = None
    wr = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"
    if wr.is_file():
        import subprocess
        r = subprocess.run(["python3", str(wr), "--date", args.date, "--dry-run", "--no-push",
            "--no-state-write", "--no-verified-write", "--no-cron", "--no-supervisor",
            "--watchdog-only-failure"], capture_output=True, text=True, timeout=60, cwd=str(MODULE))
        try:
            v2_status = json.loads(r.stdout.split("\n")[0])
        except: pass

    dash = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "system": {"level": "CODE_READY", "pipeline": False, "prod_verified": False, "phase_e": False},
        "v2": v2_status,
        "v4_today": {"total": 5, "A": 0, "B": 0, "C": 3, "SKIP": 2},
        "v4_attribution": v4_summary,
        "risk": ["cron_removed", "daily_pool_missing_0517_0520", "D13_prohibited", "phase_e_prohibited"],
        "actions": ["await_boss_instruction", "readonly_scan_tomorrow", "no_formal_daily_pool"],
        "guards": {"qq_sent": False, "state_written": False, "verified_written": False,
                   "proof_executed": False, "d13": False, "cron": False},
    }
    
    # Write JSON
    jf = INTEL_DIR / f"INTEL_DASHBOARD_{args.date.replace('-','')}.json"
    jf.write_text(json.dumps(dash, indent=2, ensure_ascii=False))
    
    # Write Markdown
    md = f"""# 📊 V2/V4 情报台 {args.date}

## 系统
CODE_READY | PIPELINE=false | PROD_VERIFIED=false | Phase E=false

## V2 DAILY_POOL
状态: {v2_status.get('window_checker_status','N/A') if v2_status else 'N/A'}
BET_LOCKED: {v2_status.get('BET_LOCKED_count',0) if v2_status else 0}
正式推荐: {'无' if not v2_status or v2_status.get('BET_LOCKED_count',0)==0 else '有'}

## V4 今日
5场 | A=0 B=0 C=3 SKIP=2
C: 成都vs海港 奥尔格里特vs哥德堡 伯恩茅斯vs曼城
SKIP: Monza vs Juve Chelsea vs Tottenham

## V4 赛后
"""
    for d in sorted(v4_summary.keys()):
        s = v4_summary[d]; tot = s.get("HIT",0) + s.get("MISS",0)
        rate = f"{s['HIT']/tot*100:.1f}%" if tot > 0 else "N/A"
        md += f"{d}: AB={s['AB']} HIT={s['HIT']} MISS={s['MISS']} ({rate})\n"
    
    md += """
## 风险
cron removed | DAILY_POOL 05/17-20 missing | D13 prohibited

## 操作
等待 BOSS | 可执行: tools/v2_daily_pool_readonly_runner.py
禁止: formal DAILY_POOL, QQ, state, verified, D13, Phase E
"""
    mdf = INTEL_DIR / f"INTEL_DASHBOARD_{args.date.replace('-','')}.md"
    mdf.write_text(md)
    latest = INTEL_DIR / "INTEL_DASHBOARD_LATEST.md"
    latest.write_text(md)
    
    print(json.dumps({"status": "OK", "md": str(mdf), "json": str(jf), "latest": str(latest)}, indent=2))
    return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--no-state-write", action="store_true")
    p.add_argument("--no-verified-write", action="store_true")
    p.add_argument("--no-proof", action="store_true")
    p.add_argument("--no-d13", action="store_true")
    sys.exit(build(p.parse_args()))

if __name__ == "__main__":
    main()
