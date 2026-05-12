"""
V4 天气数据采集 — OpenWeatherMap 免费 API
==========================================
免费配额: 1000次/天 (够用)
接入: context_enrichment.py → P8 观测层
环境变量: OPENWEATHER_API_KEY

用法:
  from engine.data_sources.weather import fetch_match_weather
  weather = fetch_match_weather(venue_city, ko_timestamp)
"""

from __future__ import annotations

import os, json, ssl, certifi, urllib.request, logging
from datetime import datetime, timezone

logger = logging.getLogger("V4_Weather")

try:
    OPENWEATHER_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
except Exception:
    OPENWEATHER_KEY = ""

CTX = ssl.create_default_context(cafile=certifi.where())

# 常见球场城市 → OpenWeatherMap city ID (静态映射，减少API查询)
CITY_GEO_MAP = {
    "London": (51.5074, -0.1278),
    "Manchester": (53.4808, -2.2426),
    "Liverpool": (53.4084, -2.9916),
    "Birmingham": (52.4862, -1.8904),
    "Madrid": (40.4168, -3.7038),
    "Barcelona": (41.3874, 2.1686),
    "Munich": (48.1351, 11.5820),
    "Berlin": (52.5200, 13.4050),
    "Dortmund": (51.5136, 7.4653),
    "Milan": (45.4642, 9.1900),
    "Rome": (41.9028, 12.4964),
    "Turin": (45.0703, 7.6869),
    "Naples": (40.8518, 14.2681),
    "Paris": (48.8566, 2.3522),
    "Marseille": (43.2965, 5.3698),
    "Lyon": (45.7640, 4.8357),
    "Lisbon": (38.7223, -9.1393),
    "Porto": (41.1579, -8.6291),
    "Amsterdam": (52.3676, 4.9041),
    "Rotterdam": (51.9225, 4.4792),
    "Eindhoven": (51.4416, 5.4697),
    "Moscow": (55.7558, 37.6173),
    "Saint Petersburg": (59.9343, 30.3351),
    "Istanbul": (41.0082, 28.9784),
    "Glasgow": (55.8642, -4.2518),
    "Zurich": (47.3769, 8.5417),
    "Basel": (47.5596, 7.5886),
    "Vienna": (48.2082, 16.3738),
    "Prague": (50.0755, 14.4378),
    "Warsaw": (52.2297, 21.0122),
    "Belgrade": (44.7866, 20.4489),
    "Zagreb": (45.8150, 15.9819),
    "Athens": (37.9838, 23.7275),
    "Copenhagen": (55.6761, 12.5683),
    "Stockholm": (59.3293, 18.0686),
    "Oslo": (59.9139, 10.7522),
    "Brussels": (50.8503, 4.3517),
    "Riyadh": (24.7136, 46.6753),
    "Jeddah": (21.5433, 39.1728),
    "Doha": (25.2854, 51.5310),
    "Dubai": (25.2048, 55.2708),
    "Abu Dhabi": (24.4539, 54.3773),
    "Sao Paulo": (-23.5505, -46.6333),
    "Rio de Janeiro": (-22.9068, -43.1729),
    "Buenos Aires": (-34.6037, -58.3816),
    "Mexico City": (19.4326, -99.1332),
    "New York": (40.7128, -74.0060),
    "Los Angeles": (34.0522, -118.2437),
    "Seoul": (37.5665, 126.9780),
    "Tokyo": (35.6762, 139.6503),
    "Beijing": (39.9042, 116.4074),
    "Shanghai": (31.2304, 121.4737),
    "Sydney": (-33.8688, 151.2093),
    "Melbourne": (-37.8136, 144.9631),
}


def _get_coords(city: str) -> tuple | None:
    """从城市名查找坐标"""
    for k, v in CITY_GEO_MAP.items():
        if k.lower() in city.lower() or city.lower() in k.lower():
            return v
    return None


def fetch_match_weather(city: str, ko_timestamp: int | None = None) -> dict:
    """
    查询比赛城市的天气。
    
    Args:
        city: 城市名或球场位置
        ko_timestamp: 开球时间戳(可选, 默认当前)
    
    Returns:
        {"temp_c": 15, "rain_mm": 0, "wind_ms": 3, "humidity": 65, 
         "condition": "Clear", "status": "OK"}
        或 {"status": "NO_KEY"/"NO_COORDS"/"API_ERROR"}
    """
    if not OPENWEATHER_KEY:
        return {"status": "NO_KEY"}

    coords = _get_coords(city)
    if not coords:
        return {"status": "NO_COORDS", "city": city}

    lat, lon = coords
    url = (
        f"https://api.openweathermap.org/data/2.5/weather?"
        f"lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "V4-Football-Quant/1.0"})
        with urllib.request.urlopen(req, context=CTX, timeout=8) as resp:
            data = json.loads(resp.read())

        return {
            "status": "OK",
            "city": city,
            "temp_c": round(data["main"]["temp"], 1),
            "humidity": data["main"]["humidity"],
            "wind_ms": round(data["wind"]["speed"], 1),
            "rain_mm": data.get("rain", {}).get("1h", 0),
            "condition": data["weather"][0]["main"] if data.get("weather") else "Unknown",
            "condition_desc": data["weather"][0]["description"] if data.get("weather") else "",
        }
    except Exception as e:
        return {"status": "API_ERROR", "error": str(e)[:80]}


def weather_marginal_impact(weather: dict) -> dict:
    """
    将天气数据转为对进球的边际影响估计（初版经验规则，需样本校准）。
    """
    if weather.get("status") != "OK":
        return {"impact": "UNKNOWN", "adjustment": 0}

    impact = {"score": 0, "factors": []}

    # 大雨：进球率 -15~20%
    if weather.get("rain_mm", 0) > 2:
        impact["score"] -= 1
        impact["factors"].append("HEAVY_RAIN")

    # 极低温（<5°C）：肌肉僵硬
    if weather.get("temp_c", 20) < 5:
        impact["score"] -= 1
        impact["factors"].append("COLD")

    # 大风（>10m/s）：影响传球精度
    if weather.get("wind_ms", 0) > 10:
        impact["score"] -= 1
        impact["factors"].append("HIGH_WIND")

    if impact["score"] >= 0:
        impact["adjustment"] = 0
    elif impact["score"] == -1:
        impact["adjustment"] = -0.05  # 轻微负面
    elif impact["score"] <= -2:
        impact["adjustment"] = -0.12  # 明显负面

    return impact
