"""
V2 纸盘验证与结算模块 (HT 1X2 架构)
======================================
1. 解析昨日预测记录
2. 拉取真实半场赛果，计算 H/D/A 标签
3. 拉取 Pinnacle 最终收盘赔率，计算 True CLV
4. 结算 PnL 并更新日志

用法：
  python3 paper_trading.py --verify 2026-05-05   # 验证指定日期的预测
  python3 paper_trading.py --test-clv             # 用首战数据测试CLV计算
  python3 paper_trading.py --summary              # 全量汇总
"""

import json
import ssl
import time
import urllib.request
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict
from typing import Optional, Dict, Tuple, List

from logger import logger

API_KEY = "你的API-KEY请替换"
API_HOST = "https://v3.football.api-sports.io"

BASE_DIR = Path("/Users/chenguoqing/.openclaw/workspace/v2_football_quant")
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
REPORT_DIR.mkdir(exist_ok=True)
LOG_DIR = BASE_DIR / "data" / "paper_trading"
LOG_DIR.mkdir(exist_ok=True)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ═══════════════════════════════════════════════════════════
# API 工具
# ═══════════════════════════════════════════════════════════

def api(endpoint: str) -> Optional[dict]:
    url = f"{API_HOST}/{endpoint}"
    req = urllib.request.Request(url, headers={"x-apisports-key": API_KEY})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return None


# ═══════════════════════════════════════════════════════════
# Step 1: 赛果解析器 (Result Parser)
# ═══════════════════════════════════════════════════════════

def parse_ht_result(halftime_score: str) -> Optional[str]:
    """
    将 "1-1" 这种字符串解析为 HT 1X2 的赛果标签。

    Returns:
        "H" | "D" | "A" | None (无效输入)
    """
    if not halftime_score or halftime_score == "None":
        return None
    try:
        home_goals, away_goals = map(int, halftime_score.strip().split('-'))
        if home_goals > away_goals:
            return "H"
        elif home_goals == away_goals:
            return "D"
        else:
            return "A"
    except Exception as e:
        logger.error(f"解析半场比分失败: '{halftime_score}' -> {e}")
        return None


def ht_has_goal(halftime_score: str) -> Optional[bool]:
    """兼容旧V38逻辑：半场是否有进球"""
    if not halftime_score or halftime_score == "None":
        return None
    try:
        home_goals, away_goals = map(int, halftime_score.strip().split('-'))
        return (home_goals + away_goals) > 0
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# Step 2: 盈亏结算中心 (PnL Settlement)
# ═══════════════════════════════════════════════════════════

def settle_trade(stake: float, placed_odds: float, bet_outcome: str,
                 actual_outcome: str) -> Tuple[float, bool]:
    """
    计算净盈亏。

    Returns:
        (profit, is_hit): 净利润和是否命中
    """
    if actual_outcome == bet_outcome:
        return stake * (placed_odds - 1), True
    else:
        return -stake, False


# ═══════════════════════════════════════════════════════════
# Step 3: True CLV 计算器 (Vig-Free CLV)
# ═══════════════════════════════════════════════════════════

def calculate_true_clv(placed_odds: float, outcome: str,
                       closing_odds: Dict[str, float]) -> Tuple[float, float]:
    """
    基于 Pinnacle HT 1X2 收盘赔率计算 True CLV（去水收盘线价值）。

    核心逻辑：
      1. 计算三向隐含概率总和（margin = 庄家抽水）
      2. 去水 → 还原真实公平概率
      3. 计算公平收盘赔率
      4. CLV = placed_odds / fair_closing_odds - 1

    Args:
        placed_odds: 我们下注的赔率 (例如 3.05)
        outcome: 我们下注的方向 ("H", "D", "A")
        closing_odds: {"H": 8.19, "D": 3.12, "A": 1.60}

    Returns:
        (true_clv, fair_closing_odds)
    """
    if not closing_odds or not all(k in closing_odds for k in ("H", "D", "A")):
        return 0.0, 0.0

    # 1. 计算隐含概率总和 (Overround / Margin)
    inv_h = 1.0 / closing_odds["H"]
    inv_d = 1.0 / closing_odds["D"]
    inv_a = 1.0 / closing_odds["A"]
    margin = inv_h + inv_d + inv_a

    # 2. 去水，计算公平概率
    target_closing_odds = closing_odds[outcome]
    true_prob = (1.0 / target_closing_odds) / margin

    # 3. 计算公平收盘赔率（即无庄家利润的赔率）
    fair_closing_odds = 1.0 / true_prob

    # 4. 计算 CLV
    true_clv = (placed_odds / fair_closing_odds) - 1.0

    return true_clv, fair_closing_odds


def extract_pinnacle_ht_1x2(odds_response: dict) -> Dict[str, float]:
    """
    从 API odds 响应中提取 Pinnacle 的 HT 1X2 (First Half Winner) 收盘赔率。

    Returns:
        {"H": 8.19, "D": 3.12, "A": 1.60} or {}
    """
    if not odds_response or not odds_response.get("response"):
        return {}

    for entry in odds_response["response"]:
        for bm in entry.get("bookmakers", []):
            if "Pinnacle" not in bm.get("name", ""):
                continue
            for bet in bm.get("bets", []):
                if bet["name"] == "First Half Winner":
                    odds_map = {}
                    for v in bet.get("values", []):
                        val = v["value"].lower()
                        if val == "home":
                            odds_map["H"] = float(v["odd"])
                        elif val == "draw":
                            odds_map["D"] = float(v["odd"])
                        elif val == "away":
                            odds_map["A"] = float(v["odd"])
                    if len(odds_map) == 3:
                        return odds_map
    return {}


# ═══════════════════════════════════════════════════════════
# 验证流水线
# ═══════════════════════════════════════════════════════════

def verify_date(date_str: str) -> dict:
    """
    验证指定日期的所有预测。

    流程:
      1. 读取 predictions_{date}.json
      2. 逐场拉取 API 实际赛果 + Pinnacle 收盘赔率
      3. 解析 H/D/A 赛果
      4. 结算 PnL
      5. 计算 True CLV
      6. 汇总输出
    """
    pred_path = REPORT_DIR / f"predictions_{date_str.replace('-', '')}.json"
    if not pred_path.exists():
        return {"error": f"预测文件不存在: {pred_path}"}

    with open(pred_path, encoding="utf-8") as f:
        predictions = json.load(f)

    results = []
    total_staked = 0.0
    total_pnl = 0.0
    hits = 0
    clv_list = []

    for i, pred in enumerate(predictions):
        fid = pred.get("fixture_id", pred.get("id"))
        bet_outcome = pred.get("outcome", pred.get("bet"))  # "H"|"D"|"A"
        placed_odds = pred.get("placed_odds", pred.get("odds", 0))
        stake = pred.get("stake", 0)
        league = pred.get("league", "")
        home = pred.get("home", "")
        away = pred.get("away", "")

        # --- 拉取实际赛果 ---
        resp = api(f"fixtures?id={fid}")
        if not resp or not resp.get("response"):
            logger.warning(f"[{fid}] API 无响应，跳过")
            continue

        fix = resp["response"][0]
        status = fix["fixture"]["status"]["short"]

        # 等完赛
        if status not in ("FT", "AET", "PEN", "WO"):
            logger.warning(f"[{fid}] 比赛未完赛 ({status})，跳过")
            continue

        ht = fix["score"]["halftime"]
        ht_home = ht.get("home") if ht.get("home") is not None else 0
        ht_away = ht.get("away") if ht.get("away") is not None else 0
        ht_str = f"{ht_home}-{ht_away}"

        # --- Step 1: 赛果解析 ---
        actual_outcome = parse_ht_result(ht_str)
        if not actual_outcome:
            continue

        # --- 拉取 Pinnacle 收盘赔率 ---
        odds_resp = api(f"odds?fixture={fid}")
        closing_ht_1x2 = extract_pinnacle_ht_1x2(odds_resp)

        # --- Step 3: CLV 计算 ---
        true_clv, fair_close = calculate_true_clv(placed_odds, bet_outcome, closing_ht_1x2)
        clv_list.append(true_clv)

        # --- Step 2: PnL 结算 ---
        pnl, is_hit = settle_trade(stake, placed_odds, bet_outcome, actual_outcome)
        if is_hit:
            hits += 1
        total_staked += stake
        total_pnl += pnl

        r = {
            "fixture_id": fid,
            "home": home,
            "away": away,
            "league": league,
            "bet_outcome": bet_outcome,
            "placed_odds": placed_odds,
            "stake": stake,
            "ht_score": ht_str,
            "actual_outcome": actual_outcome,
            "is_hit": is_hit,
            "pnl": round(pnl, 2),
            "closing_ht_1x2": closing_ht_1x2,
            "fair_closing_odds": round(fair_close, 4),
            "true_clv": round(true_clv, 4),
            "ht_has_goal": (ht_home + ht_away) > 0,
        }
        results.append(r)

        logger.info(
            f"[{fid}] {home} v {away} | "
            f"HT:{ht_str} | 投:{bet_outcome} | 赛:{actual_outcome} | "
            f"PnL:{pnl:+.2f} | CLV:{true_clv*100:+.2f}%"
            f"{' ✅' if is_hit else ' ❌'}"
        )

        time.sleep(1.0)  # API 限频

    # --- 汇总 ---
    avg_clv = sum(clv_list) / len(clv_list) if clv_list else 0.0
    roi_pct = (total_pnl / total_staked * 100) if total_staked > 0 else 0.0
    completed = len(results)

    summary = {
        "date": date_str,
        "verified_at": datetime.now().isoformat(),
        "total_predicted": len(predictions),
        "total_completed": completed,
        "pending": len(predictions) - completed,
        "hits": hits,
        "misses": completed - hits,
        "hit_rate_pct": round(hits / completed * 100, 1) if completed else 0.0,
        "total_staked": round(total_staked, 2),
        "total_pnl": round(total_pnl, 2),
        "roi_pct": round(roi_pct, 2),
        "avg_clv_pct": round(avg_clv * 100, 2),
        "results": results,
    }

    # --- 保存 ---
    log_path = LOG_DIR / f"verified_{date_str.replace('-', '')}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"验证完成: {date_str} | {hits}/{completed} 命中 | "
                f"ROI:{roi_pct:+.1f}% | CLV:{avg_clv*100:+.2f}% | "
                f"→ 已存 {log_path}")

    return summary


# ═══════════════════════════════════════════════════════════
# 全量汇总
# ═══════════════════════════════════════════════════════════

def full_summary():
    """汇总所有纸盘验证数据"""
    logs = sorted(LOG_DIR.glob("verified_*.json"))
    if not logs:
        return {"error": "无验证日志"}

    all_results = []
    for log_path in logs:
        with open(log_path) as f:
            data = json.load(f)
        all_results.extend(data.get("results", []))

    if not all_results:
        return {"error": "无结果数据"}

    total_bets = len(all_results)
    hits = sum(1 for r in all_results if r.get("is_hit"))
    total_pnl = sum(r.get("pnl", 0) for r in all_results)
    total_staked = sum(r.get("stake", 0) for r in all_results)

    # 按联赛分组
    by_league = defaultdict(lambda: {"bets": 0, "hits": 0, "pnl": 0.0, "clv": []})
    for r in all_results:
        lg = r.get("league", "Unknown")
        by_league[lg]["bets"] += 1
        if r.get("is_hit"):
            by_league[lg]["hits"] += 1
        by_league[lg]["pnl"] += r.get("pnl", 0)
        by_league[lg]["clv"].append(r.get("true_clv", 0))

    # 按CLV分组
    by_clv = defaultdict(lambda: {"bets": 0, "hits": 0, "pnl": 0.0})
    for r in all_results:
        clv = r.get("true_clv", 0)
        if clv > 0.05:
            bucket = "CLV > +5%"
        elif clv > 0:
            bucket = "CLV 0~+5%"
        elif clv > -0.05:
            bucket = "CLV -5%~0"
        else:
            bucket = "CLV < -5%"
        by_clv[bucket]["bets"] += 1
        if r.get("is_hit"):
            by_clv[bucket]["hits"] += 1
        by_clv[bucket]["pnl"] += r.get("pnl", 0)

    return {
        "total_days": len(logs),
        "total_bets": total_bets,
        "hits": hits,
        "hit_rate_pct": round(hits / total_bets * 100, 1),
        "total_staked": round(total_staked, 2),
        "total_pnl": round(total_pnl, 2),
        "roi_pct": round(total_pnl / total_staked * 100, 2) if total_staked else 0,
        "avg_clv_pct": round(
            sum(r.get("true_clv", 0) for r in all_results) / total_bets * 100, 2
        ) if total_bets else 0,
        "by_league": {
            lg: {
                "bets": d["bets"],
                "hits": d["hits"],
                "hit_rate": round(d["hits"] / d["bets"] * 100, 1),
                "pnl": round(d["pnl"], 2),
                "avg_clv": round(sum(d["clv"]) / len(d["clv"]) * 100, 2) if d["clv"] else 0,
            }
            for lg, d in sorted(by_league.items(), key=lambda x: -x[1]["bets"])
        },
        "by_clv_bucket": {
            b: {"bets": d["bets"], "hits": d["hits"],
                "hit_rate": round(d["hits"] / d["bets"] * 100, 1) if d["bets"] else 0,
                "pnl": round(d["pnl"], 2)}
            for b, d in sorted(by_clv.items())
        },
    }


# ═══════════════════════════════════════════════════════════
# 测试：首战 CLV 验算
# ═══════════════════════════════════════════════════════════

def test_clv():
    """用 Al Khaleej vs Al Hilal 首战数据测试 CLV 计算"""
    print("=" * 55)
    print("🧪 True CLV 单元测试")
    print("  Al Khaleej vs Al Hilal | HT: 1-1 (Draw)")
    print("=" * 55)

    # --- 测试 parse_ht_result ---
    assert parse_ht_result("1-1") == "D", f"FAIL: 1-1 → 应该 D, 得到 {parse_ht_result('1-1')}"
    assert parse_ht_result("2-0") == "H"
    assert parse_ht_result("0-1") == "A"
    assert parse_ht_result("0-0") == "D"
    assert parse_ht_result(None) is None
    print("✅ parse_ht_result: 全部通过")

    # --- 测试 settle_trade ---
    profit, hit = settle_trade(42, 3.05, "D", "D")
    assert abs(profit - 86.1) < 0.01, f"Profit expected 86.1, got {profit}"
    assert hit is True
    profit, hit = settle_trade(42, 3.05, "D", "H")
    assert abs(profit - (-42)) < 0.01, f"Profit expected -42, got {profit}"
    assert hit is False
    print(f"✅ settle_trade: 命中→+{86.1}, 未中→-42")

    # --- 测试 calculate_true_clv ---
    closing = {"H": 8.19, "D": 3.12, "A": 1.60}
    placed = 3.05

    # 手工计算验证
    inv_h = 1/8.19; inv_d = 1/3.12; inv_a = 1/1.60
    margin = inv_h + inv_d + inv_a
    fair_draw = 1.0 / ((1.0 / 3.12) / margin)
    expected_clv = (3.05 / fair_draw) - 1.0

    true_clv, fair_close = calculate_true_clv(placed, "D", closing)
    print(f"\n📊 Pinnacle 收盘: H={closing['H']}, D={closing['D']}, A={closing['A']}")
    print(f"   Margin (Overround): {margin:.4f} ({(margin-1)*100:.2f}%)")
    print(f"   公平 Draw 收盘赔率: {fair_close:.4f} (期望: {fair_draw:.4f})")
    print(f"   True CLV: {true_clv*100:+.2f}% (期望: {expected_clv*100:+.2f}%)")

    assert abs(true_clv - expected_clv) < 0.0001, \
        f"CLV mismatch: {true_clv:.6f} vs expected {expected_clv:.6f}"
    assert abs(fair_close - fair_draw) < 0.0001
    print(f"✅ calculate_true_clv: {true_clv*100:+.2f}% 与手工计算一致")

    # --- 测试 extract_pinnacle_ht_1x2 ---
    mock_odds = {
        "response": [{
            "bookmakers": [{
                "name": "Pinnacle",
                "bets": [{
                    "name": "First Half Winner",
                    "values": [
                        {"value": "Home", "odd": "8.19"},
                        {"value": "Draw", "odd": "3.12"},
                        {"value": "Away", "odd": "1.60"},
                    ]
                }]
            }]
        }]
    }
    extracted = extract_pinnacle_ht_1x2(mock_odds)
    assert extracted == {"H": 8.19, "D": 3.12, "A": 1.60}
    print(f"✅ extract_pinnacle_ht_1x2: 正确提取三向赔率")

    # --- 完整流程模拟 ---
    print(f"\n--- 完整流程模拟 ---")
    ht_str = "1-1"
    actual = parse_ht_result(ht_str)
    pnl, is_hit = settle_trade(42, 3.05, "D", actual)
    clv, fair = calculate_true_clv(3.05, "D", closing)

    print(f"  HT: {ht_str} → {actual}")
    print(f"  投注: D @ 3.05 × 42u")
    print(f"  PnL: {pnl:+.2f}u {'✅' if is_hit else '❌'}")
    print(f"  CLV: {clv*100:+.2f}%")
    print(f"  结论: {'Alpha真实' if clv > 0 else '方差/运气 (CLV<0)'}")

    print(f"\n{'=' * 55}")
    print(f"✅ 所有测试通过 — paper_trading.py V2 就绪")
    print(f"{'=' * 55}")


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if "--test-clv" in sys.argv:
        test_clv()

    elif "--verify" in sys.argv:
        idx = sys.argv.index("--verify")
        dt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else date.today().isoformat()
        print(f"🔍 验证 {dt} 的预测...")
        result = verify_date(dt)
        if "error" in result:
            print(f"  ⚠️ {result['error']}")
        else:
            print(f"  ✅ {result['hits']}/{result['total_completed']} 命中 | "
                  f"ROI {result['roi_pct']:+.2f}% | CLV {result['avg_clv_pct']:+.2f}%")
            if result["pending"] > 0:
                print(f"  ⏳ {result['pending']} 场等待完赛")

    elif "--summary" in sys.argv:
        s = full_summary()
        if "error" in s:
            print(f"⚠️ {s['error']}")
        else:
            print(f"\n📊 纸盘总汇: {s['total_days']}天 {s['total_bets']}场")
            print(f"命中率: {s['hit_rate_pct']}% | PnL: {s['total_pnl']:+.2f}u")
            print(f"ROI: {s['roi_pct']:+.2f}% | 平均CLV: {s['avg_clv_pct']:+.2f}%")
            if s.get("by_clv_bucket"):
                print(f"\n按CLV分桶:")
                for b, d in s["by_clv_bucket"].items():
                    print(f"  {b}: {d['bets']}场 | {d['hits']}中({d['hit_rate']}%) | PnL{d['pnl']:+.2f}")
            if s.get("by_league"):
                print(f"\n按联赛:")
                for lg, d in list(s["by_league"].items())[:10]:
                    print(f"  {lg}: {d['bets']}场 | {d['hit_rate']}% | PnL{d['pnl']:+.2f} | CLV{d['avg_clv']:+.2f}%")

    else:
        print("用法:")
        print("  python3 paper_trading.py --test-clv          # 单元测试 CLV 计算")
        print("  python3 paper_trading.py --verify 2026-05-05 # 验证指定日期")
        print("  python3 paper_trading.py --summary           # 全量汇总")
