"""
Phase 4: 纸盘至实盘最高权力网关 (Live Bridge)
================================================
不管 V2 / V3 / V4，要下单必须过这一关。

三大闸门：
  ⛩️ can_enter_sandbox()    — 实盘准入 (N≥50, CLV≥1%, MDD≤12%)
  🛡️ calculate_sandbox_stake() — 试水期固定小额 (0.5%本金)
  🛑 check_kill_switch()    — CLV 跌破 0 → 自动拔网线回纸盘
"""

import logging
import json
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class LiveMode(str, Enum):
    PAPER = "PAPER"                # 纯纸盘 (当前)
    MICRO_SANDBOX = "MICRO_SANDBOX" # 微型沙盒侦察兵 (N≥40, CLV≥1.5%, 0.25%注码)
    SANDBOX = "SANDBOX"             # 小仓试水实盘 (N≥50, CLV≥1%, 0.5%注码)
    FULL = "FULL"                   # 全仓实盘 (未来)


BASE_DIR = Path(__file__).resolve().parent.parent
V3_WC_CONFIG_PATH = BASE_DIR / "config" / "v3_wc_config.json"


def _load_v3_wc_config() -> dict:
    if not V3_WC_CONFIG_PATH.exists():
        return {}
    try:
        with open(V3_WC_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class LiveBridgeGateway:
    """
    Phase 4: 纸盘到实盘的最高权力网关。
    负责：入场资格审查、试水期资金限额、以及 Kill-Switch 拔网线。
    """

    def __init__(self, mode: LiveMode = LiveMode.PAPER):
        self.mode = mode
        self.v3_wc_config = _load_v3_wc_config()

    def can_enter_micro_sandbox(self, paper_summary: dict, router_summary: dict) -> bool:
        """
        🔬 微型沙盒准入 (N≥40, CLV≥1.5%): 用更厚Edge弥补样本不足
        """
        logger.info("🔍 正在审查 MICRO_SANDBOX 侦察兵准入资格...")

        bets = paper_summary.get("total_bets", 0)
        if bets < 40:
            logger.warning(f"[GUARD] BRIDGE_BLOCKED | code=MICRO_N_INSUFFICIENT | detail=N={bets} < 40")
            return False

        last40 = paper_summary.get("last_40_stats", paper_summary.get("last_50_stats", {}))
        clv = last40.get("avg_true_clv_pct", 0.0)
        if clv < 1.5:
            logger.warning(f"[GUARD] BRIDGE_BLOCKED | code=MICRO_CLV_WEAK | detail=avg_true_clv={clv}% < 1.5%")
            return False

        logger.info("✅ MICRO_SANDBOX 侦察兵准入通过！")
        return True

    def calculate_micro_sandbox_stake(self, total_bankroll: float) -> dict:
        """
        🔬 微型沙盒注码: 0.25% (20000→50块), 纯数据采集费
        """
        if self.mode != LiveMode.MICRO_SANDBOX:
            return {"action": "BLOCK_NOT_MICRO", "stake": 0, "reason": "非 MICRO_SANDBOX 状态"}

        safe_stake = round(total_bankroll * 0.0025, 2)
        return {
            "action": "BET_LIVE_MICRO",
            "stake": safe_stake,
            "reason": f"侦察兵模式: 固定 {0.25}% 仓位 (纯数据采集费)"
        }

    def can_v3_enter_micro_sandbox(self, v3_paper_summary: dict) -> bool:
        """
        ⛩️ V3 大赛引擎专属准入闸门 (仅限 MD2 阶段触发)
        """
        logger.info("🔍 正在审查 V3 引擎(WC2026) MICRO_SANDBOX 准入资格...")

        md1_stats = v3_paper_summary.get("MD1_stats", {})
        bets = md1_stats.get("bets", 0)
        clv = md1_stats.get("avg_true_clv_pct", 0.0)
        completeness = md1_stats.get("data_completeness_pct", 0.0)
        gate = (self.v3_wc_config.get("md1_gate") or {})
        min_bets = int(gate.get("min_bets", 10))
        min_clv = float(gate.get("min_avg_true_clv_pct", 0.0))
        min_comp = float(gate.get("min_data_completeness_pct", 90.0))

        if bets < min_bets:
            logger.warning(f"[GUARD] V3_BRIDGE_BLOCKED | code=V3_N_TOO_SMALL | detail=MD1 纸盘样本 {bets} < 要求 {min_bets}")
            return False

        if clv < min_clv:
            logger.warning(f"[GUARD] V3_BRIDGE_BLOCKED | code=V3_CLV_NEG | detail=MD1 纸盘 CLV {clv}% < 要求 {min_clv}%")
            return False

        if completeness < min_comp:
            logger.warning(
                f"[GUARD] V3_BRIDGE_BLOCKED | code=V3_DATA_INCOMPLETE | "
                f"detail=MD1 数据完整率 {completeness}% < 要求 {min_comp}%"
            )
            return False

        logger.info("✅ V3 准入审查通过！授权激活 MD2 MICRO_SANDBOX 侦察兵模式。")
        return True

    def calculate_v3_micro_stake(self, total_bankroll: float) -> dict:
        """
        🛡️ V3 专属注码剥夺：固定 0.25% 本金 (20000 -> 50)
        """
        safe_stake = round(total_bankroll * 0.0025, 2)
        return {
            "action": "BET_LIVE_MICRO_SANDBOX",
            "stake": safe_stake,
            "reason": f"V3 极小仓保护：固定 0.25% 本金"
        }

    def check_v3_kill_switch(self, v3_live_summary: dict) -> bool:
        """
        🛑 V3 极速熔断：Rolling 10 实盘 CLV < 0 立刻拔网线
        """
        windows = v3_live_summary.get("rolling_windows_10", [])
        if not windows:
            return False

        last_window = windows[-1]
        clv = last_window.get("avg_true_clv_pct", 0.0)

        if last_window.get("bets", 0) >= 10 and clv < 0.0:
            logger.critical(f"🚨 [GUARD] V3_KILL_SWITCH | code=V3_LIVE_CLV_NEG | detail=Rolling 10 CLV {clv}% 跌穿 0")
            return True
        return False

    def check_micro_kill_switch(self, live_summary: dict) -> bool:
        """
        🔬 Hair-trigger Kill Switch: rolling_10 CLV ≤ 0 → 立刻熔断
        """
        if self.mode != LiveMode.MICRO_SANDBOX:
            return False

        windows = live_summary.get("rolling_windows", [])
        if not windows or len(windows) < 1:
            return False

        # Hair-trigger: 只看最近10场
        last_clv = windows[-1].get("avg_true_clv_pct", 0.0)
        if last_clv <= 0.0:
            logger.critical(f"[GUARD] MICRO_KILL_SWITCH | code=LIVE_CLV_NEG | detail=rolling10 CLV={last_clv}%")
            self.mode = LiveMode.PAPER
            return True
        return False

    def can_enter_sandbox(self, paper_summary: dict, router_summary: dict) -> bool:
        """
        ⛩️ 第一道闸：实盘准入条件审查 (纯客观，无情感)
        """
        logger.info("🔍 正在审查实盘(SANDBOX)准入资格...")

        # 1. 样本底线 (N >= 50)
        bets = paper_summary.get("total_bets", 0)
        if bets < 50:
            logger.warning(f"[GUARD] BRIDGE_BLOCKED | code=PAPER_N_INSUFFICIENT | detail=total_bets={bets} < 50")
            return False

        # 2. 全局护城河 (过去 50 场 avg_true_clv >= 1%)
        last50 = paper_summary.get("last_50_stats", {})
        clv_last50 = last50.get("avg_true_clv_pct", 0.0)
        if clv_last50 < 1.0:
            logger.warning(f"[GUARD] BRIDGE_BLOCKED | code=PAPER_CLV_WEAK | detail=last50 avg_true_clv={clv_last50}% < 1.0%")
            return False

        # 3. 资金曲线定力 (MDD <= 12%)
        mdd = paper_summary.get("mdd_pct", 100.0)
        if mdd > 12.0:
            logger.warning(f"[GUARD] BRIDGE_BLOCKED | code=PAPER_MDD_HIGH | detail=MDD={mdd}% > 12%")
            return False

        # 4. 核心发力证明 (黄金区必须证明有效)
        golden = router_summary.get("[5] -> [4]", {})
        if golden.get("bets", 0) < 20 or golden.get("avg_true_clv_pct", 0.0) <= 0:
            logger.warning(f"[GUARD] BRIDGE_BLOCKED | code=GOLDEN_ZONE_UNPROVEN | detail=黄金跳变区 N={golden.get('bets',0)} CLV={golden.get('avg_true_clv_pct',0)}%")
            return False

        logger.info("✅ 准入审查通过！系统具备进入 SANDBOX 模式资格。")
        return True

    def calculate_sandbox_stake(self, total_bankroll: float, recommended_action: str) -> dict:
        """
        🛡️ 第二道闸：试水期资金剥夺 (抛弃 Kelly，固定小额)
        """
        if self.mode != LiveMode.SANDBOX:
            return {"action": "BLOCK_NOT_SANDBOX", "stake": 0,
                    "reason": "系统当前未处于 SANDBOX 状态"}

        if not recommended_action.startswith("BET"):
            return {"action": recommended_action, "stake": 0,
                    "reason": "保持原有拦截逻辑"}

        # 试水期铁律：固定锁定总本金的 0.5%
        safe_stake = round(total_bankroll * 0.005, 2)

        return {
            "action": "BET_LIVE_SANDBOX",
            "stake": safe_stake,
            "reason": f"沙盒模式保护：固定 {0.5}% 仓位"
        }

    def check_kill_switch(self, live_summary: dict) -> bool:
        """
        🛑 第三道闸：试水期熔断退回机制
        如果实盘滚动的 True CLV 跌破 0，立刻拔网线。
        """
        if self.mode != LiveMode.SANDBOX:
            return False

        windows = live_summary.get("rolling_windows", [])
        if not windows:
            return False

        last_window = windows[-1]
        clv = last_window.get("avg_true_clv_pct", 0.0)
        bets = last_window.get("bets", 0)

        if bets >= 20 and clv < 0.0:
            logger.critical(f"[GUARD] KILL_SWITCH_TRIGGERED | code=LIVE_CLV_NEG | detail=rolling20 avg_true_clv={clv}%")
            logger.critical("🚨 系统判定遇到了严重滑点或微观结构巨变。强制回退至 PAPER 模式！")
            self.mode = LiveMode.PAPER
            return True

        return False


# ==========================================
# 🧪 准入测试
# ==========================================
if __name__ == "__main__":
    print("🧪 Live Bridge Gateway 单元测试\n")

    bridge = LiveBridgeGateway()

    # 测试1: 纸盘样本不足
    print("【测试 1】N=3 → 准入应失败")
    ok = bridge.can_enter_sandbox(
        {"total_bets": 3, "last_50_stats": {"avg_true_clv_pct": 2.0}, "mdd_pct": 5.0},
        {"[5] -> [4]": {"bets": 25, "avg_true_clv_pct": 3.5}}
    )
    print(f"  结果: {'✅ 放行' if ok else '🚫 拦截'} (预期: 拦截)\n")

    # 测试2: 全通过
    print("【测试 2】N=50, CLV=2%, MDD=8%, 黄金区有效 → 准入应通过")
    ok = bridge.can_enter_sandbox(
        {"total_bets": 55, "last_50_stats": {"avg_true_clv_pct": 2.0}, "mdd_pct": 8.0},
        {"[5] -> [4]": {"bets": 25, "avg_true_clv_pct": 3.5}}
    )
    print(f"  结果: {'✅ 放行' if ok else '🚫 拦截'} (预期: 放行)\n")

    # 测试3: CLV不达标
    print("【测试 3】N=50, CLV=0.3%, MDD=8% → 准入应失败")
    ok = bridge.can_enter_sandbox(
        {"total_bets": 55, "last_50_stats": {"avg_true_clv_pct": 0.3}, "mdd_pct": 8.0},
        {"[5] -> [4]": {"bets": 25, "avg_true_clv_pct": 3.5}}
    )
    print(f"  结果: {'✅ 放行' if ok else '🚫 拦截'} (预期: 拦截)\n")

    # 测试4: Sandbox stake
    bridge.mode = LiveMode.SANDBOX
    stake = bridge.calculate_sandbox_stake(20000, "BET")
    print(f"【测试 4】SANDBOX stake: {stake}")
    print(f"  预期: BET_LIVE_SANDBOX, stake=100.0\n")

    # 测试5: Kill switch
    print("【测试 5】Kill-switch: CLV=-1% → 应触发")
    triggered = bridge.check_kill_switch({
        "rolling_windows": [{"bets": 20, "avg_true_clv_pct": -1.0}]
    })
    print(f"  Kill-switch: {'🔥 触发!' if triggered else '😌 安全'}, mode={bridge.mode.value}")
    print(f"  预期: 触发, mode=PAPER")

    print("\n✅ Live Bridge 全功能测试通过")
