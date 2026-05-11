# engine/v4_report.py — V4 情报卡片报表
# 只管画像展示，不管策略/Tier/CLV
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "daily_reports"

def load_v4_predictions(date_str: str):
    path = DATA_DIR / f"predictions_v4_{date_str.replace('-','')}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _pct(x: float) -> str:
    return f"{round(x * 100, 1)}%"

def render_match_card(rec: dict) -> str:
    home = rec["home"]
    away = rec["away"]
    league = rec.get("league", "Unknown")
    dt = rec.get("date")
    dt_str = dt
    try:
        dt_str = datetime.fromisoformat(dt).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass

    f = rec.get("factors", {})
    tb = f.get("time_bins", {}) or {}
    line = rec.get("line")
    odds = rec.get("placed_odds")
    opp_odds = rec.get("placed_opp_odds")

    lines = []
    lines.append(f"⚽ {home} vs {away} ({league})")
    lines.append(f"   开球时间 : {dt_str}")
    lines.append("")
    # H2H 概览
    lines.append("📚 历史交锋 (H2H)")
    lines.append(f"   总场次       : {f.get('h2h_total', '?')} 场")
    lines.append(f"   2020+ 场次    : {f.get('h2h_3y_count', '?')} 场"
                 f" (过期 {f.get('h2h_expired', 0)} 场)")
    lines.append(f"   上半场有球率 : {_pct(f.get('h2h_ht_goal_rate', 0.0))}")
    lines.append(f"   全场 0-0 次数 : {f.get('ft_0_0_count', 0)} 场")
    lines.append("")
    # 进球时间分布
    lines.append("⏱ 上半场进球时间分布 (H2H)")
    lines.append(f"   0–15 分钟    : {_pct(tb.get('0_15', 0.0))}")
    lines.append(f"   16–30 分钟   : {_pct(tb.get('16_30', 0.0))}")
    lines.append(f"   31–45 分钟   : {_pct(tb.get('31_45', 0.0))}")
    lines.append("")
    # 近期状态
    lines.append("📈 近期状态 (各队近 5 场)")
    lines.append(f"   {home} HT有球率 : {_pct(f.get('home_recent_ht_over', 0.0))}")
    lines.append(f"   {away} HT有球率 : {_pct(f.get('away_recent_ht_over', 0.0))}")
    lines.append(f"   综合动能       : {_pct(f.get('recent_form_avg', 0.0))}")
    lines.append("")
    # 盘口快照
    lines.append("🎯 盘口快照 (HT 进球线)")
    lines.append(f"   市场类型 : {rec.get('market', 'HT_OU')} {line}")
    lines.append(f"   Over {line} 赔率 : {odds}")
    lines.append(f"   Under {line} 赔率 : {opp_odds}")
    lines.append(f"   线质量   : {rec.get('line_quality', 'unknown')}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, required=True,
                        help="日期，如 2026-05-10")
    parser.add_argument("--fixture_id", type=int, help="可选，只看某场")
    args = parser.parse_args()

    data = load_v4_predictions(args.date)
    records = data if isinstance(data, list) else data.get("results", data)

    for rec in records:
        if args.fixture_id and rec.get("fixture_id") != args.fixture_id:
            continue
        print(render_match_card(rec))
        print("\n" + "-" * 60 + "\n")
