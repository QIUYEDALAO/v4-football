# engine/v4_scout_report.py — V4 战术指挥面板
# Hotness排序 + 红绿灯 + 多维过滤 → 赛前情报卡片
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "daily_reports"

# ── 核心球员权重库 ──
def _load_core_weights():
    try:
        path = BASE_DIR / "config" / "core_players_weight.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

CORE_WEIGHTS = _load_core_weights()


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


# ── 🚦 战力红绿灯引擎 ──
def get_injury_traffic_light(team_name: str, injury_data: dict) -> str:
    if not injury_data:
        return "❓ 数据缺失"
    missing = injury_data.get("missing", [])
    if not missing:
        return "✅ 全员健康"

    total_damage = 0.0
    core_names = []
    team_core = CORE_WEIGHTS.get(team_name, {})
    for player in missing:
        pname = player.get("name", "")
        for core_name, weight in team_core.items():
            if core_name.lower() in pname.lower():
                total_damage += weight
                core_names.append(core_name)
                break

    if total_damage >= 3.0 or len(core_names) >= 3:
        return f"🔴 严重折损 [{', '.join(core_names[:3])} 缺阵!]"
    elif total_damage > 0:
        return f"🟡 核心缺阵 [{', '.join(core_names[:3])}]"
    else:
        return f"🟢 战力完整 (无核心缺阵, {len(missing)}人替补伤停)"


# ── 🌡 热力评分引擎 ──
def calculate_hotness(factors: dict) -> float:
    h2h_rate = factors.get("h2h_ht_goal_rate", 0)
    recent_form = factors.get("recent_form_avg", 0)
    tb = factors.get("time_bins", {})
    late_goal_prob = tb.get("31_45", 0)
    # H2H基因50% + 近期动能30% + 后段绝杀偏好20%
    score = (h2h_rate * 0.5) + (recent_form * 0.3) + (late_goal_prob * 0.2)
    return round(score * 100, 1)


# ── 卡片渲染 ──
def generate_match_card(match_data: dict, show_hotness: bool = True) -> str:
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
    hotness = match_data.get("hotness_score", 0)

    lines = []
    lines.append("=" * 60)
    if show_hotness and hotness > 0:
        hot_bar = _heat_bar(hotness / 100, 15)
        lines.append(f"🏟  {league}                                  🔥热度: {hotness}/100 {hot_bar}")
    else:
        lines.append(f"🏟  {league}")
    lines.append(f"⏰  {ko_str}")
    lines.append(f"🔥  {home} vs {away}")
    lines.append("=" * 60)

    # 📋 历史基因
    lines.append("")
    lines.append("📋 【历史基因 (H2H)】")
    lines.append(f"   近{factors.get('h2h_sample_size','?')}场 HT有球率: {_pct(factors.get('h2h_ht_goal_rate',0))}"
                 f" {_heat_bar(factors.get('h2h_ht_goal_rate',0))}  |  场均 {factors.get('h2h_avg_ht_goals','?')} 球")
    lines.append(f"   2020+ {factors.get('h2h_3y_count','?')}场 (过期{factors.get('h2h_expired',0)}场)  |  0-0: {factors.get('ft_0_0_count',0)}场")
    lines.append(f"   进球热区: 0-15分 {_pct(tb.get('0_15',0))} {_heat_bar(tb.get('0_15',0))}")
    lines.append(f"            16-30分 {_pct(tb.get('16_30',0))} {_heat_bar(tb.get('16_30',0))}")
    lines.append(f"            31-45分 {_pct(tb.get('31_45',0))} {_heat_bar(tb.get('31_45',0))}")

    # ⚡ 近期动能
    lines.append("")
    lines.append("⚡ 【近期动能 (近5场)】")
    lines.append(f"   {home}: HT有球率 {_pct(factors.get('home_recent_ht_over',0))}"
                 f" | 场均 {factors.get('home_recent_avg_goals','?')} 球 {_heat_bar(factors.get('home_recent_ht_over',0))}")
    lines.append(f"   {away}: HT有球率 {_pct(factors.get('away_recent_ht_over',0))}"
                 f" | 场均 {factors.get('away_recent_avg_goals','?')} 球 {_heat_bar(factors.get('away_recent_ht_over',0))}")
    lines.append(f"   综合动能: {_pct(factors.get('recent_form_avg',0))}")

    # ⚖️ 庄家阵地
    lines.append("")
    lines.append("⚖️ 【庄家盘口阵地 (HT)】")
    if ht_lines:
        for ln in ht_lines:
            lines.append(f"   大{ln.get('line','?')} @{ln.get('over','-')}  ｜  小{ln.get('line','?')} @{ln.get('under','-')}")
    else:
        lines.append("   ❓ 暂无")

    # 🚦 战力红绿灯
    lines.append("")
    lines.append("🚦 【战力红绿灯】")
    lines.append(f"   {home}: {get_injury_traffic_light(home, injury.get('home', {}))}")
    lines.append(f"   {away}: {get_injury_traffic_light(away, injury.get('away', {}))}")

    # 💡 情报总结
    lines.append("")
    lines.append("💡 【情报总结】")
    ht_rate = factors.get("h2h_ht_goal_rate", 0)
    rfa = factors.get("recent_form_avg", 0)
    stats_text = []
    if ht_rate >= 0.85:
        stats_text.append("🔥极高HT有球局")
    elif ht_rate >= 0.7:
        stats_text.append("✅典型HT有球局")
    else:
        stats_text.append("⚠️HT有球率偏低")
    if rfa >= 0.8:
        stats_text.append("近期火热")
    elif rfa >= 0.7:
        stats_text.append("近期尚可")
    late_goal = tb.get("31_45", 0)
    early_goal = tb.get("0_15", 0)
    if late_goal > 0.5:
        stats_text.append(f"慢热后发({_pct(late_goal)}进球在31-45分)")
    if early_goal > 0.4:
        stats_text.append(f"闪电战({_pct(early_goal)}前15分破门)")
    lines.append("   " + "；".join(stats_text))

    has_high = any(float(str(ln["line"])) >= 1.5 for ln in ht_lines)
    if has_high and late_goal > 0.5:
        lines.append("   ⏱ 庄家高开+慢热画像 → 滚球潜伏良机")
    elif has_high:
        lines.append("   ⏱ 庄家高开 → 赛前直打风险偏高")

    lines.append("=" * 60)
    return "\n".join(lines)


def tier_label(score: float) -> str:
    if score >= 90:
        return "👑 S级 | 绝对焦点"
    elif score >= 80:
        return "🎖️ A级 | 优质候选"
    else:
        return "📋 B级 | 达标观察"


def tier_icon(score: float) -> str:
    if score >= 90: return "👑"
    elif score >= 80: return "🎖️"
    else: return "📋"


# ── CLI ──
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="V4 战术指挥面板")
    parser.add_argument("--date", type=str, required=True, help="日期 YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--league", type=str, help="只看某联赛")
    parser.add_argument("--min_ht_rate", type=float, default=0.7, help="最低HT有球率")
    parser.add_argument("--min_recent", type=float, default=0.0, help="最低近期动能")
    parser.add_argument("--fixture_id", type=int, help="只看某场(跳过过滤)")
    args = parser.parse_args()

    data = load_scout_data(args.date)
    records = data if isinstance(data, list) else data.get("results", data)

    filtered = []
    for rec in records:
        if args.fixture_id and rec.get("fixture_id") != args.fixture_id:
            continue
        f = rec.get("factors", {})
        if not args.fixture_id:
            if args.league and args.league.lower() not in rec.get("league", "").lower():
                continue
            if f.get("h2h_ht_goal_rate", 0) < args.min_ht_rate:
                continue
            if f.get("recent_form_avg", 0) < args.min_recent:
                continue
        rec["hotness_score"] = calculate_hotness(f)
        filtered.append(rec)

    sorted_matches = sorted(filtered, key=lambda x: x["hotness_score"], reverse=True)
    league_str = args.league or "全部"
    print(f"\n🔭 V4 战术情报雷达 | {args.date} | {league_str}")
    print(f"🎯 过滤: HT率≥{args.min_ht_rate} | 动能≥{args.min_recent}")
    print(f"📊 命中 {len(sorted_matches)} 场")
    print()

    # ── 按 S/A/B 分组 ──
    tiers = {"S": [], "A": [], "B": []}
    for m in sorted_matches:
        score = m["hotness_score"]
        m["tier_icon"] = tier_icon(score)
        if score >= 90:
            tiers["S"].append(m)
        elif score >= 80:
            tiers["A"].append(m)
        else:
            tiers["B"].append(m)

    for tier_key, tier_name in [("S", "👑 S级 | 绝对焦点"), ("A", "🎖️ A级 | 优质候选"), ("B", "📋 B级 | 达标观察")]:
        group = tiers[tier_key]
        if not group:
            continue
        print(f"{tier_name} (共 {len(group)} 场)")
        print("-" * 40)
        for rec in group:
            print(generate_match_card(rec))
            print()

    print(f"📊 共 {len(sorted_matches)} 场  |  S:{len(tiers['S'])} A:{len(tiers['A'])} B:{len(tiers['B'])}")
