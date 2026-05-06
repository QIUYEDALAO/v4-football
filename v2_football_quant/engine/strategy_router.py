"""
V2-V4 多策略路由中心 (Strategy Router)
负责将每天扫描到的比赛，根据赛事级别、数据可用性，分发到最匹配的量化定价模型。
"""
from logger import logger

# ---------------------------------------------------------
# 常量定义：联赛分组字典 (API-Football IDs)
# ---------------------------------------------------------
WORLD_CUP_ID = [1]  # 世界杯的 API-Football ID 通常是 1（实盘前需二次确认）

TOP_5_LEAGUES = [
    39,   # 英超 Premier League
    140,  # 西甲 La Liga
    78,   # 德甲 Bundesliga
    135,  # 意甲 Serie A
    61    # 法甲 Ligue 1
]

# ---------------------------------------------------------
# 占位模型 (Stubs)
# ---------------------------------------------------------
def evaluate_v2_ht_draw(fixture: dict):
    """
    V2 模型: 半场平局错杀狙击 (当前生产环境主力)
    目标: 非五大联赛的次级市场
    """
    fix_id = fixture.get("fixture", {}).get("id")
    # 这里的实际运算逻辑现在依然躺在 daily_runner 里，
    # 等下周纸盘结束后，我们会把 calc_edge 逻辑整体搬移到这里。
    return {"model": "v2", "status": "mock_routed"}


def evaluate_v3_world_cup(fixture: dict):
    """
    V3 模型: 世界杯 Elo/身价认知套利
    目标: 杯赛散户情绪盘
    """
    fix_id = fixture.get("fixture", {}).get("id")
    logger.info(f"[{fix_id}] 路由匹配 -> [V3 World Cup] 引擎 (待开发)")
    return None


def evaluate_v4_top5_xg(fixture: dict):
    """
    V4 模型: 五大联赛 xG 均值回归
    目标: 高流动性红海市场的高阶数据套利
    """
    fix_id = fixture.get("fixture", {}).get("id")
    logger.info(f"[{fix_id}] 路由匹配 -> [V4 xG Top5] 引擎 (待开发)")

    # 核心降级逻辑 (Fallback) 预留：
    # if not xg_data_is_available():
    #     logger.warning(f"[{fix_id}] xG 数据缺失，降级至 V2 引擎")
    #     return evaluate_v2_ht_draw(fixture)

    return None


# ---------------------------------------------------------
# 主路由分发器
# ---------------------------------------------------------
def route_and_evaluate(fixture: dict):
    """
    根据比赛的联赛 ID 和数据条件，动态路由到最佳盈利模型

    Returns:
        Dict: 包含下注建议的字典，如果没有 Edge 则返回 None
    """
    league_id = fixture.get("league", {}).get("id")

    if league_id in WORLD_CUP_ID:
        return evaluate_v3_world_cup(fixture)

    elif league_id in TOP_5_LEAGUES:
        return evaluate_v4_top5_xg(fixture)

    else:
        # 默认回退：全部交给 V2 处理（如日职联、沙特联、荷甲等）
        return evaluate_v2_ht_draw(fixture)


# ---------------------------------------------------------
# 单元测试 (绝不污染生产环境)
# ---------------------------------------------------------
if __name__ == "__main__":
    print("🧪 启动 Strategy Router 路由沙盘推演...\n")

    mock_fixtures = [
        {"league": {"id": 39, "name": "Premier League"}, "fixture": {"id": 10001, "name": "Arsenal vs Chelsea"}},
        {"league": {"id": 1, "name": "World Cup"}, "fixture": {"id": 10002, "name": "Brazil vs Switzerland"}},
        {"league": {"id": 98, "name": "J1 League"}, "fixture": {"id": 10003, "name": "Vissel Kobe vs Urawa Reds"}}
    ]

    for fx in mock_fixtures:
        league_name = fx["league"]["name"]
        league_id = fx["league"]["id"]
        result = route_and_evaluate(fx)
        route_table = {
            1: "V3 World Cup",
            39: "V4 xG Top5",
            98: "V2 HT Draw"
        }
        model = route_table.get(league_id, "V2 HT Draw (fallback)")
        print(f"  {league_name} (ID={league_id}) → [{model}] → result={result}")

    print("\n✅ 路由逻辑测试完成。")
    print("  英超 → V4 · 世界杯 → V3 · 日职联 → V2")
    print("  降级 Fallback 预留 · V2 不受影响")
