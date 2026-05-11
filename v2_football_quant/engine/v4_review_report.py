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
from engine.v4_strategy_eval import evaluate as evaluate_v4_results, load_v4_results
from engine.v4_sh_strategy_eval import evaluate as evaluate_sh_results, load_rows as load_sh_rows
from engine.walk_forward_backtest import run_walk_forward
from engine.league_replay_tiers import build_report as build_league_tiers

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
EXEC_DIR = BASE_DIR / "data" / "execution"
RESEARCH_DIR = BASE_DIR / "data" / "research"
CONFIG_DIR = BASE_DIR / "config"


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


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _pct(x) -> str:
    try:
        return f"{float(x):.1f}%"
    except Exception:
        return "-"


def _parse_pct_value(text: str) -> float:
    s = str(text).strip().replace("%", "")
    try:
        return float(s)
    except Exception:
        return 0.0


def _load_kill_criteria_thresholds() -> dict:
    path = CONFIG_DIR / "kill_criteria.yaml"
    if not path.exists():
        return {}
    # 轻量解析（仅提取当前用到的字段，避免额外依赖）
    after_100 = None
    after_300 = None
    rej_rate = None
    with open(path, encoding="utf-8") as f:
        for ln in f:
            t = ln.strip()
            if t.startswith("if_slippage_adjusted_roi_below:"):
                val = t.split(":", 1)[1].strip()
                if after_100 is None:
                    after_100 = _parse_pct_value(val)
                else:
                    after_300 = _parse_pct_value(val)
            elif t.startswith("if_rejection_rate_above:"):
                val = t.split(":", 1)[1].strip()
                rej_rate = _parse_pct_value(val)
    return {
        "after_100_roi_below_pct": after_100 if after_100 is not None else -3.0,
        "after_300_roi_below_pct": after_300 if after_300 is not None else 0.0,
        "rejection_rate_above_pct": rej_rate if rej_rate is not None else 30.0,
    }


def _build_health_panel(review_core: dict) -> dict:
    se = review_core.get("strategy_eval", {}) or {}
    rt = review_core.get("roi_triplet", {}) or {}
    lt = review_core.get("league_tiers", {}) or {}
    th = _load_kill_criteria_thresholds()

    sample = int(se.get("sample_size", 0) or 0)
    min_sample = int(se.get("min_sample", 50) or 50)
    conservative_roi = float(rt.get("conservative_fill_roi_pct", 0.0) or 0.0)
    slippage_roi = float(rt.get("slippage_adjusted_roi_pct", 0.0) or 0.0)
    exec_n = int(rt.get("execution_samples", 0) or 0)

    # 联赛状态建议统计
    league_rows = lt.get("leagues", []) if isinstance(lt, dict) else []
    league_status_counts = Counter((x.get("status") or "UNKNOWN") for x in league_rows)

    kill_flags = []
    if sample >= 100 and slippage_roi < float(th.get("after_100_roi_below_pct", -3.0)):
        kill_flags.append("AFTER_100_TRIGGER: pause_and_review")
    if sample >= 300 and slippage_roi < float(th.get("after_300_roi_below_pct", 0.0)):
        kill_flags.append("AFTER_300_TRIGGER: disable_real_money")

    health = "GREEN"
    if kill_flags:
        health = "RED"
    elif sample < min_sample or conservative_roi <= 0:
        health = "YELLOW"

    return {
        "health_status": health,
        "sample_progress": {
            "sample_size": sample,
            "min_sample": min_sample,
            "progress_pct": round(sample / min_sample * 100, 1) if min_sample else 0.0,
        },
        "execution_quality": {
            "conservative_fill_roi_pct": conservative_roi,
            "slippage_adjusted_roi_pct": slippage_roi,
            "execution_samples": exec_n,
        },
        "league_switch_suggestion": dict(league_status_counts),
        "kill_criteria_flags": kill_flags,
    }


def build_review(date_str: str) -> dict:
    key = _date_key(date_str)
    scout = _load_json(REPORT_DIR / f"scout_v4_{key}.json", [])
    watchlist = _load_json(REPORT_DIR / f"live_watchlist_{key}.json", [])
    live_status = _load_json(MONITOR_DIR / f"v4_live_status_{key}.json", {})
    entries = _load_json(PAPER_DIR / f"v4_live_entries_{key}.json", [])
    verified = _load_json(PAPER_DIR / f"v4_live_verified_{key}.json", {})
    sh_verified = _load_json(PAPER_DIR / f"v4_second_half_verified_{key}.json", {})
    execution_rows = _load_jsonl(EXEC_DIR / f"live_execution_sim_{key}.jsonl")
    strategy_eval = evaluate_v4_results(load_v4_results())
    sh_strategy_eval = evaluate_sh_results(load_sh_rows())
    walk_forward = run_walk_forward()
    league_tiers = build_league_tiers()
    candidates_path = RESEARCH_DIR / "strategy_candidates.jsonl"
    candidate_count = 0
    if candidates_path.exists():
        with open(candidates_path, encoding="utf-8") as f:
            candidate_count = sum(1 for ln in f if ln.strip())

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

    raw_pnl = float(verified.get("total_pnl", 0) if isinstance(verified, dict) else 0.0)
    raw_stake = float(verified.get("total_staked", 0) if isinstance(verified, dict) else 0.0)
    slip_cost = sum(float(x.get("slippage", 0) or 0) for x in execution_rows)
    conservative_factor = 0.0
    if execution_rows:
        conservative_factor = sum(float(x.get("accepted_amount_estimate", 1.0) or 1.0) for x in execution_rows) / max(len(execution_rows), 1)
    conservative_factor = max(0.0, min(1.0, conservative_factor))
    slippage_pnl = raw_pnl - slip_cost
    conservative_pnl = slippage_pnl * conservative_factor

    roi_triplet = {
        "raw_paper_roi_pct": round((raw_pnl / raw_stake * 100), 2) if raw_stake else 0.0,
        "slippage_adjusted_roi_pct": round((slippage_pnl / raw_stake * 100), 2) if raw_stake else 0.0,
        "conservative_fill_roi_pct": round((conservative_pnl / raw_stake * 100), 2) if raw_stake else 0.0,
        "slippage_cost": round(slip_cost, 4),
        "execution_samples": len(execution_rows),
    }

    review = {
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
        "roi_triplet": roi_triplet,
        "strategy_eval": {
            "sample_size": strategy_eval.get("sample_size", 0),
            "sample_ready": strategy_eval.get("sample_ready", False),
            "decision": strategy_eval.get("decision"),
            "by_match_type": strategy_eval.get("by_match_type", {}),
            "by_primary_direction": strategy_eval.get("by_primary_direction", {}),
            "by_confidence": strategy_eval.get("by_confidence", {}),
        },
        "sh_verified_summary": {
            "completed": sh_verified.get("completed", 0) if isinstance(sh_verified, dict) else 0,
            "wins": sh_verified.get("wins", 0) if isinstance(sh_verified, dict) else 0,
            "pushes": sh_verified.get("pushes", 0) if isinstance(sh_verified, dict) else 0,
            "losses": sh_verified.get("losses", 0) if isinstance(sh_verified, dict) else 0,
            "total_pnl": sh_verified.get("total_pnl", 0) if isinstance(sh_verified, dict) else 0,
            "roi_pct": sh_verified.get("roi_pct", 0) if isinstance(sh_verified, dict) else 0,
        },
        "sh_strategy_eval": sh_strategy_eval,
        "walk_forward": walk_forward,
        "strategy_candidates": {
            "count": candidate_count,
            "path": str(candidates_path),
        },
        "league_tiers": league_tiers,
        "entries": entry_summaries,
    }
    review["health_panel"] = _build_health_panel(review)
    return review


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
        "## 三套ROI",
    ])
    rt = review.get("roi_triplet", {})
    lines.extend([
        f"- Raw Paper ROI: {_pct(rt.get('raw_paper_roi_pct', 0))}",
        f"- Slippage Adjusted ROI: {_pct(rt.get('slippage_adjusted_roi_pct', 0))}",
        f"- Conservative Fill ROI: {_pct(rt.get('conservative_fill_roi_pct', 0))}",
        f"- 滑点成本: {rt.get('slippage_cost', 0)} | 执行样本: {rt.get('execution_samples', 0)}",
        "",
        "## 智能标签样本",
    ])
    sv = review.get("sh_verified_summary", {})
    sh = review.get("sh_strategy_eval", {})
    lines.extend([
        "",
        "## 下半场策略",
        f"- 已结算: {sv.get('completed', 0)} | W/P/L {sv.get('wins', 0)}/{sv.get('pushes', 0)}/{sv.get('losses', 0)}",
        f"- ROI: {_pct(sv.get('roi_pct', 0))} | 样本决策: {sh.get('decision', '-')}",
    ])
    se = review.get("strategy_eval", {})
    lines.extend([
        f"- 样本: {se.get('sample_size', 0)} | {se.get('decision', '-')}",
        "- 按比赛类型:",
    ])
    by_type = se.get("by_match_type", {}) or {}
    if not by_type:
        lines.append("  - 暂无标签样本")
    for tag, stat in by_type.items():
        lines.append(
            f"  - {tag}: n={stat.get('n', 0)} · {stat.get('sample_status', '-')} · "
            f"W/P/L={stat.get('wins', 0)}/{stat.get('pushes', 0)}/{stat.get('losses', 0)} · "
            f"ROI={_pct(stat.get('roi_pct', 0))}"
        )
    wf = review.get("walk_forward", {})
    splits = wf.get("splits", {})
    lines.extend([
        "",
        "## Walk-forward",
        f"- 总样本: {wf.get('sample_size', 0)}",
    ])
    for k in ["train", "tune", "valid", "lock_test", "forward_sim", "paper_live"]:
        sp = splits.get(k, {})
        if not sp:
            continue
        lines.append(
            f"- {k}: n={sp.get('n', 0)} ROI={_pct(sp.get('roi_pct', 0))} "
            f"({sp.get('start', '-')}-{sp.get('end', '-')})"
        )
    sc = review.get("strategy_candidates", {})
    lt = review.get("league_tiers", {}) or {}
    top_leagues = (lt.get("leagues") or [])[:8]
    lines.extend([
        "",
        "## Strategy Candidates",
        f"- 记录数: {sc.get('count', 0)}",
        f"- 文件: {sc.get('path', '-')}",
        "",
        "## 联赛分层",
        f"- 样本: {lt.get('sample_size', 0)} | 联赛数: {lt.get('league_count', 0)}",
    ])
    for lg in top_leagues:
        lines.append(
            f"- {lg.get('league_code')} {lg.get('league_name')} | {lg.get('tier')} {lg.get('status')} | "
            f"n={lg.get('sample_size')} ROI={_pct(lg.get('roi_pct', 0))}"
        )
    hp = review.get("health_panel", {}) or {}
    sp = hp.get("sample_progress", {}) or {}
    ex = hp.get("execution_quality", {}) or {}
    lines.extend([
        "",
        "## 策略健康",
        f"- 状态: {hp.get('health_status', 'UNKNOWN')}",
        f"- 样本进度: {sp.get('sample_size', 0)}/{sp.get('min_sample', 0)} ({_pct(sp.get('progress_pct', 0))})",
        f"- Conservative ROI: {_pct(ex.get('conservative_fill_roi_pct', 0))} | Slippage ROI: {_pct(ex.get('slippage_adjusted_roi_pct', 0))}",
        f"- 联赛开关建议: {hp.get('league_switch_suggestion', {})}",
    ])
    flags = hp.get("kill_criteria_flags", []) or []
    if flags:
        lines.append(f"- Kill Flags: {'; '.join(flags)}")
    else:
        lines.append("- Kill Flags: 无触发")
    lines.extend([
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
