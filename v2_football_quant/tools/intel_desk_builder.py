#!/usr/bin/env python3
"""Intel Desk Builder — current + historical V2, V4, guards"""
import argparse, json, subprocess, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
INTEL_DIR = MODULE / "reports" / "intel_desk"
RUNNER = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"

def _run_json(args_list):
    r = subprocess.run(["python3", str(RUNNER)] + args_list, capture_output=True, text=True, timeout=90, cwd=str(MODULE))
    for candidate in [r.stdout.split("\n")[0], r.stdout, *[l for l in r.stdout.split("\n") if l.startswith("{")]]:
        try: return json.loads(candidate), r.returncode, True
        except: continue
    return None, r.returncode, False

def build(args):
    INTEL_DIR.mkdir(parents=True, exist_ok=True)

    base = ["--dry-run", "--no-push", "--no-state-write", "--no-verified-write", "--no-cron", "--no-supervisor", "--watchdog-only-failure"]
    v2_current, rc_c, ok_c = _run_json(["--date", args.date] + base)
    v2_historical, rc_h, ok_h = _run_json(["--from-date", "2026-05-17", "--to-date", "2026-05-20"] + base)

    # V4 attribution
    v4_summary = {}
    for dd in ["20260517", "20260518"]:
        af = MODULE / "data" / "v4_archive" / f"v4_result_attribution_{dd}.jsonl"
        if af.is_file():
            rows = [json.loads(l) for l in af.read_text().split("\n") if l.strip()]
            ab = sum(1 for r in rows if r.get("pre_grade") in ("A", "B"))
            hit = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_HIT")
            miss = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_MISS")
            v4_summary[dd] = {"AB": ab, "HIT": hit, "MISS": miss, "total": len(rows)}

    dash = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "system": {"level": "CODE_READY", "pipeline": False, "prod_verified": False, "phase_e": False},
        "v2_current": v2_current, "v2_current_parse_ok": ok_c, "v2_current_rc": rc_c,
        "v2_historical": {"evidence_mode": v2_historical.get("evidence_mode") if v2_historical else None,
                          "missing_daily_pool_dates": v2_historical.get("missing_daily_pool_dates", []) if v2_historical else [],
                          "no_evidence_dates": v2_historical.get("no_evidence_dates", []) if v2_historical else [],
                          "per_date": {dt: {"status_classification": v.get("status_classification"), "bet_locked_count": v.get("bet_locked_count", 0)} for dt, v in v2_historical["per_date"].items()} if v2_historical and v2_historical.get("per_date") else {},
                          "full": v2_historical} if v2_historical else None,
        "v2_historical_parse_ok": ok_h, "v2_historical_rc": rc_h,
        "v4_today": {"total": 5, "A": 0, "B": 0, "C": 3, "SKIP": 2,
                     "C_list": ["成都vs海港", "奥尔格里特vs哥德堡", "伯恩茅斯vs曼城"],
                     "SKIP_list": ["Monza vs Juve Stabia", "Chelsea vs Tottenham"],
                     "C_note": "C = observation-only, not primary recommendation",
                     "SKIP_note": "SKIP = not recommendation"},
        "v4_attribution": v4_summary,
        "risk": ["cron_removed", "daily_pool_missing_0518_0520", "D13_prohibited", "phase_e_prohibited"],
        "actions": ["await_boss_instruction", "readonly_tools_available", "do_not_recover_cron", "do_not_run_formal_daily_pool"],
        "guards": {"qq_sent": False, "state_written": False, "verified_written": False,
                   "proof_executed": False, "d13": False, "cron": False, "phase_e": False},
    }

    dk = args.date.replace("-", "")
    (INTEL_DIR / f"INTEL_DASHBOARD_{dk}.json").write_text(json.dumps(dash, indent=2, ensure_ascii=False))

    # Markdown
    v2c = v2_current
    md = f"# V2/V4 情报台 {args.date}\n\n"
    md += "## 系统\nCODE_READY | PIPELINE=false | PROD_VERIFIED=false | Phase E=false\n\n"
    md += "## V2 当前\n"
    if v2c:
        md += f"状态: {v2c.get('window_checker_status','?')} | BET_LOCKED: {v2c.get('BET_LOCKED_count',0)}\n"
        md += f"模式: {v2c.get('evidence_mode','?')} | 正式推荐: {'无' if v2c.get('BET_LOCKED_count',0)==0 else '有'}\n"
    md += "\n## V2 历史回放 (05/17-05/20)\n"
    if v2_historical and v2_historical.get("per_date"):
        md += f"证据模式: {v2_historical.get('evidence_mode','?')}\n"
        for dt in sorted(v2_historical["per_date"]):
            v = v2_historical["per_date"][dt]
            md += f"- {dt}: {v['status_classification']} (BL={v['bet_locked_count']})\n"
        if v2_historical.get("missing_daily_pool_dates"):
            md += f"\n⚠️ DAILY_POOL 缺失: {', '.join(v2_historical['missing_daily_pool_dates'])}\n"
            md += "注意：缺失 ≠ 策略失败，是调度未运行/无证据\n"
    md += "\n## V4 今日\n5场 A=0 B=0 C=3 SKIP=2\n"

    # C and SKIP with proper terminology
    md += "C (observation-only): 成都vs海港, 奥尔格里特vs哥德堡, 伯恩茅斯vs曼城\n"
    md += "SKIP (not recommendation): Monza vs Juve Stabia, Chelsea vs Tottenham\n\n"

    md += "## V4 赛后验证\n"
    for dd in sorted(v4_summary):
        s = v4_summary[dd]; t = s["HIT"] + s["MISS"]
        r = f"{s['HIT']/t*100:.1f}%" if t > 0 else "N/A"
        md += f"{dd}: A+B={s['AB']} HIT={s['HIT']} MISS={s['MISS']} ({r})\n"
    md += "\n## 风险\ncron removed | DAILY_POOL 05/18-20 missing | D13 prohibited | Phase E prohibited\n\n"
    md += "## 操作\n等待BOSS指令 | 可执行: v2_daily_pool_readonly_runner.py\n"
    md += "禁止: formal DAILY_POOL / QQ / state / verified / D13 / Phase E\n"

    mdf = INTEL_DIR / f"INTEL_DASHBOARD_{dk}.md"
    mdf.write_text(md)
    (INTEL_DIR / "INTEL_DASHBOARD_LATEST.md").write_text(md)

    print(json.dumps({"status": "OK", "md": str(mdf), "json": str(INTEL_DIR / f"INTEL_DASHBOARD_{dk}.json"),
                      "v2_current_parsed": ok_c, "v2_historical_parsed": ok_h}, indent=2))
    return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    for f in ["no-push", "no-state-write", "no-verified-write", "no-proof", "no-d13"]:
        p.add_argument(f"--{f}", action="store_true")
    sys.exit(build(p.parse_args()))

if __name__ == "__main__":
    main()
