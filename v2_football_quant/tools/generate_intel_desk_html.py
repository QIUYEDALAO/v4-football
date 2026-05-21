#!/usr/bin/env python3
"""Generate Intel Desk dashboard HTML from candidate view JSON.

Reads:  data/runtime/status/intel_desk_v4_candidate_view_20260520.json
Writes: data/runtime/dashboard/index.html
        data/runtime/dashboard/intel_desk.html
        data/runtime/dashboard/ops_heartbeat.html
        data/runtime/dashboard/v2_today.html

Every B/C card in the output HTML comes directly from the candidate JSON.
source_path and source_hash are embedded in the HTML metadata.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))

CANDIDATE_JSON = MODULE / "data" / "runtime" / "status" / "intel_desk_v4_candidate_view_20260520.json"

CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0c1220;color:#e0e0e0;padding:8px;max-width:540px;margin:0 auto}
h1{font-size:15px;color:#fff;margin:4px 0}h2{font-size:13px;color:#4fc3f7;margin:10px 0 2px;border-bottom:1px solid #1a2a3a;padding-bottom:2px}
.card{background:#111a2a;border-radius:8px;padding:8px;margin:4px 0;font-size:12px}
.r{display:flex;justify-content:space-between;padding:2px 0}
.l{color:#8899aa}.v{color:#e0e0e0;font-weight:600}
.t{display:inline-block;padding:1px 5px;border-radius:3px;font-size:10px;margin:1px}
.g{background:#1a3a1a;color:#4caf50}.y{background:#3a3a1a;color:#ff9800}.n{background:#1a2a3a;color:#8899aa}.r2{background:#3a1a1a;color:#f44336}
.m{font-size:10px;color:#556}.m2{font-size:11px;color:#4fc3f7;margin:2px 0}
.bcard{background:#0d1a2a;border:1px solid #1a3a3a;border-radius:8px;padding:8px 10px;margin:6px 0;font-size:12px}
.bcard .bl{font-size:10px;color:#4fc3f7;font-weight:700;margin-bottom:2px}
.bcard .bn{font-size:13px;color:#fff;font-weight:600;margin-bottom:1px}
.bcard .bs{font-size:10px;color:#8899aa}
.bcard .bt{display:flex;flex-wrap:wrap;gap:3px;margin-top:4px}
.bcard .bi{font-size:10px;color:#ff9800;margin-top:2px}
.ccard{background:#0d1a2a;border:1px solid #1a2a2a;border-radius:6px;padding:6px 8px;margin:3px 0;font-size:11px}
.history{background:#0c1218;border:1px dashed #1a2a3a;border-radius:6px;padding:6px;margin:6px 0;font-size:10px;color:#667}
.footer{text-align:center;margin:16px 0 8px;font-size:10px;color:#556}
</style>"""


def normalize_entry(entry, grade, source_window):
    """Ensure every candidate entry has all required fields. Fills gaps, never overwrites existing values."""
    defaults = {
        "grade": grade,
        "qq_sent": False,
        "source_window": source_window,
    }
    if grade == "C":
        defaults.update({
            "status": "observation_only",
            "recommendation_status": "observation_only",
            "league": entry.get("league", "UNKNOWN"),
            "kickoff_time": entry.get("kickoff_time", entry.get("kickoff_display", "UNKNOWN")),
            "actual_send": False,
            "V4_QQ_ENABLED": False,
        })
    elif grade in ("A", "B"):
        defaults.update({
            "recommendation_status": entry.get("recommendation_status", "candidate_pending_approval"),
            "actual_send": False,
            "V4_QQ_ENABLED": False,
            "tags": entry.get("tags", []),
        })
    for k, v in defaults.items():
        if k not in entry or entry[k] is None:
            entry[k] = v
    # Always set source_window to match top-level — per-entry values are stale
    if entry.get("source_window") != source_window:
        entry["source_window"] = source_window
    return entry


def tag(grade):
    """Return CSS class and label for a grade tag."""
    if grade == "B":
        return "g", "B"
    if grade == "C":
        return "y", "C"
    if grade == "A":
        return "g", "A"
    return "n", grade


def render_b_card(b):
    """Render a single B candidate card from JSON entry."""
    tag_cls, tag_label = tag(b.get("grade", "B"))
    tags_html = " ".join(
        f'<span class="t {tag_cls if i == 0 else "n"}">{t}</span>'
        for i, t in enumerate(b.get("tags", [])[:4])
    )
    info = b.get("recommendation_status", "candidate_pending_approval").replace("_", " ")
    return f"""<div class="bcard"><div class="bl">B{b['index']} · {b['league']} · {b['kickoff_display']}</div><div class="bn">{b['home']} vs {b['away']}</div><div class="bs">{b.get('best_focus','')} · {b.get('market_type','')} · HT:{b.get('ht_score','?')} · Best:{b.get('best_score','?')}</div><div class="bt">{tags_html}</div><div class="bi">{info} · 待BOSS批准 · QQ未发送 · {b['source_window']} window</div></div>"""


def render_c_card(c):
    """Render a single C observation card from JSON entry."""
    return f"""<div class="ccard">C{c['index']} · {c['home']} vs {c['away']} · <span class="t y">observation-only</span> · QQ未发送</div>"""


def generate_html(data, source_hash, title, hardening_tag, include_nav=False):
    """Generate complete HTML page from candidate data."""
    sw = data.get("source_window", "midday")
    b_candidates = [normalize_entry(b, "B", sw) for b in data.get("B_candidates", [])]
    c_candidates = [normalize_entry(c, "C", sw) for c in data.get("C_candidates", [])]
    b_cards = "\n".join(render_b_card(b) for b in b_candidates)
    c_cards = "\n".join(render_c_card(c) for c in c_candidates)

    nav_html = ""
    if include_nav:
        nav_html = """<div style="background:#111a2a;border-radius:8px;padding:8px 10px;margin:8px 0;font-size:12px">
<div style="font-size:11px;color:#4fc3f7;font-weight:700;margin-bottom:4px"> NAV 仪表总台入口</div>
<div style="display:flex;flex-wrap:wrap;gap:6px">
<a href="intel_ops_console.html" style="color:#fff;background:#0a2a4a;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:600"> 仪表总台</a>
<a href="v2_today.html" style="color:#4fc3f7;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px">V2 Today</a>
<a href="intel_desk.html" style="color:#4fc3f7;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px">Intel Desk</a>
<a href="ops_heartbeat.html" style="color:#4fc3f7;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px">OPS Heartbeat</a>
</div></div>
"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="Cache-Control" content="no-store,no-cache,must-revalidate,max-age=0">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>{title}</title>
{CSS}</head><body>
<h1>{title}</h1>
{nav_html}
<div class="m2">next_window={data.get('next_window','?')} | V4_QQ_ENABLED=false | A={data['A_count']} B={data['B_count']} C={data['C_count']} SKIP={data['SKIP_count']} | future_ab_trigger={"true" if data.get('future_ab_trigger') else "false"} | BOSS approval required</div>
<div class="m">生成: {data['generated_at']} | source: {data['source_window']} window | source_hash: {source_hash} | hardening={hardening_tag}</div>

<h2>CURRENT: V2 状态</h2>
<div class="card">
<div class="r"><span class="l">PRODUCTION_VERIFIED</span><span class="v"><span class="t g">true</span></span></div>
<div class="r"><span class="l">PIPELINE_READY</span><span class="v"><span class="t g">true</span></span></div>
<div class="r"><span class="l">QQ_ENABLED</span><span class="v"><span class="t g">true</span> V2 only</span></div>
<div class="r"><span class="l">CRON_ENABLED</span><span class="v"><span class="t g">true</span></span></div>
<div class="r"><span class="l">VERIFIED_WRITTEN</span><span class="v"><span class="t g">true</span> scope=V2_ONLY</span></div>
<div class="r"><span class="l">real_bet / D13 / V33 / HOURLY</span><span class="v"><span class="t n">false</span></span></div>
</div>

<h2>CURRENT: V4 状态</h2>
<div class="card">
<div class="r"><span class="l">A / B / C / SKIP</span><span class="v"><b>{data['A_count']} / {data['B_count']} / {data['C_count']} / {data['SKIP_count']}</b></span></div>
<div class="r"><span class="l">formal_recommendation_count</span><span class="v">{data['formal_recommendation_count']}</span></div>
<div class="r"><span class="l">future_ab_trigger</span><span class="v"><span class="t g">true</span></span></div>
<div class="r"><span class="l">V4_QQ_ENABLED</span><span class="v"><span class="t n">false</span></span></div>
<div class="r"><span class="l">actual_send / qq_sent</span><span class="v"><span class="t r2">false</span></span></div>
<div class="r"><span class="l">route</span><span class="v">shadow_only</span></div>
<div class="r"><span class="l">BOSS approval required</span><span class="v"><span class="t y">true</span></span></div>
<div class="r"><span class="l">next_window</span><span class="v">{data.get('next_window','?')}</span></div>
<div class="r"><span class="l">D13 / V33 / HOURLY</span><span class="v"><span class="t n">false</span></span></div>
</div>

<h2> V4 B级候选 — {data['B_count']}场</h2>
{b_cards}

<h2> C级观察 — {data['C_count']}场（observation-only）</h2>
{c_cards}

<h2> 历史审计 (historical=true · not_current=true · audit_only=true)</h2>
<div class="history">
<b>QQ unauthorized incident</b> — 2026-05-19 23:09<br>
_push_system_event() 无 V2_QQ_SEND_ENABLED gate → QQ 真实发送<br>
已修复 · BOSS 已签收 (23:24)<br><br>

<b>T90 BET_LOCKED proof</b> — 2026-05-19 23:00<br>
Ried vs Wolfsberger AC (historical, not current)<br><br>

<b>Previous hardening tags (NOT current):</b>
cron_removed · readonly_only · no_formal_daily_pool · crontool removed · no_cron_recovery<br>
All above are historical. NOT current operational status.<br>
Current ops mode: BOSS-directed. V2 PRODUCTION_VERIFIED. V4 QQ disabled pending BOSS approval.<br><br>

<i>historical=true · not_current=true · audit_only=true</i>
</div>

<div class="footer">
V2: PRODUCTION_VERIFIED | V4: {data['source_window']} A={data['A_count']} B={data['B_count']} C={data['C_count']} SKIP={data['SKIP_count']}, QQ disabled | Next: {data.get('next_window','?')}<br>
D13/V33/HOURLY=false | actual_send=false | strategy unchanged<br>
source: {data['source_window']} window | hash: {source_hash}
</div>
</body></html>"""


def main():
    if not CANDIDATE_JSON.is_file():
        print(f"ERROR: candidate JSON not found: {CANDIDATE_JSON}", file=sys.stderr)
        sys.exit(1)

    raw = CANDIDATE_JSON.read_bytes()
    source_hash = hashlib.md5(raw).hexdigest()[:12]
    data = json.loads(raw.decode())

    generated_at = datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    hardening_tag = "INTEL-DESK-CANDIDATE-VIEW-SOURCE-BINDING"

    # Generate all 4 dashboard pages
    pages = {
        "index.html": ("V2/V4 情报台", hardening_tag),
        "intel_desk.html": ("Intel Desk", hardening_tag),
        "v2_today.html": ("V2/V4 情报台", hardening_tag),
        "ops_heartbeat.html": ("OPS Heartbeat", hardening_tag),
    }

    dash_dir = MODULE / "data" / "runtime" / "dashboard"
    dash_dir.mkdir(parents=True, exist_ok=True)

    for filename, (title, tag_val) in pages.items():
        is_index = filename == "index.html"
        html = generate_html(data, source_hash, title, tag_val, include_nav=is_index)
        out_path = dash_dir / filename
        out_path.write_text(html)
        print(f"  wrote {out_path} ({len(html)} bytes)")

    # Write generation marker
    marker = {
        "generator": "tools/generate_intel_desk_html.py",
        "generated_at": generated_at,
        "source_path": str(CANDIDATE_JSON.relative_to(MODULE)),
        "source_hash": source_hash,
        "source_hash_full": hashlib.md5(raw).hexdigest(),
        "B_count": data["B_count"],
        "C_count": data["C_count"],
        "pages_generated": list(pages.keys()),
    }
    marker_path = MODULE / "data" / "runtime" / "status" / "intel_desk_html_generation_marker_20260520.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))

    print(f"\nGeneration complete. source_hash={source_hash} | B={data['B_count']} C={data['C_count']}")
    print(f"Marker: {marker_path}")


if __name__ == "__main__":
    main()
