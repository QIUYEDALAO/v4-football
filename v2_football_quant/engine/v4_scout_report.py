# engine/v4_scout_report.py — V4 战术指挥面板
# Hotness排序 + 红绿灯 + 多维过滤 → 赛前情报卡片
import json
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
DATA_DIR = BASE_DIR / "data" / "daily_reports"

try:
    from engine.team_cn_map import strict_match as team_name_cn
except Exception:
    def team_name_cn(name: str) -> str:
        return name

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
    scores = factors.get("market_scores") or {}
    if scores:
        return round(max(float(v or 0) for v in scores.values()), 1)
    h2h_rate = factors.get("h2h_ht_goal_rate", 0)
    recent_form = factors.get("recent_form_avg", 0)
    tb = factors.get("time_bins", {})
    late_goal_prob = tb.get("31_45", 0)
    ht_score = (h2h_rate * 0.5) + (recent_form * 0.3) + (late_goal_prob * 0.2)

    sh_tb = factors.get("second_half_bins", {})
    sh_score = (
        factors.get("h2h_sh_goal_rate", 0) * 0.5
        + factors.get("recent_sh_avg", 0) * 0.3
        + (max(sh_tb.values()) if sh_tb else 0) * 0.2
    )
    ft_score = (
        factors.get("h2h_ft_over_1_5_rate", 0) * 0.55
        + factors.get("recent_ft_over_1_5", 0) * 0.30
        + factors.get("h2h_avg_ft_goals", 0) / 4.0 * 0.15
    )
    return round(max(ht_score, sh_score, ft_score) * 100, 1)


# ── 卡片渲染 ──
def generate_match_card(match_data: dict, show_hotness: bool = True) -> str:
    home_raw = match_data["home"]
    away_raw = match_data["away"]
    home = team_name_cn(home_raw)
    away = team_name_cn(away_raw)
    league = match_data.get("league", "Unknown")
    ko = match_data.get("kickoff", "")
    try:
        dt = datetime.fromisoformat(ko.replace("Z", "+00:00"))
        ko_str = dt.strftime("%m-%d %H:%M")
    except Exception:
        ko_str = ko or "??:??"

    factors = match_data.get("factors", {})
    tb = factors.get("time_bins", {})
    sh_tb = factors.get("second_half_bins", {})
    ht_lines = match_data.get("ht_ou_lines", [])
    injury = match_data.get("injury", {})
    lineup_gate = match_data.get("lineup_gate") or {}
    baseline = match_data.get("league_baseline", {}) or {}
    baseline_adj = baseline.get("adjustment", {}) or {}
    season_phase = match_data.get("season_phase", {}) or {}
    phase_adj = season_phase.get("adjustment", {}) or {}
    motivation = match_data.get("motivation", {}) or {}
    motivation_gate = motivation.get("gate", {}) or {}
    home_mot = motivation.get("home", {}) or {}
    away_mot = motivation.get("away", {}) or {}
    schedule_pressure = match_data.get("schedule_pressure", {}) or {}
    home_sched = schedule_pressure.get("home", {}) or {}
    away_sched = schedule_pressure.get("away", {}) or {}
    hotness = match_data.get("hotness_score", 0)
    market_focus = match_data.get("market_focus", "HT_LIVE_OVER")
    scores = match_data.get("market_scores") or factors.get("market_scores") or {}
    market_label = {
        "HT_LIVE_OVER": "上半场走地",
        "SECOND_HALF_OVER": "下半场大球参考",
        "FULLTIME_OVER": "全场大球参考",
    }.get(market_focus, market_focus)

    lines = []
    lines.append("=" * 60)
    if show_hotness and hotness > 0:
        hot_bar = _heat_bar(hotness / 100, 15)
        lines.append(f"🏟  {league}                                  🔥热度: {hotness}/100 {hot_bar}")
    else:
        lines.append(f"🏟  {league}")
    lines.append(f"⏰  {ko_str}")
    lines.append(f"🔥  {home} vs {away}  |  {market_label}")
    lines.append("=" * 60)

    # 📋 历史基因
    lines.append("")
    lines.append("🎚 【三方向评分】")
    lines.append(f"   HT走地: {scores.get('HT_LIVE_OVER', 0):>5}  |  SH参考: {scores.get('SECOND_HALF_OVER', 0):>5}  |  FT参考: {scores.get('FULLTIME_OVER', 0):>5}")
    lines.append(f"   当前方向: {market_label}  |  评分最强: {match_data.get('best_focus_by_score') or factors.get('best_focus_by_score', '-')}")
    lines.append("")
    lines.append("📋 【历史基因 (H2H)】")
    lines.append(f"   近{factors.get('h2h_sample_size','?')}场 HT有球率: {_pct(factors.get('h2h_ht_goal_rate',0))}"
                 f" {_heat_bar(factors.get('h2h_ht_goal_rate',0))}  |  场均 {factors.get('h2h_avg_ht_goals','?')} 球")
    lines.append(f"   2020+ {factors.get('h2h_3y_count','?')}场 (过期{factors.get('h2h_expired',0)}场)  |  0-0: {factors.get('ft_0_0_count',0)}场")
    lines.append(f"   进球热区: 0-10分 {_pct(tb.get('0_10',0))} | 11-30分 {_pct(tb.get('11_30',0))} | 11-45分 {_pct(tb.get('11_45',0))}")
    lines.append(f"            16-30分 {_pct(tb.get('16_30',0))} | 16-45分 {_pct(tb.get('16_45',0))} | 31-45分 {_pct(tb.get('31_45',0))}")
    lines.append(f"   回调适配: {factors.get('pullback_fit','-')} | 11-45压力 {_pct(factors.get('late_fh_pressure',0))}"
                 f"{' | 开场闪击型' if factors.get('early_only_flag') else ''}")
    lines.append(f"   下半场:   46-60分 {_pct(sh_tb.get('46_60',0))} | 61-75分 {_pct(sh_tb.get('61_75',0))} | 76-90分 {_pct(sh_tb.get('76_90',0))}")

    # ⚡ 近期动能
    lines.append("")
    lines.append("⚡ 【近期动能 (近5场)】")
    lines.append(f"   {home}: HT有球率 {_pct(factors.get('home_recent_ht_over',0))}"
                 f" | 场均 {factors.get('home_recent_avg_goals','?')} 球 {_heat_bar(factors.get('home_recent_ht_over',0))}")
    lines.append(f"   {away}: HT有球率 {_pct(factors.get('away_recent_ht_over',0))}"
                 f" | 场均 {factors.get('away_recent_avg_goals','?')} 球 {_heat_bar(factors.get('away_recent_ht_over',0))}")
    lines.append(f"   综合动能: {_pct(factors.get('recent_form_avg',0))}")
    lines.append(f"   {home}: HT进球 {_pct(factors.get('home_recent_ht_scored',0))} / HT失球 {_pct(factors.get('home_recent_ht_conceded',0))}")
    lines.append(f"   {away}: HT进球 {_pct(factors.get('away_recent_ht_scored',0))} / HT失球 {_pct(factors.get('away_recent_ht_conceded',0))}")
    lines.append(f"   攻防组合: 主攻客防 {_pct(factors.get('home_attack_vs_away_defense',0))}"
                 f" | 客攻主防 {_pct(factors.get('away_attack_vs_home_defense',0))}"
                 f" | 最强 {_pct(factors.get('ht_attack_vs_defense',0))}")
    lines.append(f"   下半场动能: {_pct(factors.get('recent_sh_avg',0))}"
                 f" | H2H下半场有球 {_pct(factors.get('h2h_sh_goal_rate',0))}"
                 f" | FT2+ {_pct(factors.get('h2h_ft_over_1_5_rate',0))}")

    # 🏟 联赛基准
    lines.append("")
    lines.append("🏟 【联赛基准】")
    lines.append(f"   HT环境: {baseline.get('ht_env','-')} | HT有球 {_pct(baseline.get('ht_goal_rate',0))}"
                 f" | SH有球 {_pct(baseline.get('sh_goal_rate',0))}"
                 f" | FT2+ {_pct(baseline.get('ft_over_1_5_rate',0))}")
    lines.append(f"   样本: {baseline.get('sample_size',0)} | 置信度: {baseline.get('confidence','-')}"
                 f" | 调整: {baseline_adj.get('action','-')} ({baseline_adj.get('reason','-')})")

    # 🗓 赛季阶段
    lines.append("")
    lines.append("🗓 【赛季阶段】")
    lines.append(f"   阶段: {season_phase.get('phase','-')} | 进度 {_pct(season_phase.get('progress_pct',0))}"
                 f" | 已完 {season_phase.get('completed',0)}/{season_phase.get('total',0)}"
                 f" | 剩余约 {season_phase.get('remaining_rounds_est','-')} 轮")
    lines.append(f"   调整: {phase_adj.get('action','-')} ({phase_adj.get('reason','-')})")

    # 🎯 排名战意
    lines.append("")
    lines.append("🎯 【排名战意】")
    lines.append(f"   闸门: {motivation_gate.get('action','-')} | 分数 {motivation_gate.get('score','-')}"
                 f" | {motivation_gate.get('reason','-')}")
    lines.append(f"   {home}: #{home_mot.get('rank','-')} {home_mot.get('points','-')}分"
                 f" | {', '.join(home_mot.get('tags', []) or ['-'])}")
    lines.append(f"   {away}: #{away_mot.get('rank','-')} {away_mot.get('points','-')}分"
                 f" | {', '.join(away_mot.get('tags', []) or ['-'])}")

    # 🧭 赛程压力
    lines.append("")
    lines.append("🧭 【未来三场赛程压力】")
    lines.append(f"   闸门: {schedule_pressure.get('action','-')} | 等级 {schedule_pressure.get('level','-')}"
                 f" | {schedule_pressure.get('reason','-')}")
    lines.append(f"   {home}: 7天内 {home_sched.get('games_next_7d','-')} 场"
                 f" | 最短间隔 {home_sched.get('min_gap_days','-')} 天")
    lines.append(f"   {away}: 7天内 {away_sched.get('games_next_7d','-')} 场"
                 f" | 最短间隔 {away_sched.get('min_gap_days','-')} 天")

    # ⚖️ 庄家阵地
    lines.append("")
    lines.append("⚖️ 【庄家盘口阵地 (HT)】")
    if ht_lines:
        for ln in ht_lines:
            lines.append(f"   大{ln.get('line','?')} @{ln.get('over','-')}")
    else:
        lines.append("   ❓ 暂无")

    # 🚦 战力红绿灯
    lines.append("")
    lines.append("🚦 【战力红绿灯】")
    lines.append(f"   {home}: {get_injury_traffic_light(home, injury.get('home', {}))}")
    lines.append(f"   {away}: {get_injury_traffic_light(away, injury.get('away', {}))}")
    if lineup_gate:
        lines.append(f"   首发闸门: {lineup_gate.get('lineup_action','-')} | {lineup_gate.get('lineup_reason','-')}")
        for label, side in ((home, lineup_gate.get("home", {}) or {}), (away, lineup_gate.get("away", {}) or {})):
            if side.get("lineup_signal") in ("LINEUP_PENDING", "LINEUP_UNKNOWN"):
                lines.append(f"   {label}: {side.get('lineup_signal')} | {side.get('warning','-')}")
            else:
                lines.append(f"   {label}: 攻核 {side.get('attack_core_present','-')}/{side.get('attack_core_count','-')}"
                             f" | 防核 {side.get('defense_core_present','-')}/{side.get('defense_core_count','-')}"
                             f" | {side.get('attack_signal','-')}/{side.get('defense_signal','-')}")

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

    has_high = any(float(str(ln["line"])) >= 1.25 for ln in ht_lines)
    if has_high and late_goal > 0.5:
        lines.append("   ⏱ 庄家高开+慢热画像 → 滚球潜伏良机")
    elif has_high:
        lines.append("   ⏱ 庄家高开 → 赛前直打风险偏高")
    if factors.get("phase_bias") == "SECOND_HALF_BIAS":
        lines.append("   🔁 进球明显偏下半场 → 这类场次优先看下半场/全场，不硬追上半场")

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
