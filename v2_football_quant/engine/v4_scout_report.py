# engine/v4_scout_report.py — V4 球探报告系统
# 读取 scout_v4_YYYYMMDD.json → 生成教练笔记式战术画像
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "daily_reports"

def load_scout_data(date_str: str):
    path = DATA_DIR / f"scout_v4_{date_str.replace('-','')}.json"
    if not path.exists():
        path = DATA_DIR / f"predictions_v4_{date_str.replace('-','')}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _pct(x: float) -> str:
    return f"{round(x * 100, 1)}%"

def _heat_bar(pct_val: float, width: int = 10) -> str:
    filled = int(round(pct_val * width))
    return "█" * filled + "░" * (width - filled)

def generate_match_report(match_data: dict) -> str:
    home = match_data["home"]
    away = match_data["away"]
    league = match_data.get("league", "Unknown")
    ko = match_data.get("kickoff", "")
    try:
        dt = datetime.fromisoformat(ko.replace("Z", "+00:00"))
        ko_str = dt.strftime("%m-%d %H:%M")
    except Exception:
        ko_str = ko or "??:??"

    factors = match_data.get("factors", {})
    tb = factors.get("time_bins", {})
    ht_lines = match_data.get("ht_ou_lines", [])
    injury = match_data.get("injury", {})

    lines = []
    lines.append("=" * 60)
    lines.append(f"🏟  {league}")
    lines.append(f"⏰  {ko_str}")
    lines.append(f"🔥  {home} vs {away}")
    lines.append("=" * 60)

    # ── 1. 历史基因 ──
    lines.append("")
    lines.append("📋 【历史基因 (H2H)】")
    lines.append(f"   近 {factors.get('h2h_sample_size', '?')} 场交锋 HT 有球率: {_pct(factors.get('h2h_ht_goal_rate', 0))}"
                 f" {_heat_bar(factors.get('h2h_ht_goal_rate', 0))}")
    lines.append(f"   2020+ 场次: {factors.get('h2h_3y_count', '?')} 场"
                 f" (过期 {factors.get('h2h_expired', 0)} 场)")
    lines.append(f"   0-0 场次: {factors.get('ft_0_0_count', 0)} 场")
    lines.append(f"   进球时间热区:")
    lines.append(f"     0-15分  {_pct(tb.get('0_15', 0))} {_heat_bar(tb.get('0_15', 0))}")
    lines.append(f"     16-30分 {_pct(tb.get('16_30', 0))} {_heat_bar(tb.get('16_30', 0))}")
    lines.append(f"     31-45分 {_pct(tb.get('31_45', 0))} {_heat_bar(tb.get('31_45', 0))}")

    # ── 2. 近期动能 ──
    lines.append("")
    lines.append("⚡ 【近期动能 (近5场)】")
    lines.append(f"   {home}: HT有球率 {_pct(factors.get('home_recent_ht_over', 0))}"
                 f" {_heat_bar(factors.get('home_recent_ht_over', 0))}")
    lines.append(f"   {away}: HT有球率 {_pct(factors.get('away_recent_ht_over', 0))}"
                 f" {_heat_bar(factors.get('away_recent_ht_over', 0))}")
    lines.append(f"   综合动能: {_pct(factors.get('recent_form_avg', 0))}"
                 f" {'✅ 达标' if factors.get('recent_form_avg', 0) >= 0.7 else '⚠️ 偏弱'}")

    # ── 3. 庄家盘口阵地 ──
    lines.append("")
    lines.append("⚖️ 【庄家盘口阵地 (HT 大小球)】")
    if ht_lines:
        for ln in ht_lines:
            over_val = ln.get("over", "-")
            under_val = ln.get("under", "-")
            line_str = str(ln.get("line", "?"))
            lines.append(f"   大 {line_str}  @ {over_val}  ｜  小 {line_str}  @ {under_val}")
    else:
        lines.append("   ❓ 暂无 Pinnacle 半场大小球数据")

    # ── 4. 伤病侦查 ──
    lines.append("")
    lines.append("🚑 【战力完整度】")
    for side, team_name in [("home", home), ("away", away)]:
        h = injury.get(side, {})
        status = h.get("status", "unknown")
        missing = h.get("missing", [])
        if status == "healthy":
            lines.append(f"   {team_name}: ✅ 全员健康")
        elif missing:
            lines.append(f"   {team_name}: ⚠️ 缺阵 {h.get('missing_count', 0)} 人")
            for m in missing[:3]:
                lines.append(f"      - {m['name']} ({m['reason']})")
        else:
            lines.append(f"   {team_name}: ❓ 数据缺失")

    # ── 5. 情报总结 ──
    lines.append("")
    lines.append("💡 【情报总结】")
    ht_rate = factors.get("h2h_ht_goal_rate", 0)
    rfa = factors.get("recent_form_avg", 0)
    stats_text = []

    if ht_rate >= 0.85:
        stats_text.append("🔥 极高 HT 有球局，历史交锋几乎必有进球")
    elif ht_rate >= 0.7:
        stats_text.append("✅ 典型 HT 有球局")
    else:
        stats_text.append("⚠️ HT 有球率偏低")

    if rfa >= 0.8:
        stats_text.append("两队近期状态火热")
    elif rfa >= 0.7:
        stats_text.append("近期状态尚可")

    late_goal = tb.get("31_45", 0)
    early_goal = tb.get("0_15", 0)
    if late_goal > 0.5:
        stats_text.append(f"慢热后发型：{_pct(late_goal)} 的进球在31-45分钟")
    if early_goal > 0.4:
        stats_text.append(f"闪电战型：{_pct(early_goal)} 的比赛前15分钟就破门")

    lines.append("   " + "；".join(stats_text))

    has_high = any(float(str(ln["line"])) >= 1.5 for ln in ht_lines)
    if has_high and late_goal > 0.5:
        lines.append("   ⏱ 庄家高开 + 慢热画像 → 前20分钟0-0是滚球切入良机")
    elif has_high:
        lines.append("   ⏱ 庄家高开盘口 → 赛前直打风险偏高，建议观察")

    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="V4 球探报告系统")
    parser.add_argument("--date", type=str, required=True, help="日期，如 2026-05-11")
    parser.add_argument("--fixture_id", type=int, help="可选，只看某场")
    parser.add_argument("--league", type=str, help="可选，只看某个联赛")
    args = parser.parse_args()

    data = load_scout_data(args.date)
    records = data if isinstance(data, list) else data.get("results", data)

    printed = 0
    for rec in records:
        if args.fixture_id and rec.get("fixture_id") != args.fixture_id:
            continue
        if args.league and args.league.lower() not in rec.get("league", "").lower():
            continue
        print(generate_match_report(rec))
        print()
        printed += 1

    print(f"📊 共 {printed}/{len(records)} 场")
