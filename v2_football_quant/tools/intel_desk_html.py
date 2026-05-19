#!/usr/bin/env python3
"""Generate HTML intel dashboard — no-cache, mobile-first, reads intel desk JSON"""
import json, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
INTEL_DIR = MODULE / "reports" / "intel_desk"
DASH_DIR = MODULE / "data" / "runtime" / "dashboard"

def build_html(data, title="V2/V4 情报台"):
    gen = data.get("generated_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    v2c = data.get("v2_current", {}) or {}
    v2h = data.get("v2_historical") or {}
    v4t = data.get("v4_today", {}) or {}
    v4a = data.get("v4_attribution", {}) or {}
    guards = data.get("guards", {})
    risk = data.get("risk", [])
    actions = data.get("actions", [])
    ver = data.get("dashboard_version", "?")

    # V2 current
    v2_status = v2c.get("window_checker_status", "?")
    v2_bl = v2c.get("BET_LOCKED_count", 0)
    v2_bl_tag = "ok" if v2_bl > 0 else "neutral"

    # V2 historical rows
    hrows = ""
    per_date = v2h.get("per_date", {})
    for dt in sorted(per_date):
        v = per_date[dt]
        cls = v.get("status_classification", "?")
        tag = "ok" if cls == "DAILY_POOL_FOUND" else ("warn" if cls == "DAILY_POOL_MISSING" else "neutral")
        hrows += f'<tr><td>{dt}</td><td><span class="tag {tag}">{cls}</span></td><td>{v.get("bet_locked_count",0)}</td></tr>'

    missing = v2h.get("missing_daily_pool_dates", [])
    missing_txt = ", ".join(missing) if missing else "无"
    ev_mode = v2h.get("evidence_mode", "?")

    # V4 today
    v4_src = v4t.get("source_mode", "?")
    v4_fresh = v4t.get("source_freshness", "?")
    v4_a = v4t.get("A_count") if v4t.get("A_count") is not None else "?"
    v4_b = v4t.get("B_count") if v4t.get("B_count") is not None else "?"
    v4_c = v4t.get("C_count") if v4t.get("C_count") is not None else "?"
    v4_s = v4t.get("SKIP_count") if v4t.get("SKIP_count") is not None else "?"
    v4_total = v4t.get("total_matches") if v4t.get("total_matches") is not None else "?"
    v4_degraded = v4_src == "SOURCE_MISSING"
    v4_tag = "warn" if v4_degraded else "ok"

    # V4 attribution
    arows = ""
    for dd in sorted(v4a):
        s = v4a[dd]; t = s["HIT"] + s["MISS"]
        rate = f"{s['HIT']/t*100:.1f}%" if t > 0 else "N/A"
        arows += f'<tr><td>{dd[:4]}-{dd[4:6]}-{dd[6:]}</td><td>{s["AB"]}</td><td>{s["HIT"]}</td><td>{s["MISS"]}</td><td><b>{rate}</b></td></tr>'

    # Guards
    gitems = ""
    for k, v in guards.items():
        cls = "ok" if not v else "bad"
        gitems += f'<span class="tag {cls}">{k}: {v}</span> '

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="Cache-Control" content="no-store,no-cache,must-revalidate,max-age=0">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,system-ui,sans-serif;background:#0c1220;color:#e0e0e0;padding:12px;max-width:520px;margin:0 auto}}
h1{{font-size:18px;margin:8px 0 4px;color:#fff}}
h2{{font-size:15px;margin:16px 0 6px;color:#4fc3f7;border-bottom:1px solid #1a2a3a;padding-bottom:4px}}
.card{{background:#111a2a;border-radius:8px;padding:12px;margin:8px 0}}
.row{{display:flex;justify-content:space-between;padding:4px 0;font-size:14px}}
.label{{color:#8899aa}}.value{{color:#e0e0e0;font-weight:600}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;margin:2px}}
.tag.ok{{background:#1a3a1a;color:#4caf50}}.tag.bad{{background:#3a1a1a;color:#f44336}}
.tag.warn{{background:#3a3a1a;color:#ff9800}}.tag.neutral{{background:#1a2a3a;color:#8899aa}}
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:13px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #1a2a3a}}
th{{color:#8899aa;font-weight:500}}td{{color:#e0e0e0}}
.meta{{font-size:11px;color:#556;margin:8px 0}}
.guards{{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0}}
.footer{{text-align:center;margin:20px 0;font-size:11px;color:#445}}
.degraded{{background:#3a2a1a;padding:8px;border-radius:4px;color:#ff9800;font-size:13px;margin:8px 0}}
</style>
</head>
<body>
<h1>📊 V2/V4 情报台</h1>
<div class="meta">版本: {ver} · 生成: {gen} · 源日期: {data.get("date","?")}</div>

<h2>🖥️ 系统</h2>
<div class="card">
<div class="row"><span class="label">CODE_READY</span><span class="value">PIPELINE=false · PROD_VERIFIED=false</span></div>
<div class="row"><span class="label">Phase E</span><span class="value">false</span></div>
<div class="guards">{gitems}</div>
</div>

<h2>📈 V2 当前</h2>
<div class="card">
<div class="row"><span class="label">窗口状态</span><span class="value">{v2_status}</span></div>
<div class="row"><span class="label">BET_LOCKED</span><span class="value"><span class="tag {v2_bl_tag}">{v2_bl}</span></span></div>
<div class="row"><span class="label">正式推荐</span><span class="value">{'有' if v2_bl > 0 else '无'}</span></div>
</div>

<h2>📋 V2 历史回放</h2>
<div class="card">
<div class="meta">证据模式: {ev_mode} · 缺失: {missing_txt}</div>
<table>
<tr><th>日期</th><th>状态</th><th>BL</th></tr>
{hrows}
</table>
<div class="meta">⚠️ 缺失=调度未运行，非策略失败</div>
</div>

<h2>⚽ V4 今日</h2>
<div class="card">
<div class="row"><span class="label">总计</span><span class="value">{v4_total}场</span></div>
<div class="row"><span class="label">A</span><span class="value"><span class="tag ok">{v4_a}</span></span></div>
<div class="row"><span class="label">B</span><span class="value"><span class="tag ok">{v4_b}</span></span></div>
<div class="row"><span class="label">C</span><span class="value"><span class="tag warn">{v4_c}</span> (observation-only)</span></div>
<div class="row"><span class="label">SKIP</span><span class="value"><span class="tag neutral">{v4_s}</span> (not recommendation)</span></div>
<div class="meta">源: {v4_src} · 新鲜度: {v4_fresh}</div>
</div>
{('<div class="degraded">⚠️ V4 今日源缺失，不使用硬编码快照</div>' if v4_degraded else '')}

<h2>📊 V4 赛后验证</h2>
<div class="card">
<table>
<tr><th>日期</th><th>A+B</th><th>HIT</th><th>MISS</th><th>命中率</th></tr>
{arows}
</table>
</div>

<h2>⚠️ 风险</h2>
<div class="card">
{' '.join(f'<span class="tag warn">{r}</span>' for r in risk)}
</div>

<h2>🔧 操作</h2>
<div class="card">
{' '.join(f'<span class="tag neutral">{a}</span>' for a in actions)}
</div>

<div class="footer">V2/V4 情报台 · 只读 · 不推QQ · 不写state · crontool removed · D13 prohibited · Phase E prohibited</div>
</body></html>'''
    return html


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--json", default="")
    p.add_argument("--date", default=time.strftime("%Y%m%d"))
    p.add_argument("--no-push", action="store_true")
    args = p.parse_args()

    # Find latest JSON
    jf = Path(args.json) if args.json else (INTEL_DIR / f"INTEL_DASHBOARD_{args.date}.json")
    if not jf.is_file():
        jsons = sorted(INTEL_DIR.glob("INTEL_DASHBOARD_20*.json"), reverse=True)
        if jsons:
            jf = jsons[0]
        else:
            print("ERROR: no dashboard JSON found", file=sys.stderr)
            sys.exit(1)

    data = json.loads(jf.read_text())
    html = build_html(data)

    # Write to output locations
    latest_html = INTEL_DIR / "INTEL_DASHBOARD_LATEST.html"
    latest_html.write_text(html)

    # Also write to dashboard server directory
    DASH_DIR.mkdir(parents=True, exist_ok=True)
    vt = DASH_DIR / "v2_today.html"
    vt.write_text(html)

    # Also write index.html
    idx = DASH_DIR / "index.html"
    idx.write_text(html)

    print(json.dumps({
        "status": "OK",
        "v2_today_html": str(vt),
        "latest_html": str(latest_html),
        "index_html": str(idx),
        "source_json": str(jf),
        "generated_at": data.get("generated_at", "?"),
        "dashboard_version": data.get("dashboard_version", "?")
    }, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
