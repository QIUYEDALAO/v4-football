"""
V4 进阶数据源: FotMob 逆向爬虫
功能: 零成本获取五大联赛的高阶 xG、首发阵容、射门坐标和动能图
"""
import requests
import json
import time


class FotMobScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.fotmob.com",
            "Referer": "https://www.fotmob.com/"
        }
        self.base_url = "https://www.fotmob.com/api"

    def get_match_details(self, fotmob_match_id: int) -> dict:
        """逆向请求核心端点，获取单场比赛的全维度 JSON 数据"""
        url = f"{self.base_url}/matchDetails?matchId={fotmob_match_id}"

        try:
            time.sleep(1.5)
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                print(f"🚨 触发风控 403! 比赛 {fotmob_match_id}")
                return None
            else:
                print(f"⚠️ 状态码 {response.status_code}")
                # 看看是不是返回了 HTML 而不是 JSON
                if response.headers.get("Content-Type", "").startswith("text/html"):
                    print("  → 返回的是 HTML(SPA)，API 可能改版")
                return None

        except Exception as e:
            print(f"❌ 网络崩溃: {e}")
            return None

    def extract_xg_and_lineups(self, match_data: dict) -> dict:
        """从庞大的 JSON 中精准剥离我们需要的量化因子"""
        if not match_data:
            return None

        result = {
            "home_xg": 0.0,
            "away_xg": 0.0,
            "home_lineup": [],
            "away_lineup": []
        }

        try:
            stats_list = match_data.get("content", {}).get("stats", {}).get("Periods", {}).get("All", {}).get("stats", [])
            for stat_group in stats_list:
                for stat in stat_group.get("stats", []):
                    if stat.get("title") == "Expected goals (xG)":
                        result["home_xg"] = float(stat.get("stats", [0, 0])[0])
                        result["away_xg"] = float(stat.get("stats", [0, 0])[1])
                        break
        except Exception:
            pass

        try:
            lineup_data = match_data.get("content", {}).get("lineup", {}).get("lineup", [])
            if len(lineup_data) == 2:
                for row in lineup_data[0].get("players", []):
                    for player in row:
                        result["home_lineup"].append(player.get("name", {}).get("fullName"))
                for row in lineup_data[1].get("players", []):
                    for player in row:
                        result["away_lineup"].append(player.get("name", {}).get("fullName"))
        except Exception:
            pass

        return result


if __name__ == "__main__":
    scraper = FotMobScraper()

    # 测试最近一场五大联赛比赛
    test_ids = [4193853, 4193504, 5375542]

    for mid in test_ids:
        print(f"🚀 测试 matchId={mid}...")
        raw = scraper.get_match_details(mid)
        if raw and "general" in raw:
            g = raw["general"]
            print(f"  ✅ {g.get('homeTeam',{}).get('name')} vs {g.get('awayTeam',{}).get('name')}")
            extracted = scraper.extract_xg_and_lineups(raw)
            print(f"  xG: H={extracted['home_xg']} A={extracted['away_xg']}")
            print(f"  首发: H={len(extracted['home_lineup'])}人 A={len(extracted['away_lineup'])}人")
            break
        elif raw:
            print(f"  ⚠️ 有数据但无 general: keys={list(raw.keys())[:5]}")
        else:
            print(f"  ❌ 失败")
        time.sleep(2)

    print("\n🏁 测试完成")
