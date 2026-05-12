"""
API-Football 深度数据挖掘器
=============================
利用现有订阅，涵盖三个核心模块：
1. 伤停名单 → 核心球员缺失检测
2. 首发阵容 → 战力折损指数 (Drop-off Index)
3. 球员数据 → Proxy xG 基础特征
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import os

API_KEY = os.environ.get("APIFOOTBALL_KEY", "your-api-key-here")
API_HOST = "https://v3.football.api-sports.io"
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 使用统一 API (urllib → curl 自动兜底)
import sys as _sys
_sys.path.insert(0, str(BASE_DIR))
from engine.net_utils import api_get as _api_get


def api_request(endpoint: str, params: dict = None) -> dict:
    """通用 API 请求 (curl 兜底, 永不被封)"""
    query_str = ""
    if params:
        query_str = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    result = _api_get(endpoint + query_str, API_KEY, API_HOST)
    if result is None:
        return {"error": "api_failed"}
    return result


def get_injuries(team_id: int, season: int = 2025) -> list:
    """获取球队伤停名单"""
    r = api_request("injuries", {"team": team_id, "season": season})
    injuries = r.get("response", [])
    return [
        {
            "player": i["player"]["name"],
            "reason": i.get("player", {}).get("reason", "?"),
            "fixture_return": i.get("fixture", {}).get("date", "?"),
        }
        for i in injuries
    ]


def get_player_stats(team_id: int, season: int = 2025) -> list:
    """获取球队球员赛季数据"""
    r = api_request("players", {"team": team_id, "season": season})
    players = r.get("response", [])
    result = []
    for p in players:
        stats = p.get("statistics", [{}])[0]
        result.append(
            {
                "id": p["player"]["id"],
                "name": p["player"]["name"],
                "position": stats.get("games", {}).get("position", "?"),
                "shots_total": stats.get("shots", {}).get("total") or 0,
                "shots_on": stats.get("shots", {}).get("on") or 0,
                "goals": stats.get("goals", {}).get("total") or 0,
            }
        )
    return result


# ==========================================
# 🚑 早盘伤停折损引擎 (08:00 Crude Attrition)
# ==========================================

class InjuryAttritionEngine:
    """赛前早盘分析 → 基于 injuries 接口计算绝对核心伤缺带来的 Spread 折损"""

    def __init__(self, weights_path: str = None):
        path = weights_path or str(BASE_DIR / "config" / "core_players_weight.json")
        try:
            with open(path) as f:
                self.weights_db = json.load(f)
        except Exception:
            self.weights_db = {}
        self._injury_cache = {}

    def fetch_fixture_injuries(self, fixture_id: int) -> list:
        """拉取该场比赛的所有伤病/停赛名单"""
        if fixture_id in self._injury_cache:
            return self._injury_cache[fixture_id]

        resp = api_request("injuries", {"fixture": fixture_id})
        data = resp.get("response", [])
        self._injury_cache[fixture_id] = data
        return data

    def calculate_attrition(self, fixture_id: int, home_id: int, away_id: int) -> dict:
        """
        计算主客队的战力折损 Delta。
        Returns: {"delta_home": float, "delta_away": float, "details": list}
        """
        result = {"delta_home": 0.0, "delta_away": 0.0, "details": []}

        home_str, away_str = str(home_id), str(away_id)
        # 如果两队都不在配置表里，直接跳过，节省网络请求
        if home_str not in self.weights_db and away_str not in self.weights_db:
            return result

        injuries = self.fetch_fixture_injuries(fixture_id)
        if not injuries:
            return result

        for inj in injuries:
            # 安全提取 team_id：team 可能是 dict/None/str
            team_raw = inj.get("team") if isinstance(inj, dict) else None
            if isinstance(team_raw, dict):
                team_id = str(team_raw.get("id", ""))
            elif isinstance(team_raw, str):
                team_id = team_raw
            else:
                continue

            # 安全提取 player_name
            player_raw = inj.get("player") if isinstance(inj, dict) else None
            if isinstance(player_raw, dict):
                player_name = (player_raw.get("name") or "").strip()
            elif isinstance(player_raw, str):
                player_name = player_raw
            else:
                player_name = ""

            if team_id not in self.weights_db:
                continue

            core_players = self.weights_db[team_id].get("players", {})

            # 名字匹配 (包含匹配，防止 API 缩写不一致)
            if not player_name:
                continue
            for core_name, core_data in core_players.items():
                if core_name.lower() in player_name.lower() or player_name.lower() in core_name.lower():
                    weight = core_data["weight"]
                    if team_id == home_str:
                        result["delta_home"] += weight
                        result["details"].append(f"{core_name} (-{weight})")
                    elif team_id == away_str:
                        result["delta_away"] += weight
                        result["details"].append(f"{core_name} (-{weight})")
                    break  # 匹配到一个就跳出

        result["delta_home"] = round(result["delta_home"], 1)
        result["delta_away"] = round(result["delta_away"], 1)
        return result


# ==========================================
# 🎯 战力折损引擎 (Lineup Arbitrage · V4 T-60min)
# ==========================================

class LineupArbitrageEngine:
    """赛前1小时首发分析 → 计算核心球员缺失度 → 战力折损指数"""

    def __init__(self, weights_path: str = None):
        self.weights_db = self._load_weights(weights_path)
        self._lineup_cache = {}  # 内存缓存，一场比赛只拉一次

    def _load_weights(self, path: str = None) -> dict:
        path = path or str(BASE_DIR / "config" / "core_players_weight.json")
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}

    def fetch_fixture_lineup(self, fixture_id: int) -> dict:
        """拉取赛前1小时首发阵容 (带内存缓存)"""
        if fixture_id in self._lineup_cache:
            return self._lineup_cache[fixture_id]

        lineups_data = api_request(f"fixtures/lineups?fixture={fixture_id}")
        data = lineups_data.get("response", [])
        self._lineup_cache[fixture_id] = data
        return data

    def calculate_dropoff_index(self, fixture_id: int, team_id: int) -> dict:
        """
        计算指定球队在当前比赛中的战力折损百分比。
        
        Returns:
            {"dropoff_pct": float, "missing_players": [str], "team_name": str}
        """
        team_str_id = str(team_id)
        result = {
            "dropoff_pct": 0.0,
            "missing_players": [],
            "team_name": "Unknown",
            "warning": None,
        }

        if team_str_id not in self.weights_db:
            return result

        team_config = self.weights_db[team_str_id]
        core_players = team_config.get("players", {})
        result["team_name"] = team_config.get("team_name", "?")

        # 拉取首发阵容
        lineups_data = self.fetch_fixture_lineup(fixture_id)
        if not lineups_data:
            result["warning"] = "首发名单暂未公布"
            return result

        # 找到目标球队的首发 11 人 player_id 集合
        starting_ids = set()
        for team_lineup in lineups_data:
            if team_lineup.get("team", {}).get("id") == team_id:
                for player_obj in team_lineup.get("startXI", []):
                    pid = player_obj.get("player", {}).get("id")
                    if pid:
                        starting_ids.add(str(pid))
                # 也检查替补（可能轮换上调）
                break

        # 遍历核心名单，缺失的累加折损度
        for p_name, p_data in core_players.items():
            p_id = str(p_data["id"])
            if p_id not in starting_ids:
                result["dropoff_pct"] += p_data["weight"]
                result["missing_players"].append(
                    f"{p_name} ({p_data['role']}, -{p_data['weight']}%)"
                )

        result["dropoff_pct"] = round(result["dropoff_pct"], 1)
        return result


# ==========================================
# 🧪 本地测试
# ==========================================
if __name__ == "__main__":
    engine = LineupArbitrageEngine()

    # 测试1: 用一场最近的英超比赛
    print("🧪 战力折损引擎测试\n")

    # 找一场曼联的比赛测试（fixture_id 从你已拉取的数据中选）
    test_cases = [
        # (fixture_id, team_id, 说明)
        (1035043, 33, "曼联 (任意比赛)"),
        (1382762, 157, "拜仁 vs PSG (明日比赛，首发可能未公布)"),
    ]

    for fid, tid, desc in test_cases:
        print(f"📊 fixture={fid} {desc} (team_id={tid})")
        result = engine.calculate_dropoff_index(fid, tid)
        if result["warning"]:
            print(f"  ⚠️ {result['warning']}")
        elif result["dropoff_pct"] > 0:
            print(f"  🚨 战力折损: {result['dropoff_pct']}%")
            print(f"  球队: {result['team_name']}")
            for m in result["missing_players"]:
                print(f"    ❌ {m}")
        else:
            print(f"  ✅ 全核心出战，折损 0% ({result['team_name']})")
        print()
