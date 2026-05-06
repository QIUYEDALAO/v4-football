"""
V3 世界杯: Elo 积分爬虫
=======================
数据源: eloratings.net
获取国家队 Elo 积分，用于计算基准胜率。
"""

import csv
import io
import json
from pathlib import Path
from datetime import datetime

import requests

ELO_URL = "https://www.eloratings.net/2026.tsv"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "deep"

# 2026世界杯预估参赛队
WC2026_TEAMS = [
    "US", "MX", "CA", "AR", "BR", "UY", "CO", "EC", "PY", "VE",
    "EN", "FR", "DE", "ES", "PT", "NL", "IT", "BE", "HR", "DK",
    "CH", "AT", "RS", "PL", "CZ", "TR", "NO", "UA", "GR",
    "JP", "KR", "IR", "AU", "SN", "NG", "MA", "DZ", "EG", "PA", "UZ",
]

COUNTRY_NAMES = {
    "US": "美国", "MX": "墨西哥", "CA": "加拿大",
    "AR": "阿根廷", "BR": "巴西", "UY": "乌拉圭", "CO": "哥伦比亚", "EC": "厄瓜多尔",
    "PY": "巴拉圭", "VE": "委内瑞拉",
    "EN": "英格兰", "FR": "法国", "DE": "德国", "ES": "西班牙",
    "PT": "葡萄牙", "NL": "荷兰", "IT": "意大利", "BE": "比利时",
    "HR": "克罗地亚", "DK": "丹麦", "CH": "瑞士", "AT": "奥地利",
    "RS": "塞尔维亚", "PL": "波兰", "CZ": "捷克", "TR": "土耳其",
    "NO": "挪威", "UA": "乌克兰", "GR": "希腊",
    "JP": "日本", "KR": "韩国", "IR": "伊朗", "AU": "澳大利亚",
    "SN": "塞内加尔", "NG": "尼日利亚", "MA": "摩洛哥", "DZ": "阿尔及利亚",
    "EG": "埃及", "PA": "巴拿马", "UZ": "乌兹别克斯坦",
}


def fetch_elo_ratings() -> dict:
    """
    TSV 列: ?, rank, code, rating, ...
    返回: {code: {"rank": int, "rating": int, "name": str}}
    """
    resp = requests.get(ELO_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    reader = csv.reader(io.StringIO(resp.text), delimiter="\t")
    ratings = {}
    for row in reader:
        if len(row) < 4:
            continue
        code = row[2].strip()
        try:
            rank = int(row[1])
            rating = int(row[3])
        except (ValueError, IndexError):
            continue
        ratings[code] = {
            "rank": rank, "rating": rating,
            "name": COUNTRY_NAMES.get(code, code), "code": code,
        }
    return ratings


def get_wc2026_elo() -> list[dict]:
    """W杯参赛队 Elo，按积分降序"""
    all_ratings = fetch_elo_ratings()
    teams = [all_ratings[c] for c in WC2026_TEAMS if c in all_ratings]
    teams.sort(key=lambda t: t["rating"], reverse=True)
    return teams


if __name__ == "__main__":
    print("🧪 Elo 积分爬虫\n")
    teams = get_wc2026_elo()
    print(f"参赛队: {len(teams)} 支\n")
    print(f"{'排名':<6}{'国家':<12}{'Elo':<8}")
    print("-" * 30)
    for t in teams[:16]:
        print(f"{t['rank']:<6}{t['name']:<12}{t['rating']:<8}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "wc2026_elo.json", "w") as f:
        json.dump({"source": "eloratings.net", "fetched": datetime.now().isoformat(), "teams": teams}, f, indent=2, ensure_ascii=False)
    print(f"\n💾 wc2026_elo.json")
