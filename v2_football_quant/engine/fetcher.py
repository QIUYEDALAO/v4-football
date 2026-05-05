"""
批量数据拉取脚本 v0.1
======================
api-football 限频：免费版 30次/分钟（1次/2秒）
保守策略：1.5秒间隔 + 3次重试 + 指数退避

用法：
  python3 fetcher.py --date 2026-05-05 --leagues all
  python3 fetcher.py --date 2026-05-05 --leagues 39,140,135
  python3 fetcher.py --date-range 2026-05-01,2026-05-05 --leagues all

输出：
  data/raw_fixtures/fixtures_list.json  (追加)
  data/raw_fixtures/h2h/{fixture_id}.json
  data/raw_fixtures/predictions/{fixture_id}.json
  data/raw_fixtures/odds/{fixture_id}.json
"""

import asyncio
import json
import os
import ssl
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
import urllib.request

# ===== 配置 =====
API_KEY = "你的API-KEY请替换"
API_HOST = "https://v3.football.api-sports.io"
DATA_DIR = Path(__file__).parent.parent / "data" / "raw_fixtures"
SLEEP_MS = 1500  # 1.5秒/次 → 40次/分钟（留余量）
MAX_RETRIES = 3
RETRY_BASE_MS = 2000

# SSL context（macOS Python 证书问题）
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# 白名单联赛
with open(Path(__file__).parent.parent / "config" / "leagues_whitelist.json") as f:
    LEAGUE_IDS = list(json.load(f)["leagueId"].keys())


def api_sync(endpoint: str) -> Optional[dict]:
    """同步 API 调用（带重试）"""
    url = f"{API_HOST}/{endpoint}"
    req = urllib.request.Request(url, headers={
        "x-apisports-key": API_KEY,
        "Accept": "application/json",
    })

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
                body = resp.read()
                data = json.loads(body)
                if data.get("errors"):
                    err_key = list(data["errors"].keys())[0] if data["errors"] else "unknown"
                    if "rate" in err_key.lower():
                        # 被限频，等久一点
                        wait = RETRY_BASE_MS * (2 ** attempt)
                        print(f"  ⚠️ 限频，等待 {wait/1000:.0f}s...")
                        time.sleep(wait / 1000)
                        continue
                    raise Exception(f"API Error: {data['errors']}")
                return data
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BASE_MS * (2 ** attempt) / 1000
                time.sleep(wait)
            else:
                print(f"  ❌ 最终失败: {e}")
                return None
    return None


def fetch_fixtures(date_str: str, league_ids: list[str]) -> tuple[list, set]:
    """拉取指定日期的比赛列表"""
    fixtures = []
    fixture_ids = set()

    for lg_id in league_ids:
        resp = api_sync(f"fixtures?date={date_str}&league={lg_id}&timezone=Asia/Shanghai")
        if not resp:
            continue

        for f in resp.get("response", []):
            fixture = f["fixture"]
            league = f["league"]
            teams = f["teams"]
            score = f["score"]

            item = {
                "id": fixture["id"],
                "date": fixture["date"],
                "league": league["id"],
                "league_name": league["name"],
                "home": teams["home"]["name"],
                "away": teams["away"]["name"],
                "homeId": teams["home"]["id"],
                "awayId": teams["away"]["id"],
                "htHome": score["halftime"]["home"],
                "htAway": score["halftime"]["away"],
                "ftHome": score["fulltime"]["home"],
                "ftAway": score["fulltime"]["away"],
                "status": fixture["status"]["short"],
            }
            fixtures.append(item)
            fixture_ids.add(str(fixture["id"]))

        time.sleep(SLEEP_MS / 1000)

    return fixtures, fixture_ids


def fetch_details(fixture_id: str):
    """拉取单场比赛的 H2H / Predictions / Odds"""
    # 1. H2H
    h2h_resp = api_sync(f"fixtures/headtohead?h2h={fixture_id}&last=20")
    if h2h_resp and "response" in h2h_resp:
        with open(DATA_DIR / "h2h" / f"{fixture_id}.json", "w", encoding="utf-8") as f:
            json.dump(h2h_resp["response"], f, ensure_ascii=False)
    time.sleep(SLEEP_MS / 1000)

    # 2. Predictions
    pred_resp = api_sync(f"predictions?fixture={fixture_id}")
    if pred_resp and "response" in pred_resp:
        with open(DATA_DIR / "predictions" / f"{fixture_id}.json", "w", encoding="utf-8") as f:
            json.dump(pred_resp["response"][0] if pred_resp["response"] else {}, f, ensure_ascii=False)
    time.sleep(SLEEP_MS / 1000)

    # 3. Odds（可能为空）
    odds_resp = api_sync(f"odds?fixture={fixture_id}")
    if odds_resp and "response" in odds_resp:
        with open(DATA_DIR / "odds" / f"{fixture_id}.json", "w", encoding="utf-8") as f:
            json.dump(odds_resp["response"][0] if odds_resp["response"] else {}, f, ensure_ascii=False)
    time.sleep(SLEEP_MS / 1000)


def update_fixtures_list(new_fixtures: list):
    """更新 fixtures_list.json（去重追加）"""
    list_path = DATA_DIR / "fixtures_list.json"

    existing = []
    existing_ids = set()
    if list_path.exists():
        with open(list_path) as f:
            existing = json.load(f)
        existing_ids = {str(item["id"]) for item in existing if isinstance(item, dict)}

    added = 0
    for nf in new_fixtures:
        if str(nf["id"]) not in existing_ids:
            existing.append(nf)
            existing_ids.add(str(nf["id"]))
            added += 1

    with open(list_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return added


def run(date_str: str = None, date_range: str = None, leagues: list[str] = None):
    """主入口"""
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "h2h").mkdir(exist_ok=True)
    (DATA_DIR / "predictions").mkdir(exist_ok=True)
    (DATA_DIR / "odds").mkdir(exist_ok=True)

    lg_ids = leagues if leagues else LEAGUE_IDS

    # 确定拉取日期
    if date_range:
        start_str, end_str = date_range.split(",")
        start = datetime.strptime(start_str.strip(), "%Y-%m-%d")
        end = datetime.strptime(end_str.strip(), "%Y-%m-%d")
        dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range((end - start).days + 1)]
    elif date_str:
        dates = [date_str]
    else:
        dates = [date.today().strftime("%Y-%m-%d")]

    print("=" * 60)
    print(f"Fetcher v0.1")
    print(f"日期: {dates}")
    print(f"联赛: {len(lg_ids)} 个")
    print(f"间隔: {SLEEP_MS}ms")
    print("=" * 60)

    total_fixtures = 0
    total_details = 0

    for d in dates:
        print(f"\n[{d}] 拉取比赛列表...")
        fixtures, fixture_ids = fetch_fixtures(d, lg_ids)
        print(f"  获取 {len(fixtures)} 场比赛")

        added = update_fixtures_list(fixtures)
        print(f"  新增 {added} 场到 fixtures_list.json")
        total_fixtures += added

        # 拉取详情
        new_ids = [fid for fid in fixture_ids
                   if not (DATA_DIR / "h2h" / f"{fid}.json").exists()]

        print(f"  拉取 {len(new_ids)} 场详情 (H2H+Predictions+Odds)...")

        for i, fid in enumerate(new_ids):
            fetch_details(fid)
            total_details += 1
            if (i + 1) % 10 == 0 or (i + 1) == len(new_ids):
                print(f"    {i + 1}/{len(new_ids)} 完成")

    print(f"\n✅ 完成！")
    print(f"  比赛: {total_fixtures} 场")
    print(f"  详情: {total_details} 场")
    print(f"  数据目录: {DATA_DIR}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="API-Football 批量拉取")
    p.add_argument("--date", help="单日期 YYYY-MM-DD")
    p.add_argument("--date-range", help="日期范围 YYYY-MM-DD,YYYY-MM-DD")
    p.add_argument("--leagues", default="all",
                   help="联赛ID逗号分隔，或 'all' 使用白名单")
    args = p.parse_args()

    lg_ids = None
    if args.leagues != "all":
        lg_ids = [x.strip() for x in args.leagues.split(",")]

    run(date_str=args.date, date_range=args.date_range, leagues=lg_ids)
