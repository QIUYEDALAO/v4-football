#!/usr/bin/env python3
"""
V2 时间机器 — 离线回测注入器 (加速器2)
==========================================
喂入过去3个月的赛程ID，复用V2引擎逻辑，批量生成 verified_backtest_YYYYMMDD.json。

用法:
  python3 engine/run_historical_paper.py --start 2026-02-01 --end 2026-05-01
  python3 engine/run_historical_paper.py --fixtures 123,456,789

输出: data/paper_trading/verified_backtest_YYYYMMDD.json (含 "mode": "BACKTEST" 标签)
"""

import json
import ssl
import certifi
import time
import urllib.request
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.secrets import API_KEY, API_HOST
from engine.daily_runner import calc_spread, fetch_ht_1x2, calc_edge, map_to_decile
from engine.data_sources.apifootball_deep import InjuryAttritionEngine
from engine.paper_trading import extract_pinnacle_ht_1x2, parse_ht_result, settle_trade
from engine.clv import clv_triple
from logger import logger

SSL_CTX = ssl.create_default_context(cafile=certifi.where())

PAPER_DIR = BASE_DIR / "data" / "paper_trading"
PAPER_DIR.mkdir(exist_ok=True)

# 白名单
with open(BASE_DIR / "config" / "leagues_whitelist.json") as f:
    LEAGUE_CN = json.load(f)["leagueId"]


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
    return None


def fetch_fixtures_in_range(start: str, end: str) -> list:
    """拉取日期范围内的比赛"""
    wl_set = set(str(k) for k in LEAGUE_CN.keys())
    all_fixtures = []
    d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")

    while d <= end_d:
        day_str = d.strftime("%Y-%m-%d")
        resp = api(f"fixtures?date={day_str}")
        d += timedelta(days=1)

        if not resp:
            continue
        for f in resp.get("response", []):
            fid = f["fixture"]["id"]
            lg_id = str(f["league"]["id"])
            status = f["fixture"]["status"]["short"]
            if lg_id not in wl_set:
                continue
            if status not in ("FT", "AET", "PEN"):
                continue
            all_fixtures.append({
                "id": fid,
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "league": f["league"]["id"],
                "league_name": LEAGUE_CN.get(lg_id, f["league"]["name"]),
                "date": f["fixture"]["date"],
                "homeId": f["teams"]["home"]["id"],
                "awayId": f["teams"]["away"]["id"],
            })
        time.sleep(1.0)

    logger.info(f"拉取 {start}~{end}: {len(all_fixtures)} 场完赛")
    return all_fixtures


def run_backtest(fixtures: list, injury_engine: InjuryAttritionEngine):
    results_by_date = {}
    processed = 0
    skipped = 0

    for fx in fixtures:
        processed += 1
        fid = fx["id"]

        # 拉取基本信息
        pred_resp = api(f"predictions?fixture={fid}")
        time.sleep(0.8)

        # 构造最小 fixture 结构
        pred_data = pred_resp.get("response", [{}])[0] if pred_resp else {}
        fx["_predictions"] = pred_data

        # Step 1: calc_spread
        try:
            base_spread = calc_spread(fx)
            orig_bin = fx["decile_info"]["decile"]
        except Exception:
            skipped += 1
            continue

        # Step 2: 伤停折损
        attrition = injury_engine.calculate_attrition(fid, fx["homeId"], fx["awayId"])
        delta_home = attrition["delta_home"]
        delta_away = attrition["delta_away"]

        if delta_home > 0 or delta_away > 0:
            adj_spread = round(base_spread - delta_home + delta_away, 1)
            fx["att_def_spread"] = adj_spread
            fx["decile_info"] = map_to_decile(adj_spread)
            fx["attrition_flag"] = True
            fx["bin_jump_size"] = abs(orig_bin - fx["decile_info"]["decile"])
        else:
            fx["attrition_flag"] = False
            fx["bin_jump_size"] = 0

        # Step 3: 拉取赔率
        odds = fetch_ht_1x2(fid)
        fx["_ht_1x2"] = odds
        time.sleep(0.8)

        # Step 4: 拉取收盘赔率 + 实际赛果
        fix_resp = api(f"fixtures?id={fid}")
        if not fix_resp or not fix_resp.get("response"):
            skipped += 1
            continue

        fix_data = fix_resp["response"][0]
        ht = fix_data["score"]["halftime"]
        ht_home = ht.get("home", 0) or 0
        ht_away = ht.get("away", 0) or 0
        ht_str = f"{ht_home}-{ht_away}"
        actual = parse_ht_result(ht_str)

        if not actual:
            skipped += 1
            continue

        # 收盘赔率
        odds_resp = api(f"odds?fixture={fid}")
        time.sleep(0.8)
        closing = extract_pinnacle_ht_1x2(odds_resp)

        # Step 5: Edge + CLV
        edge_result = calc_edge(fx)
        if not edge_result:
            skipped += 1
            continue

        # 三层CLV
        triple = {}
        if closing and "D" in closing:
            triple = clv_triple(edge_result["odds"], "D", closing)

        # Step 6: 赛果
        pnl, is_hit = settle_trade(0, edge_result["odds"], "D", actual)

        row = fx.get("decile_info", {})
        result = {
            "fixture_id": fid,
            "home": fx["home"],
            "away": fx["away"],
            "league": fx["league_name"],
            "bet_outcome": "D",
            "placed_odds": edge_result["odds"],
            "stake": 0,
            "ht_score": ht_str,
            "actual_outcome": actual,
            "is_hit": is_hit,
            "pnl": round(pnl, 2),
            "closing_ht_1x2": closing,
            "raw_clv": triple.get("raw_clv"),
            "fair_line_clv": triple.get("fair_line_clv"),
            "ev_vs_close": triple.get("ev_vs_close"),
            "clv_margin": triple.get("margin"),
            "raw_closing_odds": triple.get("raw_close"),
            "fair_closing_odds": triple.get("fair_close"),
            "true_clv": round(triple.get("ev_vs_close", 0), 4),
            "ht_has_goal": (ht_home + ht_away) > 0,
            "attrition_flag": fx.get("attrition_flag", False),
            "bin_jump_size": fx.get("bin_jump_size", 0),
            "orig_bin": orig_bin,
            "adj_bin": fx["decile_info"]["decile"] if fx.get("attrition_flag") else orig_bin,
            "mode": "BACKTEST",
        }

        # 按日期分组
        match_date = fx.get("date", "unknown")[:10]
        if match_date not in results_by_date:
            results_by_date[match_date] = []
        results_by_date[match_date].append(result)

        if processed % 10 == 0:
            logger.info(f"  进度: {processed}/{len(fixtures)}")

    # 保存
    for d, results in results_by_date.items():
        date_key = d.replace("-", "")
        out_path = PAPER_DIR / f"verified_backtest_{date_key}.json"
        summary = {
            "date": d,
            "verified_at": datetime.now().isoformat(),
            "mode": "BACKTEST",
            "total_predicted": len(results),
            "total_completed": len(results),
            "hits": sum(1 for r in results if r["is_hit"]),
            "misses": sum(1 for r in results if not r["is_hit"]),
            "total_staked": 0.0,
            "total_pnl": sum(r["pnl"] for r in results),
            "results": results,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✅ 回测完成: {len(fixtures)} 场 → {len(results_by_date)} 天")
    logger.info(f"   成功: {sum(len(r) for r in results_by_date.values())} 场, 跳过: {skipped}")


if __name__ == "__main__":
    engine = InjuryAttritionEngine()

    if "--start" in sys.argv and "--end" in sys.argv:
        si = sys.argv.index("--start")
        ei = sys.argv.index("--end")
        start_date = sys.argv[si + 1]
        end_date = sys.argv[ei + 1]
        fix_list = fetch_fixtures_in_range(start_date, end_date)
        if fix_list:
            run_backtest(fix_list, engine)
    else:
        print("用法: python3 engine/run_historical_paper.py --start 2026-02-01 --end 2026-05-01")
