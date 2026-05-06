"""
V3 世界杯模型: Elo + 身价认知套利引擎
======================================
核心假设:
1. Elo 分差 → 基准胜率 (唯一数学依据)
2. 身价偏差 → 公众认知泡沫 (Perception Gap)
3. 淘汰赛 + 保守主帅 → 平局概率上修

零依赖 API-Football 近期数据，纯靠客观实力指标定价。
"""

import json
import math
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data" / "deep"

# 暂时导入估值数据 (后续整合到 JSON)
import sys
sys.path.insert(0, str(BASE_DIR / "data_sources"))
from team_values import TEAM_MARKET_VALUES as VALUES, get_value_rank
from elo_scraper import fetch_elo_ratings

# 保守主帅 = 淘汰赛阶段平局概率加成 (人工标注)
CONSERVATIVE_MANAGERS = {
    "FR": 8, "EN": 7, "HR": 8, "DK": 7, "CH": 7,
    "RS": 6, "PL": 6, "IR": 8, "DE": 5, "IT": 7, "PT": 6,
}
DEFAULT_CONSERVATIVE = 4

# 淘汰赛平局修正系数
KO_DRAW_BOOST = 0.08


def load_wc_elo() -> dict:
    """加载或抓取 W杯球队 Elo"""
    path = DATA_DIR / "wc2026_elo.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        return {t["code"]: t for t in data.get("teams", [])}
    ratings = fetch_elo_ratings()
    # 过滤WC参赛队
    from elo_scraper import WC2026_TEAMS
    return {c: r for c, r in ratings.items() if c in WC2026_TEAMS}


def elo_to_win_prob(elo_a: float, elo_b: float) -> tuple:
    """
    Elo → 胜率转换 (标准 400 分差公式)
    
    返回: (home_win, draw, away_win) 概率三元组
    """
    diff = elo_a - elo_b
    # 主队胜率 (含主场优势 ~100 Elo)
    we = 1.0 / (math.pow(10, -diff / 400) + 1)
    
    # 平局概率估算 (基于 Elo 分差)
    draw = max(0.15, 0.30 - abs(diff) / 1500)
    
    # 分配剩余概率
    home_win = we * (1 - draw)
    away_win = (1 - we) * (1 - draw)
    
    return round(home_win, 4), round(draw, 4), round(away_win, 4)


def calc_perception_gap(home_code: str, away_code: str) -> float:
    """
    公众认知偏差指数 (Perception Gap)
    
    正值 = 散户过度看好主队 (主队名气 > 实力)
    负值 = 散户过度看好客队
    """
    elo = load_wc_elo()
    
    elo_h = elo.get(home_code, {}).get("rating", 1500)
    elo_a = elo.get(away_code, {}).get("rating", 1500)
    val_h = VALUES.get(home_code, 1.0)
    val_a = VALUES.get(away_code, 1.0)
    
    # Elo差 vs 身价差的比值 — 比值偏离1越大, 认知偏差越大
    if val_a == 0:
        return 0.0
    
    elo_ratio = elo_h / max(elo_a, 1)
    val_ratio = val_h / max(val_a, 0.1)
    
    # 正值 = 人气溢价 (散户多买主队)
    gap = round(val_ratio / max(elo_ratio, 0.5) - 1, 4)
    return gap


def calc_ft_draw_edge(
    home_code: str, away_code: str, 
    market_odds: dict = None,
    stage: str = "group",
) -> dict | None:
    """
    V3 全场平局分析 (世界杯专用)
    
    Args:
        market_odds: {"H": 2.50, "D": 3.20, "A": 2.80} 或 None (理论值)
        stage: "group" | "ko16" | "ko8" | "final"
    
    Returns:
        Edge 分析结果, 或 None (无信号)
    """
    elo = load_wc_elo()
    elo_h = elo.get(home_code, {}).get("rating", 1500)
    elo_a = elo.get(away_code, {}).get("rating", 1500)
    
    # 1. Elo 基准概率
    hw, draw_prob, aw = elo_to_win_prob(elo_h, elo_a)
    
    # 2. 淘汰赛平局加成
    if stage != "group":
        h_mgr = CONSERVATIVE_MANAGERS.get(home_code, DEFAULT_CONSERVATIVE)
        a_mgr = CONSERVATIVE_MANAGERS.get(away_code, DEFAULT_CONSERVATIVE)
        mgr_boost = (h_mgr + a_mgr) / 20 * KO_DRAW_BOOST
        draw_prob = min(0.50, draw_prob + mgr_boost)
    
    # 3. Perception Gap — 公众情绪套利
    gap = calc_perception_gap(home_code, away_code)
    
    # 4. Edge vs 市场
    if market_odds and "D" in market_odds:
        implied_prob = 1 / market_odds["D"]
        edge = draw_prob - implied_prob
    else:
        edge = None  # 无市场赔率，仅输出理论概率
    
    result = {
        "home": elo.get(home_code, {}).get("name", home_code),
        "away": elo.get(away_code, {}).get("name", away_code),
        "elo_h": elo_h, "elo_a": elo_a,
        "draw_prob": round(draw_prob, 4),
        "stage": stage,
        "perception_gap": gap,
        "perception_gap_label": (
            "🔥 散户重度做多主队" if gap > 0.5 else
            "⚠️ 散户偏多主队" if gap > 0.2 else
            "均衡" if abs(gap) < 0.2 else
            "⚠️ 散户偏多客队"
        ),
    }
    
    if market_odds and "D" in market_odds:
        result["market_odds"] = market_odds["D"]
        result["edge"] = round(edge, 4)
        result["action"] = "BUY DRAW" if edge > 0.05 else "PASS"
    
    return result


def strategy_a_underdog_ah(home_code: str, away_code: str) -> dict | None:
    """
    策略 A: 受让亚盘套利
    
    当 Perception Gap 极高时 (散户疯狂买强队) → 买入弱队亚洲盘
    """
    gap = calc_perception_gap(home_code, away_code)
    elo = load_wc_elo()
    
    home_name = elo.get(home_code, {}).get("name", home_code)
    away_name = elo.get(away_code, {}).get("name", away_code)
    elo_h = elo.get(home_code, {}).get("rating", 1500)
    elo_a = elo.get(away_code, {}).get("rating", 1500)
    
    # 散户溢价方向判断
    if gap > 0.5:  # 散户过度买主队
        target = "away"
        target_name = away_name
        handicap = "+1.5" if abs(elo_h - elo_a) > 200 else "+1.25"
    elif gap < -0.3:  # 散户过度买客队
        target = "home"
        target_name = home_name
        handicap = "+1.5" if abs(elo_h - elo_a) > 200 else "+1.25"
    else:
        return None  # Gap不够大
    
    return {
        "home": home_name, "away": away_name,
        "perception_gap": gap,
        "target": target, "target_name": target_name,
        "handicap": handicap,
        "action": f"BUY {target_name} AH {handicap}",
    }


# ==========================================
# 🎯 V3 阶段防火墙 (Stage Firewall)
# ==========================================

def evaluate_wc_fixture(home_code: str, away_code: str, stage: str = "group",
                        market_odds: dict = None) -> dict | None:
    """
    V3 世界杯终极路由：基于回测数据的阶段隔离策略
    
    回测依据（2022世界杯）:
    - 小组赛 AH: 8/12 = 66.7%  (弱队摆大巴抢分)
    - 淘汰赛 AH: 2/9  = 22.2%  (强队打穿深盘)
    - 淘汰赛 Draw: 4/10 = 40%  (顶级强队互啄)
    """
    KO_STAGES = ["ko16", "ko8", "qf", "sf", "semi", "final", "3rd"]
    
    if stage == "group":
        return strategy_a_underdog_ah(home_code, away_code)
    elif stage in KO_STAGES:
        return calc_ft_draw_edge(home_code, away_code, market_odds, stage)
    return None


# ==========================================
# 🧪 测试
# ==========================================
if __name__ == "__main__":
    print("🧪 V3 W杯模型 沙盘推演\n")
    
    # 测试1: 小组赛
    print("=== 测试1: 小组赛 英格兰 vs 日本 ===")
    r = calc_ft_draw_edge("EN", "JP", stage="group")
    print(f"  平局概率: {r['draw_prob']:.1%}")
    print(f"  认知偏差: {r['perception_gap_label']} (gap={r['perception_gap']:.2f})")
    
    # 测试2: 淘汰赛 (保守主帅对决)
    print("\n=== 测试2: 淘汰赛 法国 vs 克罗地亚 ===")
    r2 = calc_ft_draw_edge("FR", "HR", stage="ko16")
    print(f"  平局概率: {r2['draw_prob']:.1%}")
    print(f"  阶段加成: {'是' if r2['draw_prob'] > 0.28 else '否'}")
    
    # 测试3: 策略A 亚盘套利
    print("\n=== 测试3: 亚盘套利 英格兰 vs 日本 ===")
    a = strategy_a_underdog_ah("EN", "JP")
    if a:
        print(f"  {a['action']}")
        print(f"  Gap={a['perception_gap']:.2f}")
    else:
        print("  无信号 (Gap不足)")
    
    # 测试4: 巴西 vs 阿根廷
    print("\n=== 测试4: 巴西 vs 阿根廷 ===")
    r4 = calc_ft_draw_edge("BR", "AR", stage="final")
    print(f"  平局概率: {r4['draw_prob']:.1%}")
    print(f"  认知偏差: {r4['perception_gap_label']}")
    
    print("\n✅ V3 模型沙盘测试完成")
