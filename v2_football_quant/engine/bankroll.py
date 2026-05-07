"""
仓位管理模块 v0.1
===================
遵循 P0 红线：半Kelly / 1/4 Kelly，绝不 Full Kelly

Kelly公式：f* = (bp - q) / b
  b = 赔率-1
  p = 预测胜率
  q = 1-p
  f* = 最优仓位比例

半Kelly：f = f* / 2
1/4 Kelly：f = f* / 4（保守，适合高波动）

应用：单注金额 = 本金 * f，上限 300，下限 100
"""

import math
from dataclasses import dataclass

@dataclass
class Bankroll:
    principal: float = 20000.0  # 本金
    current: float = 20000.0    # 当前余额
    daily_count: int = 0        # 今日已投场次
    unit_max: float = 1000.0    # 单注安全帽 (5%本金)
    unit_min: float = 100.0     # 单注底注 (动态底限, Kelly不足则跳过)
    stop_loss_pct: float = 0.3   # 硬熔断: -30% → 亏6000强制停机
    max_drawdown_pct: float = 0.15  # 软熔断: -15% → 亏3000减半注
    
    peak: float = 20000.0       # 历史最高余额


def kelly_fraction(p: float, odds: float, kelly_factor: float = 0.25) -> float:
    """
    Kelly 仓位比例.
    
    Args:
        p: 预测胜率 (0-1)
        odds: 十进制赔率
        kelly_factor: 0.25=1/4Kelly, 0.5=半Kelly, 1.0=FullKelly(禁止)
    
    Returns:
        仓位比例 (0-1)
    """
    if odds <= 1 or p <= 0:
        return 0.0
    
    b = odds - 1  # 净赔率
    q = 1 - p
    
    f_star = (b * p - q) / b
    f_star = max(0.0, f_star)  # 不做负期望值的投注
    
    return f_star * kelly_factor


def _kelly_factor_for_drawdown(drawdown: float) -> float:
    """阶梯式 Kelly 熔断函数 (为未来多档位扩展留好后路)"""
    if drawdown > 0.30:
        return 0.0   # 30% 硬熔断停机
    if drawdown > 0.15:
        return 0.125 # 15% 软熔断降级 (1/8)
    # 预留未来中间档位: if drawdown > 0.10: return 0.1667
    return 0.25       # 正常 1/4 Kelly


def calculate_stake(bankroll: Bankroll, p: float, odds: float) -> dict:
    """
    计算下注金额，强制返回 Kelly 思考元数据 (Task 1)
    
    Returns:
        {"action": "BET"|"SKIP_*", "stake": float, "reason": str,
         "raw_kelly": float, "effective_kelly": float, "kelly_factor_used": float}
    """
    drawdown = (bankroll.peak - bankroll.current) / bankroll.peak

    # 获取 Kelly 系数 (阶梯熔断)
    kf = _kelly_factor_for_drawdown(drawdown)
    if kf == 0.0:
        return {
            "action": "SKIP_MELTDOWN", "stake": 0, "reason": "回撤>30%触发硬熔断",
            "raw_kelly": 0.0, "effective_kelly": 0.0, "kelly_factor_used": 0.0
        }

    # 计算原始 Kelly
    f_star = ((odds - 1) * p - (1 - p)) / (odds - 1) if odds > 1 else 0.0
    raw_k = round(max(0.0, f_star), 4)  # 过滤负数，报表更干净

    if f_star <= 0:
        return {
            "action": "SKIP_NO_EDGE", "stake": 0, "reason": "数学 Edge 极弱或为负",
            "raw_kelly": raw_k, "effective_kelly": 0.0, "kelly_factor_used": kf
        }

    stake_raw = bankroll.current * f_star * kf
    final_stake = min(bankroll.unit_max, stake_raw)

    # 动态获取底注限制，告别硬编码 100
    min_unit = getattr(bankroll, "unit_min", 100.0)

    if final_stake < min_unit:
        return {
            "action": "SKIP_LOW_KELLY", "stake": 0,
            "reason": f"计算仓位 {round(final_stake, 2)} < 底注 {min_unit}",
            "raw_kelly": raw_k, "effective_kelly": round(f_star * kf, 4), "kelly_factor_used": kf
        }

    return {
        "action": "BET", "stake": round(final_stake, 2), "reason": "PASS",
        "raw_kelly": raw_k, "effective_kelly": round(f_star * kf, 4), "kelly_factor_used": kf
    }


def update_bankroll(bankroll: Bankroll, stake: float, won: bool, odds: float):
    """更新余额"""
    if won:
        bankroll.current += stake * (odds - 1)
    else:
        bankroll.current -= stake
    
    bankroll.daily_count += 1
    
    if bankroll.current > bankroll.peak:
        bankroll.peak = bankroll.current


def reset_daily(bankroll: Bankroll):
    """每日重置投注计数"""
    bankroll.daily_count = 0


# ===== 熔断状态机 =====
class CircuitBreaker:
    """简单熔断器：连续N场亏损触发"""
    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self.consecutive_losses = 0
        self.open = False
    
    def record(self, won: bool):
        if won:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
        
        if self.consecutive_losses >= self.threshold:
            self.open = True
    
    def reset(self):
        self.consecutive_losses = 0
        self.open = False


if __name__ == "__main__":
    br = Bankroll()
    
    # 测试：60% 预测胜率，赔率 1.85
    stake = calculate_stake(br, 0.60, 1.85)
    print(f"Kelly 1/4: f*=0.25 → 单注 {stake}")
    print(f"本金 {br.principal}, 当前 {br.current}")
    
    # 模拟回撤
    br.current = 1400
    br.peak = 2000
    stake2 = calculate_stake(br, 0.60, 1.85)
    print(f"\n回撤 {(2000-1400)/2000*100:.0f}%后: 单注 {stake2}")
    
    br.current = 1100
    stake3 = calculate_stake(br, 0.60, 1.85)
    print(f"回撤 {(2000-1100)/2000*100:.0f}%后: 单注 {stake3} (熔断)")

    # 连续亏损熔断
    cb = CircuitBreaker(5)
    for i in range(6):
        cb.record(False)
        print(f"  连亏 {i+1}, 熔断={cb.open}")
