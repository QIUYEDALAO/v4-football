"""
纸盘验证日志系统 v1.0 (P2-3)
==============================
每天赛后自动对比预测 vs 实际结果，记录真实 ROI。

用法：
  python3 paper_trading.py --verify 2026-05-05   # 验证指定日期的预测
  python3 paper_trading.py --summary              # 全量汇总
"""

import json
import ssl
import time
import urllib.request
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict

API_KEY = "e5e315b1f9ba1ba51dc2124b35f07a01"
API_HOST = "https://v3.football.api-sports.io"

BASE_DIR = Path("/Users/chenguoqing/.openclaw/workspace/v2_football_quant")
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
LOG_DIR = BASE_DIR / "data" / "paper_trading"
LOG_DIR.mkdir(exist_ok=True)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def api(endpoint: str) -> dict | None:
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


def verify_date(date_str: str) -> dict:
    """
    验证指定日期的预测结果。
    
    1. 读取 predictions_{date}.json
    2. 对每场拉取实际赛果
    3. 对比，记录命中率 + ROI
    """
    pred_path = REPORT_DIR / f"predictions_{date_str.replace('-', '')}.json"
    if not pred_path.exists():
        return {"error": f"预测文件不存在: {pred_path}"}

    with open(pred_path) as f:
        predictions = json.load(f)

    results = []
    hit_count = 0
    total_bets = len(predictions)

    for i, pred in enumerate(predictions):
        fid = pred["fixture_id"]
        
        # 获取实际赛果
        resp = api(f"fixtures?id={fid}")
        if not resp or not resp.get("response"):
            continue
        
        fix = resp["response"][0]
        status = fix["fixture"]["status"]["short"]
        ht = fix["score"]["halftime"]
        ht_goals = (ht["home"] or 0) + (ht["away"] or 0)
        
        # 等待完赛
        if status not in ("FT", "AET", "PEN"):
            # 如果比赛还没打完，跳过
            continue
        
        actual_hit = 1 if ht_goals > 0 else 0
        if actual_hit:
            hit_count += 1

        odds = pred.get("odds")
        profit = (odds - 1) if actual_hit else -1  # 按赔率算盈亏

        results.append({
            "fixture_id": pred["fixture_id"],
            "home": pred["home"],
            "away": pred["away"],
            "league": pred["league"],
            "score": pred["score"],
            "meets_v38": pred["meets_v38"],
            "odds": odds,
            "actual_ht_home": ht["home"] or 0,
            "actual_ht_away": ht["away"] or 0,
            "actual_ht_goals": ht_goals,
            "actual_hit": actual_hit,
            "profit_1u": round(profit, 2),
            "status": status,
        })
        
        time.sleep(1.0)

    # 汇总
    total_profit = sum(r["profit_1u"] for r in results)
    hit_rate = hit_count / len(results) * 100 if results else 0
    roi = total_profit / len(results) * 100 if results else 0

    summary = {
        "date": date_str,
        "verified_at": datetime.now().isoformat(),
        "total_predicted": total_bets,
        "total_completed": len(results),
        "pending": total_bets - len(results),
        "hits": hit_count,
        "misses": len(results) - hit_count,
        "hit_rate": round(hit_rate, 1),
        "total_profit": round(total_profit, 2),
        "roi_pct": round(roi, 1),
        "results": results,
        "by_league": defaultdict(lambda: {"bets": 0, "hits": 0, "profit": 0.0}),
    }

    for r in results:
        lg = r["league"]
        summary["by_league"][lg]["bets"] += 1
        if r["actual_hit"]:
            summary["by_league"][lg]["hits"] += 1
        summary["by_league"][lg]["profit"] += r["profit_1u"]

    # 转 dict 保存
    summary["by_league"] = dict(summary["by_league"])

    # 保存
    log_path = LOG_DIR / f"verified_{date_str.replace('-', '')}.json"
    with open(log_path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def full_summary():
    """汇总所有纸盘数据"""
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
    hits = sum(1 for r in all_results if r["actual_hit"])
    total_profit = sum(r["profit_1u"] for r in all_results)
    hit_rate = hits / total_bets * 100
    roi = total_profit / total_bets * 100

    # 按联赛分组
    by_league = defaultdict(lambda: {"bets": 0, "hits": 0, "profit": 0.0})
    for r in all_results:
        lg = r["league"]
        by_league[lg]["bets"] += 1
        if r["actual_hit"]:
            by_league[lg]["hits"] += 1
        by_league[lg]["profit"] += r["profit_1u"]

    # 滚动窗口 ROI
    rolling = []
    window = 20
    for i in range(0, total_bets, window):
        chunk = all_results[i:i + window]
        if len(chunk) < window:
            break
        profit = sum(r["profit_1u"] for r in chunk)
        rolling.append({
            "start": chunk[0]["fixture_id"],
            "end": chunk[-1]["fixture_id"],
            "bets": len(chunk),
            "profit": round(profit, 2),
            "roi": round(profit / len(chunk) * 100, 1),
        })

    return {
        "total_days": len(logs),
        "total_bets": total_bets,
        "hits": hits,
        "hit_rate": round(hit_rate, 1),
        "total_profit": round(total_profit, 2),
        "roi_pct": round(roi, 1),
        "by_league": {lg: {"bets": d["bets"], "hits": d["hits"],
                           "hit_rate": round(d["hits"] / d["bets"] * 100, 1),
                           "profit": round(d["profit"], 2)}
                      for lg, d in sorted(by_league.items(), key=lambda x: -x[1]["bets"])},
        "rolling_roi": rolling,
    }


if __name__ == "__main__":
    import sys

    if "--verify" in sys.argv:
        idx = sys.argv.index("--verify")
        dt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else date.today().isoformat()
        print(f"验证 {dt} 的预测...")
        result = verify_date(dt)
        if "error" in result:
            print(f"  ⚠️ {result['error']}")
        else:
            print(f"  ✅ {result['hits']}/{result['total_completed']} 命中, "
                  f"ROI {result['roi_pct']:+.1f}%")
            if result["pending"] > 0:
                print(f"  ⏳ {result['pending']} 场等待完赛")

    elif "--summary" in sys.argv:
        s = full_summary()
        if "error" in s:
            print(f"⚠️ {s['error']}")
        else:
            print(f"纸盘总汇: {s['total_days']}天 {s['total_bets']}场")
            print(f"命中率: {s['hit_rate']}%, 盈亏: {s['total_profit']:+.1f}u, ROI: {s['roi_pct']:+.1f}%")
            print(f"\n按联赛:")
            for lg, d in s["by_league"].items():
                print(f"  {lg}: {d['hits']}/{d['bets']} ({d['hit_rate']}%), 盈亏 {d['profit']:+.1f}u")
            print(f"\n滚动窗口 ROI:")
            for w in s["rolling_roi"]:
                print(f"  窗口{w['start']}-{w['end']}: {w['roi']:+.1f}%")

    else:
        print("用法:")
        print("  python3 paper_trading.py --verify 2026-05-05")
        print("  python3 paper_trading.py --summary")
