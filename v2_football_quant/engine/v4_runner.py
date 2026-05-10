"""
V4 勘探线扫描器 (纸盘模式)
============================
每天独立运行，不与 daily_runner 冲突。
前置漏斗: 只查白名单联赛 + 12h 内开赛 → 避免 API 洪峰。

用法:
  python3 engine/v4_runner.py
  python3 engine/v4_runner.py --run_tag=AM0800

输出: data/daily_reports/predictions_v4_YYYYMMDD.json
"""

import json, ssl, certifi, time, sys
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.secrets import API_KEY, API_HOST
from engine.data_sources.h2h_engine import evaluate_h2h_edge
from engine.strategy_router import StrategyRouter
from logger import logger

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
REPORT_DIR.mkdir(exist_ok=True)

# SSL
ctx = ssl.create_default_context(cafile=certifi.where())

# 白名单
with open(BASE_DIR / "config" / "leagues_whitelist.json") as f:
    LEAGUE_CN = json.load(f)["leagueId"]

WL_SET = set(str(k) for k in LEAGUE_CN.keys())


def api_get(endpoint: str):
    url = f"{API_HOST}/{endpoint}"
    req = urllib.request.Request(url, headers={
        "x-apisports-key": API_KEY,
        "User-Agent": "V2-Football-Quant/1.0"
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception:
            if attempt < 2: time.sleep(0.5)
    return None


def fetch_today_fixtures():
    """拉取白名单联赛 + 今日/明日开赛的比赛"""
    td = date.today()
    nd = td + timedelta(days=1)
    all_fixtures = []

    for day in [td.strftime("%Y-%m-%d"), nd.strftime("%Y-%m-%d")]:
        resp = api_get(f"fixtures?date={day}&timezone=Asia/Shanghai")
        if not resp: continue
        for f in resp.get("response", []):
            lg_id = str(f["league"]["id"])
            if lg_id not in WL_SET: continue
            status = f["fixture"]["status"]["short"]
            if status not in ("NS", "TBD"): continue
            kickoff = f["fixture"]["date"]
            try:
                ko_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            except:
                ko_dt = datetime.fromisoformat(kickoff.split("+")[0] + "+00:00")

            # 前置漏斗: 只取12h内开赛
            if abs((ko_dt - datetime.now(ko_dt.tzinfo)).total_seconds()) > 43200:
                continue

            all_fixtures.append({
                "id": f["fixture"]["id"],
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "homeId": f["teams"]["home"]["id"],
                "awayId": f["teams"]["away"]["id"],
                "league": lg_id,
                "league_name": LEAGUE_CN.get(lg_id, f["league"]["name"]),
                "kickoff": kickoff,
            })
        time.sleep(0.5)

    seen = set()
    unique = []
    for fx in all_fixtures:
        if fx["id"] not in seen:
            seen.add(fx["id"])
            unique.append(fx)

    return unique


def run_v4_scan(run_tag="V4_DEFAULT"):
    logger.info(f"🚀 V4 勘探线扫描 | {run_tag} | {datetime.now().strftime('%H:%M')}")

    fixtures = fetch_today_fixtures()
    logger.info(f"📥 前置漏斗: {len(fixtures)} 场白名单 + 12h内")

    if not fixtures:
        logger.info("无符合条件的比赛")
        return

    router = StrategyRouter(config={"is_world_cup_window": False})
    predictions = []
    stats = {"total": len(fixtures), "no_h2h": 0, "below_threshold": 0, "api_error": 0, "valid": 0}

    for i, fx in enumerate(fixtures):
        if (i + 1) % 20 == 0:
            logger.info(f"  H2H 查询: {i+1}/{len(fixtures)}")

        result = evaluate_h2h_edge(fx["homeId"], fx["awayId"], api_get)
        time.sleep(0.5)

        if not result["valid"]:
            if "API_ERROR" in result.get("reason", ""):
                stats["api_error"] += 1
            elif "样本量" in result.get("reason", ""):
                stats["no_h2h"] += 1
            else:
                stats["below_threshold"] += 1
            continue

        # 拉取当前 OU 2.5 赔率
        odds_resp = api_get(f"odds?fixture={fx['id']}")
        ou_odds = None
        if odds_resp and odds_resp.get("response"):
            for bo in odds_resp["response"][0].get("bookmakers", []):
                if "Pinnacle" in bo.get("name", ""):
                    for bet in bo.get("bets", []):
                        if "over/under" in bet.get("name", "").lower():
                            for v in bet.get("values", []):
                                if "2.5" in v.get("value", ""):
                                    ou_odds = v.get("odd")
                                    break
                    break
        time.sleep(0.5)

        # 组装信号 → Router 断路器
        signal = {
            "fixture_id": fx["id"],
            "strategy_id": "V4_OU_H2H",
            "league_name": fx["league_name"],
            "home": fx["home"],
            "away": fx["away"],
            "market": result["market_type"],
            "placed_odds": float(ou_odds) if ou_odds else None,
            "metrics": result["metrics"],
            "time_pattern": "OBSERVING",
            "action": "BET",
            "priority": 50,
        }

        processed = router.process_signals(signal, {"v4_paper_trades": 0})
        stats["valid"] += 1

        predictions.append({
            "fixture_id": fx["id"],
            "date": date.today().isoformat(),
            "home": fx["home"],
            "away": fx["away"],
            "league": fx["league_name"],
            "strategy_id": "V4_OU_H2H",
            "market": result["market_type"],
            "placed_odds": float(ou_odds) if ou_odds else None,
            "metrics": result["metrics"],
            "action": processed.get("action", "SKIP"),
            "skip_reason": processed.get("skip_reason", ""),
        })

    # 保存
    today_str = date.today().strftime("%Y%m%d")
    out_path = REPORT_DIR / f"predictions_v4_{today_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    logger.info(f"\n📊 V4 扫描完成:")
    logger.info(f"  总数: {stats['total']} → H2H不足: {stats['no_h2h']} → 未达标: {stats['below_threshold']} → API错误: {stats['api_error']} → ✅有效: {stats['valid']}")
    logger.info(f"  保存: {out_path} ({len(predictions)} 条)")
    logger.info(f"  断路器: 全部 OBSERVE_ONLY (N<100, 勘探期)")


if __name__ == "__main__":
    run_v4_scan()
