#!/usr/bin/env python3
"""Intel Desk Builder — dynamic dates, rolling attribution"""
import argparse, json, subprocess, sys, time
from datetime import date
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
INTEL_DIR = MODULE / "reports" / "intel_desk"
RUNNER = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"


def _run_json(args_list):
    r = subprocess.run(["python3", str(RUNNER)] + args_list, capture_output=True, text=True, timeout=90, cwd=str(MODULE))
    for c in [r.stdout.split("\n")[0], r.stdout, *[l for l in r.stdout.split("\n") if l.startswith("{")]]:
        try:
            return json.loads(c), r.returncode, True
        except:
            continue
    return None, r.returncode, False


def build(args):
    INTEL_DIR.mkdir(parents=True, exist_ok=True)
    dk = (date.fromisoformat(args.output_date[:10].replace("/", "-"))
          if args.output_date else date.fromisoformat(args.date[:10].replace("/", "-"))).strftime("%Y%m%d")

    base = ["--dry-run", "--no-push", "--no-state-write", "--no-verified-write", "--no-cron", "--no-supervisor", "--watchdog-only-failure"]
    v2_current, rc_c, ok_c = _run_json(["--date", args.date] + base)
    v2_historical, rc_h, ok_h = _run_json(["--from-date", args.history_from, "--to-date", args.history_to] + base)

    # V4 attribution (dynamic)
    v4_summary = {}
    archive_dir = MODULE / "data" / "v4_archive"
    if archive_dir.is_dir():
        for af in sorted(archive_dir.glob("v4_result_attribution_*.jsonl"), reverse=True):
            fn = af.name
            dd = fn.replace("v4_result_attribution_", "").replace(".jsonl", "")
            if not dd.isdigit() or len(dd) != 8:
                continue
            try:
                fd = date(int(dd[:4]), int(dd[4:6]), int(dd[6:8]))
            except:
                continue
            args_dt = date.fromisoformat(args.date[:10].replace("/", "-"))
            if fd > args_dt or (args_dt - fd).days >= args.v4_attribution_days:
                continue
            rows = [json.loads(l) for l in af.read_text().split("\n") if l.strip()]
            ab = sum(1 for r in rows if r.get("pre_grade") in ("A", "B"))
            hit = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_HIT")
            miss = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_MISS")
            v4_summary[dd] = {"AB": ab, "HIT": hit, "MISS": miss, "total": len(rows)}

    
    # Resolve V4 today source (dynamic, no hardcoding)
    v4_resolver = MODULE / "tools" / "v4_today_source_resolver.py"
    v4_data = None
    if v4_resolver.is_file():
        r = subprocess.run(["python3", str(v4_resolver), "--date", args.date,
                            "--no-push", "--no-state-write", "--no-verified-write"],
                           capture_output=True, text=True, timeout=30, cwd=str(MODULE))
        try:
            v4_data = json.loads(r.stdout.strip().split("\n")[0])
        except:
            pass

    dash = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "dashboard_version": "INTEL_OPS_1_1",
        "source_freshness": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "system": {"level": "CODE_READY", "pipeline": False, "prod_verified": False, "phase_e": False},
        "date": args.date, "history_from": args.history_from, "history_to": args.history_to,
        "v4_attribution_days": args.v4_attribution_days,
        "attribution_dates": sorted(v4_summary.keys()),
        "v2_current": v2_current, "v2_current_parse_ok": ok_c, "v2_current_rc": rc_c,
        "v2_historical": {
            "evidence_mode": v2_historical.get("evidence_mode") if v2_historical else None,
            "missing_daily_pool_dates": v2_historical.get("missing_daily_pool_dates", []) if v2_historical else [],
            "no_evidence_dates": v2_historical.get("no_evidence_dates", []) if v2_historical else [],
            "per_date": {dt: {"status_classification": v.get("status_classification"),
                              "bet_locked_count": v.get("bet_locked_count", 0)}
                         for dt, v in v2_historical["per_date"].items()}
            if v2_historical and v2_historical.get("per_date") else {},
        } if v2_historical else None,
        "v2_historical_parse_ok": ok_h, "v2_historical_rc": rc_h,
        "v4_today": v4_data or {"source_mode": "SOURCE_MISSING", "hardcoded": False,
                     "source_freshness": "MISSING", "C_observation_only": True,
                     "SKIP_not_recommendation": True},
        "v4_attribution": v4_summary,
        "risk": ["cron_removed", "D13_prohibited", "phase_e_prohibited"],
        "actions": ["await_boss", "readonly_only", "no_formal_daily_pool", "no_cron_recovery"],
        "guards": {"qq_sent": False, "state_written": False, "verified_written": False,
                   "proof_executed": False, "d13": False, "cron": False, "phase_e": False},
    }

    # Write JSON
    jf = INTEL_DIR / f"INTEL_DASHBOARD_{dk}.json"
    jf.write_text(json.dumps(dash, indent=2, ensure_ascii=False))

    # Write Markdown
    v2c = v2_current
    md = f"# V2/V4 情报台 {args.date}\n\n"
    md += "## 系统\nCODE_READY | PIPELINE=false | Phase E=false | v1.1\n\n"
    md += "## V2 当前\n"
    if v2c:
        md += f"状态: {v2c.get('window_checker_status','?')} | BET_LOCKED: {v2c.get('BET_LOCKED_count',0)}\n"
        md += f"正式推荐: {'无' if v2c.get('BET_LOCKED_count',0)==0 else '有'}\n"
    md += f"\n## V2 历史回放 ({args.history_from}~{args.history_to})\n"
    if v2_historical and v2_historical.get("per_date"):
        for dt_key in sorted(v2_historical["per_date"]):
            v = v2_historical["per_date"][dt_key]
            md += f"- {dt_key}: {v['status_classification']} (BL={v['bet_locked_count']})\n"
        md_dates = v2_historical.get("missing_daily_pool_dates", [])
        if md_dates:
            md += f"\n⚠️ DAILY_POOL 缺失: {', '.join(md_dates)} [调度未运行，非策略失败]\n"
    # V4 today from resolver (dynamic, no hardcoded)
    if v4_data and v4_data.get("source_mode") != "SOURCE_MISSING":
        t, a, b, c, s = v4_data.get("total_matches"), v4_data.get("A_count"), v4_data.get("B_count"), v4_data.get("C_count"), v4_data.get("SKIP_count")
        md += f"\n## V4 今日\n总: {t if t is not None else '?'} | A={a if a is not None else '?'} B={b if b is not None else '?'} C={c if c is not None else '?'} SKIP={s if s is not None else '?'}\n"
        md += f"源: {v4_data.get('source_mode','?')} | 新鲜度: {v4_data.get('source_freshness','?')}\n"
        md += "C (observation-only) | SKIP (not recommendation)\n\n"
    else:
        md += "\n## V4 今日\n源缺失 (不使用硬编码快照)\nC (observation-only) | SKIP (not recommendation)\n\n"

    if v4_summary:
        md += f"## V4 赛后验证 (最近{args.v4_attribution_days}天)\n"
        for dd in sorted(v4_summary):
            s = v4_summary[dd]; t = s["HIT"] + s["MISS"]
            r = f"{s['HIT']/t*100:.1f}%" if t > 0 else "N/A"
            md += f"{dd[:4]}-{dd[4:6]}-{dd[6:]}: A+B={s['AB']} HIT={s['HIT']} MISS={s['MISS']} ({r})\n"

    md += "\n## 风险\ncron removed | D13/Phase E prohibited\n\n"
    md += "## 操作\nawait BOSS | 只读扫描 | 禁止 formal DAILY_POOL / QQ / cron 恢复\n"

    mdf = INTEL_DIR / f"INTEL_DASHBOARD_{dk}.md"
    mdf.write_text(md)
    latest = INTEL_DIR / "INTEL_DASHBOARD_LATEST.md"
    latest.write_text(md)

    print(json.dumps({"status": "OK", "md": str(mdf), "json": str(jf),
                      "latest": str(latest), "v2_current_parsed": ok_c,
                      "v2_historical_parsed": ok_h, "attribution_dates": sorted(v4_summary.keys())},
                     indent=2, ensure_ascii=False))
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    p.add_argument("--output-date", default="")
    p.add_argument("--history-from", required=True)
    p.add_argument("--history-to", required=True)
    p.add_argument("--v4-attribution-days", type=int, default=3)
    for f in ["no-push", "no-state-write", "no-verified-write", "no-proof", "no-d13"]:
        p.add_argument(f"--{f}", action="store_true")
    sys.exit(build(p.parse_args()))

if __name__ == "__main__":
    main()
