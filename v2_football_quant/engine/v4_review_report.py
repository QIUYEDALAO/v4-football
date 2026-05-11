"""
V4 每日复盘报告
================
汇总 scout / live status / entries / verified / odds snapshots。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.live_odds_snapshot import summarize_fixture_timeline

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
PAPER_DIR = BASE_DIR / "data" / "paper_trading"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _pct(x) -> str:
    try:
        return f"{float(x):.1f}%"
    except Exception:
        return "-"


def build_review(date_str: str) -> dict:
    key = _date_key(date_str)
    scout = _load_json(REPORT_DIR / f"scout_v4_{key}.json", [])
    watchlist = _load_json(REPORT_DIR / f"live_watchlist_{key}.json", [])
    live_status = _load_json(MONITOR_DIR / f"v4_live_status_{key}.json", {})
    entries = _load_json(PAPER_DIR / f"v4_live_entries_{key}.json", [])
    verified = _load_json(PAPER_DIR / f"v4_live_verified_{key}.json", {})

    statuses = live_status.get("statuses", []) if isinstance(live_status, dict) else []
    action_counts = Counter(x.get("action", "UNKNOWN") for x in statuses)
    tiers = Counter(x.get("tier", "B") for x in scout if isinstance(x, dict))
    entry_summaries = []
    for entry in entries if isinstance(entries, list) else []:
        fid = int(entry.get("fixture_id"))
        entry_summaries.append({
            "fixture_id": fid,
            "home": entry.get("home"),
            "away": entry.get("away"),
            "entry_minute": entry.get("entry_minute"),
            "entry_line": entry.get("entry_line"),
            "entry_over_odds": entry.get("entry_over_odds"),
            "odds_timeline": summarize_fixture_timeline(key, fid),
        })

    return {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "scout_count": len(scout) if isinstance(scout, list) else 0,
        "watchlist_count": len(watchlist) if isinstance(watchlist, list) else 0,
        "tier_counts": dict(tiers),
        "live_action_counts": dict(action_counts),
        "entry_count": len(entries) if isinstance(entries, list) else 0,
        "verified_summary": {
            "completed": verified.get("completed", 0) if isinstance(verified, dict) else 0,
            "wins": verified.get("wins", 0) if isinstance(verified, dict) else 0,
            "pushes": verified.get("pushes", 0) if isinstance(verified, dict) else 0,
            "losses": verified.get("losses", 0) if isinstance(verified, dict) else 0,
            "total_pnl": verified.get("total_pnl", 0) if isinstance(verified, dict) else 0,
            "roi_pct": verified.get("roi_pct", 0) if isinstance(verified, dict) else 0,
        },
        "entries": entry_summaries,
    }


def render_markdown(review: dict) -> str:
    lines = [
        f"# V4 每日复盘 | {review['date']}",
        "",
        f"- 情报场次: {review['scout_count']}",
        f"- 滚球雷达: {review['watchlist_count']}",
        f"- 纸盘入场: {review['entry_count']}",
        f"- 分级: {review.get('tier_counts', {})}",
        f"- 走地动作: {review.get('live_action_counts', {})}",
        "",
        "## 结算",
    ]
    v = review.get("verified_summary", {})
    lines.extend([
        f"- 已结算: {v.get('completed', 0)}",
        f"- W/P/L: {v.get('wins', 0)}/{v.get('pushes', 0)}/{v.get('losses', 0)}",
        f"- PnL: {v.get('total_pnl', 0):+}",
        f"- ROI: {_pct(v.get('roi_pct', 0))}",
        "",
        "## 入场明细",
    ])
    if not review.get("entries"):
        lines.append("- 无 BUY_NOW 入场")
    for entry in review.get("entries", []):
        tl = entry.get("odds_timeline", {})
        first_target = tl.get("first_target_line") or {}
        lines.append(
            f"- #{entry.get('fixture_id')} {entry.get('home')} vs {entry.get('away')} | "
            f"{entry.get('entry_minute')}分 大{entry.get('entry_line')}@{entry.get('entry_over_odds')} | "
            f"快照{tl.get('snapshot_count', 0)}条 | 首次目标线 {first_target.get('minute', '-')}分 "
            f"大{first_target.get('line', '-')}@{first_target.get('over_odds', '-')}"
        )
    lines.append("")
    return "\n".join(lines)


def save_review(date_str: str) -> dict:
    key = _date_key(date_str)
    review = build_review(key)
    json_path = REPORT_DIR / f"v4_review_{key}.json"
    md_path = REPORT_DIR / f"v4_review_{key}.md"
    _save_json(json_path, review)
    md_path.write_text(render_markdown(review), encoding="utf-8")
    return {"json_path": str(json_path), "md_path": str(md_path), "review": review}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    result = save_review(args.date)
    print(json.dumps({k: v for k, v in result.items() if k != "review"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
