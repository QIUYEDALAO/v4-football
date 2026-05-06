"""
方案二：Cookie 注入法 绕过 FotMob Turnstile
=============================================
原理: 从真实浏览器复制 cf_clearance cookie → requests 直接调 API。
一次手动解决 Turnstile，之后 cookie 可复用数小时。
"""

import json
import requests
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "deep"
COOKIE_FILE = Path.home() / ".config" / "fotmob_cookie.txt"


def load_cookie() -> str | None:
    """从文件读取已保存的 cf_clearance cookie"""
    if COOKIE_FILE.exists():
        return COOKIE_FILE.read_text().strip()
    return None


def save_cookie(cookie_value: str):
    """保存 cookie 供后续使用"""
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(cookie_value)
    print(f"💾 Cookie 已保存至 {COOKIE_FILE}")


def get_match_details(match_id: int, cookie: str = None) -> dict | None:
    """
    用 cf_clearance cookie 请求 FotMob API。

    Args:
        match_id: FotMob 比赛 ID（数字，如 4193853）
        cookie: 从浏览器复制的 cf_clearance 值。如果为 None，尝试从文件加载。
    """
    if cookie is None:
        cookie = load_cookie()
    
    if not cookie:
        print("❌ 无 cookie。请先获取。")
        return None

    session = requests.Session()
    session.cookies.set("cf_clearance", cookie, domain=".fotmob.com")
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://www.fotmob.com",
        "Referer": "https://www.fotmob.com/",
    })

    url = f"https://www.fotmob.com/api/data/matchDetails?matchId={match_id}"
    resp = session.get(url, timeout=15)

    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 403:
        error = resp.json() if resp.text else {}
        if error.get("code") == "TURNSTILE_REQUIRED":
            print("🔒 Cookie 已过期，需要重新获取。")
            return None
        print(f"⚠️  403: {error}")
        return None
    else:
        print(f"⚠️  HTTP {resp.status_code}")
        return None


def extract_features(data: dict) -> dict:
    """剥离量化因子"""
    g = data.get("general", {})
    c = data.get("content", {})
    result = {
        "home": g.get("homeTeam", {}).get("name"),
        "away": g.get("awayTeam", {}).get("name"),
        "date": g.get("matchTimeUTCDate"),
        "home_xg": 0.0, "away_xg": 0.0,
        "home_lineup": [], "away_lineup": [],
    }
    stats = c.get("stats", {}).get("Periods", {}).get("All", {}).get("stats", [])
    for group in stats:
        for s in group.get("stats", []):
            if "expected" in s.get("key", ""):
                vals = s.get("stats", [0, 0])
                result["home_xg"] = float(vals[0] or 0)
                result["away_xg"] = float(vals[1] or 0)
    lu = c.get("lineup", {}).get("lineup", [])
    if len(lu) == 2:
        for i, team in enumerate(lu):
            names = []
            for row in team.get("players", []):
                for p in row:
                    names.append(p.get("name", {}).get("fullName", "?"))
            (result["home_lineup"] if i == 0 else result["away_lineup"]).extend(names)
    return result


# ==========================================
# 🧪 测试
# ==========================================
if __name__ == "__main__":
    cookie = load_cookie()

    if not cookie:
        print("=" * 50)
        print("📋 获取 cf_clearance cookie 步骤:")
        print("1. 用浏览器打开 https://www.fotmob.com")
        print("2. 等页面加载（会自动解 Turnstile）")
        print("3. F12 → Application → Cookies → fotmob.com")
        print("4. 复制 cf_clearance 的值")
        print("5. 运行: python fotmob.py --cookie '粘贴的值'")
        print("=" * 50)
        print("\n或者直接粘贴 cookie 到终端:")
        import sys
        cookie = input("Cookie: ").strip()
        if cookie:
            save_cookie(cookie)

    if cookie:
        data = get_match_details(4193853, cookie)
        if data:
            f = extract_features(data)
            print(f"\n✅ {f['home']} vs {f['away']}")
            print(f"  xG: H={f['home_xg']} A={f['away_xg']}")
            print(f"  首发: H={len(f['home_lineup'])} A={len(f['away_lineup'])}")
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_DIR / "fotmob_sample.json", "w") as fp:
                json.dump(data, fp, indent=2, ensure_ascii=False)
            print(f"  💾 data/deep/fotmob_sample.json")
