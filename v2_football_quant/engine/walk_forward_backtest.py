from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from engine.asian_ev import over_asian_ev
from engine.execution_cost_model import estimate_execution_cost

PAPER_DIR = BASE_DIR / "data" / "paper_trading"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
HIST_DIR = BASE_DIR / "data" / "historical"


@dataclass
class Split:
    name: str
    start: str
    end: str


def _load(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_verified_rows() -> list[dict]:
    rows: list[dict] = []
    for fp in sorted(PAPER_DIR.glob("v4_live_verified_*.json")):
        data = _load(fp, {})
        for r in data.get("results", []):
            rr = dict(r)
            rr["_date"] = (rr.get("verified_at") or "")[:10]
            rows.append(rr)
    return rows


def _proxy_probs_from_ou25(odds_over25: float | None, ht_goals: int) -> tuple[float, float, float]:
    """
    用 O/U2.5 赔率 + 实际半场节奏粗略拟合 P0/P1/P2+（仅用于历史近似回放）。
    """
    if odds_over25 and odds_over25 > 1.01:
        implied = 1.0 / odds_over25
        p2 = max(0.22, min(0.52, implied * 0.62))
    else:
        p2 = 0.34
    # 若半场已经偏活跃，提升2+概率的先验（回放近似）
    if ht_goals >= 2:
        p2 = min(0.65, p2 + 0.06)
    p1 = max(0.24, min(0.52, 0.58 - p2 * 0.45))
    p0 = max(0.05, 1.0 - p1 - p2)
    s = p0 + p1 + p2
    return p0 / s, p1 / s, p2 / s


def _settle_over_line(line: float, ht_goals: int, odds: float = 1.80) -> float:
    if line == 1.0:
        if ht_goals >= 2:
            return odds - 1.0
        if ht_goals == 1:
            return 0.0
        return -1.0
    if line == 0.75:
        if ht_goals >= 2:
            return odds - 1.0
        if ht_goals == 1:
            return 0.5 * (odds - 1.0)
        return -1.0
    return -1.0


def _load_fd_history_rows(mode: str = "rule_replay") -> list[dict]:
    """
    从 football-data.co.uk 标准化JSONL构建可用于walk-forward的历史样本。
    mode:
      - rule_replay: 近似 V4_HT 规则回放（EV门槛 + 亚洲盘结算近似）
      - ht_goal_proxy: 老版本，仅HT有球代理
    """
    path = HIST_DIR / "fd_history_matches.jsonl"
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            d = r.get("match_date")
            if not d:
                continue
            ht_goals = int(r.get("ht_goals") or 0)
            odds_over25 = r.get("odds_over25")
            stake = 1.0
            pnl = 0.0
            entered = False
            if mode == "ht_goal_proxy":
                pnl = 0.8 if ht_goals > 0 else -1.0
                entered = True
            else:
                # 近似回放：同时评估 Over0.75 与 Over1.0，择优且必须滑点后保正EV
                p0, p1, p2 = _proxy_probs_from_ou25(odds_over25, ht_goals)
                ev1 = over_asian_ev(line=1.0, odds=1.80, p0=p0, p1=p1, p2plus=p2).ev
                ev075 = over_asian_ev(line=0.75, odds=1.80, p0=p0, p1=p1, p2plus=p2).ev
                pick_line = 0.75 if ev075 > ev1 else 1.0
                ev_gross = max(ev075, ev1)
                ex = estimate_execution_cost(
                    displayed_odds=1.80,
                    ev_gross=ev_gross,
                    odds_alive_seconds=3.0,
                    latency_seconds=1.5,
                    market_freeze=False,
                )
                if ex.conservative_ev > 0:
                    entered = True
                    gross_pnl = _settle_over_line(pick_line, ht_goals, odds=1.80)
                    exec_cost = ex.slippage + ex.latency_cost + ex.requote_cost
                    pnl = gross_pnl - exec_cost
                else:
                    stake = 0.0
                    pnl = 0.0
            rows.append({
                "_date": d,
                "stake": stake,
                "pnl": pnl,
                "source": f"fd_history_{mode}",
                "entered": entered,
                "league_code": r.get("league_code"),
                "season": r.get("season"),
            })
    return rows


def _in_range(d: str, start: str, end: str) -> bool:
    return bool(d) and start <= d <= end


def _eval(rows: list[dict]) -> dict:
    n = len(rows)
    staked = sum(float(x.get("stake", 0) or 0) for x in rows)
    pnl = sum(float(x.get("pnl", 0) or 0) for x in rows)
    wins = sum(1 for x in rows if float(x.get("pnl", 0) or 0) > 0)
    return {
        "n": n,
        "wins": wins,
        "hit_rate_pct": round(wins / n * 100, 2) if n else 0.0,
        "staked": round(staked, 4),
        "pnl": round(pnl, 4),
        "roi_pct": round(pnl / staked * 100, 2) if staked else 0.0,
    }


def run_walk_forward(mode: str = "rule_replay") -> dict:
    verified_rows = _load_verified_rows()
    fd_rows = _load_fd_history_rows(mode=mode)
    rows = fd_rows if fd_rows else verified_rows
    splits = [
        Split("train", "2024-01-01", "2024-06-30"),
        Split("tune", "2024-07-01", "2024-09-30"),
        Split("valid", "2024-10-01", "2024-12-31"),
        Split("lock_test", "2025-01-01", "2025-06-30"),
        Split("forward_sim", "2025-07-01", "2025-12-31"),
        Split("paper_live", "2026-01-01", "2026-12-31"),
    ]
    out = {
        "generated_at": datetime.now().isoformat(),
        "sample_size": len(rows),
        "data_source": f"fd_history_{mode}" if fd_rows else "v4_live_verified",
        "mode": mode,
        "splits": {},
    }
    for sp in splits:
        seg = [r for r in rows if _in_range(r.get("_date", ""), sp.start, sp.end)]
        out["splits"][sp.name] = {"start": sp.start, "end": sp.end, **_eval(seg)}
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--mode", default="rule_replay", choices=["rule_replay", "ht_goal_proxy"])
    args = parser.parse_args()
    rep = run_walk_forward(mode=args.mode)
    if args.save:
        p = REPORT_DIR / "v4_walk_forward_report.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(p), "report": rep}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
