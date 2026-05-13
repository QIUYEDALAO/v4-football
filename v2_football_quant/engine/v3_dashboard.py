from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
V3_DIR = BASE_DIR / "data" / "v3_wc2026"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _html_escape(v: Any) -> str:
    s = str(v if v is not None else "")
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _build_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    keys = [
        "V3_MD1_PAPER",
        "V3_MD2_WATCH",
        "V3_MD2_MICRO",
        "V3_BLOCK_MD3",
        "V3_BLOCK_KO",
        "V3_SKIP_LOW_GAP",
        "V3_SKIP_OFF_SEASON",
        "V3_KILL_CLV",
        "V3_BLOCK_STAGE_UNKNOWN",
        "V3_SKIP_TRUE_MISMATCH",
    ]
    counts = {k: 0 for k in keys}
    for r in rows:
        k = str(r.get("action") or "")
        counts[k] = counts.get(k, 0) + 1
    return counts


def render_dashboard(date_key: str) -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    signals_path = V3_DIR / f"v3_signals_{date_key}.jsonl"
    rows = _load_jsonl(signals_path)
    clv = _load_json(V3_DIR / "v3_clv_audit.json", {})
    counts = _build_counts(rows)
    by_source = {}
    for r in rows:
        s = str(r.get("stage_source") or "unknown")
        by_source[s] = by_source.get(s, 0) + 1

    extreme = sorted(
        [r for r in rows if float(r.get("gap_abs") or 0.0) >= 1.0],
        key=lambda x: float(x.get("gap_abs") or 0.0),
        reverse=True,
    )[:20]

    cards = []
    for r in extreme:
        cards.append(
            "<tr>"
            f"<td>{_html_escape(r.get('home'))} vs {_html_escape(r.get('away'))}</td>"
            f"<td>{_html_escape(r.get('wc_stage'))}</td>"
            f"<td>{_html_escape(r.get('bubble_team'))}</td>"
            f"<td>{_html_escape(r.get('target_market'))}</td>"
            f"<td>{float(r.get('gap_abs') or 0.0):.2f}</td>"
            f"<td>{_html_escape(r.get('action') or r.get('action_before_router'))}</td>"
            "</tr>"
        )

    table = "\n".join(cards) if cards else "<tr><td colspan='6'>暂无极端泡沫样本</td></tr>"

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>V3 世界杯泡沫雷达 {date_key}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
    h1 {{ margin: 0 0 16px; font-size: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; }}
    .label {{ color: #475569; font-size: 12px; }}
    .val {{ font-weight: 700; font-size: 22px; margin-top: 6px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }}
    th {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <h1>🌍 V3 世界杯泡沫雷达（{date_key}）</h1>
    <div class="grid">
    <div class="card"><div class="label">MD1 纸盘</div><div class="val">{counts.get('V3_MD1_PAPER', 0)}</div></div>
    <div class="card"><div class="label">MD2 观察</div><div class="val">{counts.get('V3_MD2_WATCH', 0)}</div></div>
    <div class="card"><div class="label">MD2 微沙盒</div><div class="val">{counts.get('V3_MD2_MICRO', 0)}</div></div>
    <div class="card"><div class="label">MD3 阻断</div><div class="val">{counts.get('V3_BLOCK_MD3', 0)}</div></div>
    <div class="card"><div class="label">KO 阻断</div><div class="val">{counts.get('V3_BLOCK_KO', 0)}</div></div>
    <div class="card"><div class="label">低Gap跳过</div><div class="val">{counts.get('V3_SKIP_LOW_GAP', 0)}</div></div>
  </div>
  <div class="grid">
    <div class="card"><div class="label">MD1 CLV样本</div><div class="val">{((clv.get('MD1_stats') or {{}}).get('bets') or 0)}</div></div>
    <div class="card"><div class="label">MD1 平均CLV</div><div class="val">{((clv.get('MD1_stats') or {{}}).get('avg_true_clv_pct') or 0):.2f}%</div></div>
    <div class="card"><div class="label">MD2 Rolling10 CLV</div><div class="val">{((clv.get('MD2_rolling_10') or {{}}).get('avg_true_clv_pct') or 0):.2f}%</div></div>
    <div class="card"><div class="label">Micro准入</div><div class="val">{_html_escape(((clv.get('micro_gate') or {{}}).get('status') or 'BLOCK'))}</div></div>
    </div>
  <div class="grid">
    <div class="card"><div class="label">阶段来源 explicit</div><div class="val">{by_source.get('explicit', 0)}</div></div>
    <div class="card"><div class="label">阶段来源 matchday</div><div class="val">{by_source.get('matchday', 0)}</div></div>
    <div class="card"><div class="label">阶段来源 team_group_order</div><div class="val">{by_source.get('team_group_order', 0)}</div></div>
    <div class="card"><div class="label">阶段来源 global_fallback</div><div class="val">{by_source.get('global_fallback', 0)}</div></div>
    <div class="card"><div class="label">阶段来源 unknown</div><div class="val">{by_source.get('unknown', 0)}</div></div>
  </div>
  <h2>🔥 极端泡沫 Top</h2>
  <table>
    <thead>
      <tr><th>比赛</th><th>阶段</th><th>泡沫方</th><th>目标市场</th><th>Gap</th><th>动作</th></tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
</body>
</html>
"""
    out = REPORT_DIR / f"v3_dashboard_{date_key}.html"
    latest = REPORT_DIR / "v3_dashboard_latest.html"
    out.write_text(html, encoding="utf-8")
    latest.write_text(html, encoding="utf-8")

    summary = {
        "date": date_key,
        "signals": len(rows),
        "counts": counts,
        "by_stage_source": by_source,
        "output_path": str(out),
        "latest_path": str(latest),
    }
    summary_path = REPORT_DIR / f"v3_dashboard_{date_key}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Render V3 dashboard")
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = ap.parse_args()
    summary = render_dashboard(args.date)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
