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
    principal: float = 2000.0  # 本金
    current: float = 2000.0    # 当前余额
    daily_count: int = 0       # 今日已投场次
    unit_max: float = 300.0    # 单注上限（绝对安全帽）
    stop_loss_pct: float = 0.4  # 熔断：回撤 > 40% 全停
    max_drawdown_pct: float = 0.25  # 软熔断：回撤 > 25% 减半注
    
    peak: float = 2000.0       # 历史最高余额


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


def calculate_stake(bankroll: Bankroll, p: float, odds: float) -> dict:
    """
    计算单注金额 (返回决策字典)。
    
    规则：
    1. 用 1/4 Kelly 算理论仓位
    2. 只设上限安全帽 (300)，绝不设下限逼空
    3. Kelly 算得 < 100 → SKIP_LOW_KELLY（宁可不下，绝不超配）
    4. 回撤 > 25% 减半，回撤 > 40% 熔断
    
    Returns:
        {"action": "BET"|"SKIP_*", "stake": float, "reason": str}
    """
    # 检查熔断
    drawdown = (bankroll.peak - bankroll.current) / bankroll.peak
    if drawdown > bankroll.stop_loss_pct:
        return {"action": "SKIP_MELTDOWN", "stake": 0, "reason": f"回撤 {drawdown*100:.1f}% > {bankroll.stop_loss_pct*100:.0f}% 熔断"}
    
    kf = 0.25  # 1/4 Kelly
    if drawdown > bankroll.max_drawdown_pct:
        kf = 0.125  # 减半
    
    f = kelly_fraction(p, odds, kf)
    stake_raw = bankroll.current * f
    
    # 极低价值过滤：stake < 10 则不投，避免噪音交易
    if stake_raw < 10.0:
        return {"action": "SKIP_NOISE", "stake": 0, "reason": f"Kelly 仓位 {stake_raw:.1f} < 10，噪音跳过"}
    
    # 纯粹 Kelly：只设上限安全帽，不设下限
    # 🔴 关键修改：绝不用 clamp 把 35 块强行抬到 100 块
    raw_stake = min(bankroll.unit_max, stake_raw)
    
    if raw_stake < 100:
        return {"action": "SKIP_LOW_KELLY", "stake": 0, 
                "reason": f"Kelly建议 {raw_stake:.0f} < {100} 下限，放弃此单（宁可不下绝不超配）"}
    
    return {"action": "BET", "stake": round(raw_stake, 2), "reason": "Kelly 正常"}


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
