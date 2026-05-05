"""
P0 Day 1 — 单场数据验证脚本
==========================
选一场已完赛英超，调通整条 API 链路，数据落库。

用法：python3 engine/p0_day1_validate.py --fixture-id 1379314
"""

import sqlite3
import json
import os
import urllib.request
import ssl
import time
from datetime import datetime

API_KEY = "e5e315b1f9ba1ba51dc2124b35f07a01"
API_HOST = "v3.football.api-sports.io"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "v2_football.db")

SLEEP_BETWEEN = 1.2  # 限频：免费版 30/min，保守点


def api(endpoint: str) -> dict:
    """调用 API-Football v3"""
    url = f"https://{API_HOST}/{endpoint}"
    req = urllib.request.Request(url, headers={
        "x-apisports-key": API_KEY,
        "Accept": "application/json",
    })
    
    # 创建不验证证书的 context（解决 macOS Python SSL 问题）
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise


def insert_fixture(db, f: dict):
    """插入比赛结果到 fixtures_results"""
    fixture = f["fixture"]
    league = f["league"]
    teams = f["teams"]
    score = f["score"]
    
    db.execute("""
        INSERT OR REPLACE INTO fixtures_results (
            fixture_id, league_id, league_name, season,
            kickoff_utc, status,
            home_team_id, home_team_name,
            away_team_id, away_team_name,
            ht_home_goals, ht_away_goals,
            ft_home_goals, ft_away_goals
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fixture["id"],
        league["id"],
        league["name"],
        league["season"],
        fixture["date"],
        fixture["status"]["short"],
        teams["home"]["id"],
        teams["home"]["name"],
        teams["away"]["id"],
        teams["away"]["name"],
        score["halftime"]["home"],
        score["halftime"]["away"],
        score["fulltime"]["home"],
        score["fulltime"]["away"],
    ))


def insert_odds(db, fixture_id: int, odds_data: dict):
    """插入赔率快照到 odds_snapshots"""
    if not odds_data:
        return
    
    captured = odds_data.get("update", datetime.now().isoformat())
    
    # 判断是否为临场收盘（赛前30min内）
    # 简化：根据 captured_at 和 kickoff 时间差判断
    is_closing = 1 if "18:0" in captured or "18:3" in captured or "18:5" in captured else 0
    
    for bo in odds_data.get("bookmakers", []):
        bookmaker = bo["name"]
        for bet in bo.get("bets", []):
            market = bet["name"]
            for val in bet.get("values", []):
                db.execute("""
                    INSERT INTO odds_snapshots (
                        fixture_id, captured_at, bookmaker, market,
                        odds_type, decimal_odds, is_closing
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    fixture_id, captured, bookmaker, market,
                    val["value"], float(val["odd"]), is_closing
                ))


def insert_predictions(db, fixture_id: int, pred_data: dict):
    """插入 API 预测到 predictions_cache"""
    if not pred_data:
        return
    
    predictions = pred_data.get("predictions", {}) or {}
    teams = pred_data.get("teams", {}) or {}
    
    form_home = teams.get("home", {}).get("last_5", {}).get("form", "")
    form_away = teams.get("away", {}).get("last_5", {}).get("form", "")
    att_home = teams.get("home", {}).get("last_5", {}).get("att", "")
    att_away = teams.get("away", {}).get("last_5", {}).get("att", "")
    def_home = teams.get("home", {}).get("last_5", {}).get("def", "")
    def_away = teams.get("away", {}).get("last_5", {}).get("def", "")
    
    goals_home_json = json.dumps(teams.get("home", {}).get("last_5", {}).get("goals", {}))
    goals_away_json = json.dumps(teams.get("away", {}).get("last_5", {}).get("goals", {}))
    
    raw = json.dumps(pred_data, ensure_ascii=False)
    
    db.execute("""
        INSERT OR REPLACE INTO predictions_cache (
            fixture_id, raw_response, advice,
            prob_home, prob_draw, prob_away,
            under_over,
            form_home, form_away,
            att_home, att_away,
            def_home, def_away,
            captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        fixture_id,
        raw,
        predictions.get("advice", ""),
        float(predictions.get("percent", {}).get("home", "0").rstrip("%") or 0) / 100,
        float(predictions.get("percent", {}).get("draw", "0").rstrip("%") or 0) / 100,
        float(predictions.get("percent", {}).get("away", "0").rstrip("%") or 0) / 100,
        predictions.get("under_over", ""),
        form_home, form_away,
        att_home, att_away,
        def_home, def_away,
    ))


def validate(fixture_id: int, db_path: str = DB_PATH):
    """主流程：验证单场比赛"""
    db = sqlite3.connect(db_path)
    
    # 1. 获取 fixture
    print(f"[1/4] 获取 fixture {fixture_id}...")
    resp = api(f"fixtures?id={fixture_id}")
    fixture = resp["response"][0]
    insert_fixture(db, fixture)
    print(f"  ✅ {fixture['teams']['home']['name']} {fixture['score']['fulltime']['home']}-{fixture['score']['fulltime']['away']} {fixture['teams']['away']['name']}")
    time.sleep(SLEEP_BETWEEN)
    
    # 2. 获取 odds
    print(f"[2/4] 获取 odds...")
    resp = api(f"odds?fixture={fixture_id}")
    odds = resp["response"][0] if resp["response"] else None
    insert_odds(db, fixture_id, odds)
    bookmaker_count = len(odds.get("bookmakers", [])) if odds else 0
    print(f"  ✅ {bookmaker_count} 家博彩公司赔率已入库")
    time.sleep(SLEEP_BETWEEN)
    
    # 3. 获取 predictions
    print(f"[3/4] 获取 predictions...")
    resp = api(f"predictions?fixture={fixture_id}")
    pred = resp["response"][0] if resp["response"] else None
    insert_predictions(db, fixture_id, pred)
    advice = pred.get("predictions", {}).get("advice", "N/A") if pred else "N/A"
    print(f"  ✅ API 预测: {advice}")
    time.sleep(SLEEP_BETWEEN)
    
    # 4. 验证数据完整性
    print(f"[4/4] 验证数据完整性...")
    counts = db.execute("""
        SELECT 'fixtures' as tbl, COUNT(*) as cnt FROM fixtures_results WHERE fixture_id=?
        UNION ALL
        SELECT 'odds' as tbl, COUNT(*) as cnt FROM odds_snapshots WHERE fixture_id=?
        UNION ALL
        SELECT 'predictions' as tbl, COUNT(*) as cnt FROM predictions_cache WHERE fixture_id=?
    """, (fixture_id, fixture_id, fixture_id)).fetchall()
    
    for tbl, cnt in counts:
        status = "✅" if cnt > 0 else "❌"
        print(f"  {status} {tbl}: {cnt} 条记录")
    
    db.commit()
    db.close()
    print("\n🎉 单场验证完成！")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="P0 Day 1 单场验证")
    p.add_argument("--fixture-id", type=int, required=True, help="Fixture ID")
    args = p.parse_args()
    
    validate(args.fixture_id)
