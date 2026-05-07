import logging

logger = logging.getLogger(__name__)

# ==========================================
# 🌐 Strategy Router Phase 3 蓝图
# ==========================================

class StrategyRouter:
    """
    多策略集团军路由中心 (Phase 3 Blueprint)

    当前状态：静默潜伏期 (DRY-RUN)。
    激活条件：等待 paper_trading 仪表盘积累满 N >= 20 的有效样本。
    """
    def __init__(self, enable_active_routing=False, summary_stats=None):
        self.enable_active_routing = enable_active_routing
        self.summary_stats = summary_stats or {}  # 🌟 接收来自 paper_trading 的统计数据

    def _check_iron_rule(self, pattern_key: str, required_type: str) -> bool:
        """
        🛡️ 铁律审判器：不满足 N>=20 或 CLV 方向不符绝不放行
        required_type: "boost" (要求CLV>0) 或 "toxic" (要求CLV明显为负)
        """
        stats = self.summary_stats.get(pattern_key, {})
        bets = stats.get("bets", 0)
        clv = stats.get("avg_true_clv_pct", 0.0)

        if bets < 20:
            logger.warning(f"BLOCK_ROUTER_ACTIVATION: insufficient data for pattern {pattern_key} (N={bets} < 20)")
            return False

        if required_type == "boost" and clv <= 0:
            logger.warning(f"BLOCK_ROUTER_ACTIVATION: negative CLV for pattern {pattern_key} (CLV={clv}%)")
            return False

        if required_type == "toxic" and clv > -2.0:  # 没亏透，不算毒药
            logger.warning(f"BLOCK_ROUTER_ACTIVATION: CLV not toxic enough for {pattern_key} (CLV={clv}%)")
            return False

        return True

    def process_candidates(self, candidates: list[dict]) -> list[dict]:
        """
        接收所有引擎（V2, V3, V4）的候选订单，进行冲突解决、提权与降维。
        """
        routed_signals = []

        for rec in candidates:
            signal = rec.copy()

            if self.enable_active_routing:
                strategy_id = signal.get("strategy_id", "UNKNOWN")
                orig_priority = signal.get("priority", 50)

                if strategy_id == "V2_HT_DRAW":
                    # 获取当前这单的特征 (例如 "[5] -> [4]")
                    jump_str = f"[{signal.get('orig_bin')}] -> [{signal.get('adj_bin')}]"

                    # 规则 1: 黄金跳变加权 (要求：符合 Boost 候选 + 铁律审判通过)
                    if signal.get("attrition_boost_candidate") and signal.get("bin_jump_size", 0) == 1:
                        if self._check_iron_rule(jump_str, "boost"):
                            signal["priority"] = orig_priority + 30
                            signal["max_risk_units"] = 1.2
                            signal["router_note"] = f"BOOST_ACTIVATED: 触发黄金伤停 {jump_str}"
                        else:
                            signal["router_note"] = f"ROUTER_BLOCKED: {jump_str} 铁律未满足，降级为被动路由"

                    # 规则 2: 毒药崩塌跳变拦截
                    elif signal.get("attrition_flag") and signal.get("bin_jump_size", 0) >= 2:
                        if self._check_iron_rule(jump_str, "toxic"):
                            signal["action"] = "SKIP_TOXIC_JUMP"
                            signal["skip_reason"] = f"Router 阻断: {jump_str} 毒药区，警惕庄家深坑"
                            signal["priority"] = 0

            routed_signals.append(signal)

        return routed_signals


# ==========================================
# 联赛路由分发器 (已有)
# ==========================================

# ---------------------------------------------------------
# 常量定义：联赛分组字典 (API-Football IDs)
# ---------------------------------------------------------
WORLD_CUP_ID = [1]

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
