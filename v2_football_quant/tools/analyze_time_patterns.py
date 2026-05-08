"""
三频时序形态分类器 (Time-Pattern Classifier)
=============================================
基于 AM0800 / NOON1200 / PM1600 的平赔快照，自动分类每场比赛的微观结构形态。

形态类型:
  FLAT        — 全程死水，庄家懒得调盘 (低流动性联赛)
  ACCELERATE  — 趋势确认，欧洲资金进场放大亚洲偏移
  MEAN_REVERT — 均值回归，午间偏移是假动作/噪音
  MOMENTUM    — 单向延续，早盘偏移被下午维持

用法:
  python3 tools/analyze_time_patterns.py
"""

import json
from pathlib import Path
from collections import defaultdict, Counter

BASE_DIR = Path(__file__).resolve().parent.parent
SCAN_PATH = BASE_DIR / "data" / "daily_reports"

NOISE_THRESHOLD = 0.02


def classify_time_pattern(odds_08, odds_12, odds_16):
    """基于三频快照的微观结构形态分类器"""
    if not (odds_08 and odds_12 and odds_16):
        return "INCOMPLETE"

    delta_1 = odds_12 - odds_08
    delta_2 = odds_16 - odds_12
    total_delta = odds_16 - odds_08

    # 全场未动
    if abs(total_delta) <= NOISE_THRESHOLD and abs(delta_1) <= NOISE_THRESHOLD:
        return "FLAT"

    # 均值回归：午间偏移被下午拉回
    if (delta_1 * delta_2 < 0) and (abs(delta_1) > NOISE_THRESHOLD or abs(delta_2) > NOISE_THRESHOLD):
        if abs(odds_16 - odds_08) <= NOISE_THRESHOLD:
            return "MEAN_REVERT"

    # 趋势加速：同一方向且下午幅度 >= 上午
    if delta_1 * delta_2 > 0 and abs(delta_2) >= abs(delta_1) and abs(total_delta) > NOISE_THRESHOLD:
        return "ACCELERATE"

    # 单向延续：上午偏移被下午维持但未加速
    if abs(total_delta) > NOISE_THRESHOLD:
        return "MOMENTUM"

    return "UNKNOWN"


def analyze(date_str=None):
    """分析指定日期的 full_scan"""
    if date_str is None:
        from datetime import date as dt
        date_str = dt.today().strftime("%Y%m%d")

    scan_file = SCAN_PATH / f"full_scan_{date_str}.json"
    if not scan_file.exists():
        print(f"❌ {scan_file} 不存在")
        return

    with open(scan_file) as f:
        scan = json.load(f)

    candidates = scan.get("candidates", [])

    # 三频索引
    by_id = {}
    for c in candidates:
        fid = c["fixture_id"]
        if fid not in by_id:
            by_id[fid] = {}
        by_id[fid][c.get("scan_tag", "?")] = c

    # 分类
    patterns = []
    for fid, tags in by_id.items():
        if all(t in tags for t in ["AM0800", "NOON1200", "PM1600"]):
            am = tags["AM0800"]
            noon = tags["NOON1200"]
            pm = tags["PM1600"]
            d8 = am.get("offered_odds_D")
            d12 = noon.get("offered_odds_D")
            d16 = pm.get("offered_odds_D")
            if not all([d8, d12, d16]):
                continue

            pattern = classify_time_pattern(d8, d12, d16)
            patterns.append({
                "fixture_id": fid,
                "home": am.get("home", "?"),
                "away": am.get("away", "?"),
                "league": am.get("league_name", "?"),
                "odds_0800": d8,
                "odds_1200": d12,
                "odds_1600": d16,
                "delta_am_pm": round(d16 - d8, 2),
                "time_pattern": pattern,
            })

    # 统计
    total = len(patterns)
    pattern_counts = Counter(p["time_pattern"] for p in patterns)
    league_patterns = defaultdict(lambda: defaultdict(int))
    for p in patterns:
        league_patterns[p["league"]][p["time_pattern"]] += 1

    print("=" * 65)
    print(f"📊 三频时序形态分类 | {date_str} | N={total}")
    print("=" * 65)
    print(f"\n全局分布: {dict(pattern_counts)}")
    print(f"  FLAT (死水): {pattern_counts.get('FLAT',0)} 场 — 庄家懒得动")
    print(f"  ACCELERATE (加速): {pattern_counts.get('ACCELERATE',0)} 场 — 欧洲加码")
    print(f"  MOMENTUM (延续): {pattern_counts.get('MOMENTUM',0)} 场 — 维持趋势")
    print(f"  MEAN_REVERT (回归): {pattern_counts.get('MEAN_REVERT',0)} 场 — 午间假动作")

    # 联赛 × 形态矩阵
    print(f"\n🏆 联赛×形态交叉矩阵:")
    print(f"{'联赛':<14} | {'N':>3} | {'FLAT':>4} | {'ACCEL':>4} | {'MOMEN':>4} | {'REVRT':>4}")
    print("-" * 55)
    for lg in sorted(league_patterns, key=lambda x: -sum(league_patterns[x].values())):
        cnts = league_patterns[lg]
        n = sum(cnts.values())
        f = cnts.get("FLAT", 0)
        a = cnts.get("ACCELERATE", 0)
        m = cnts.get("MOMENTUM", 0)
        r = cnts.get("MEAN_REVERT", 0)
        flag = ""
        if n >= 3:
            accel_pct = (a + m) / n * 100
            if accel_pct >= 60:
                flag = " ⚠️ 延迟开火候选"
            if f / n >= 0.8:
                flag = " ✅ 08:00锁仓安全"
        print(f"{lg:<14} | {n:>3} | {f:>4} | {a:>4} | {m:>4} | {r:>4}{flag}")

    # 列出 ACCELERATE 细节
    accel = [p for p in patterns if p["time_pattern"] == "ACCELERATE"]
    if accel:
        print(f"\n🔥 ACCELERATE 加速场次:")
        print(f"{'比赛':<35} {'08:00':>6} {'16:00':>6} {'Δ':>6}")
        for p in sorted(accel, key=lambda x: -abs(x["delta_am_pm"])):
            delta_str = f"{p['delta_am_pm']:+.2f}"
            print(f'{p["home"][:16]} vs {p["away"][:14]:<14} {p["odds_0800"]:>6.2f} {p["odds_1600"]:>6.2f} {delta_str:>6}')

    # MEAN_REVERT 细节
    revert = [p for p in patterns if p["time_pattern"] == "MEAN_REVERT"]
    if revert:
        print(f"\n🔄 MEAN_REVERT 均值回归 (午间假动作):")
        for p in revert:
            print(f'  {p["home"]} vs {p["away"]}: {p["odds_0800"]}→{p["odds_1200"]}→{p["odds_1600"]}')


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    analyze(date_arg)
