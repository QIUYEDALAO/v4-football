"""
实时赔率轮询 + 水位报警 (P2-1)
================================
对满足推荐条件的场次，每30分钟拉取 Pinnacle HT Over/Under 赔率变化。

报警条件：水位变化 >15% → 记录在 alert_log.json
"""

import json
import ssl
import time
import urllib.request
from pathlib import Path
from datetime import datetime

API_KEY = "你的API-KEY请替换"
API_HOST = "https://v3.football.api-sports.io"
ALERT_LOG = Path(__file__).parent.parent / "data" / "alert_log.json"
ODDS_SNAP_DIR = Path(__file__).parent.parent / "data" / "odds_snapshots"

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


def get_ht_odds(fixture_id: int) -> dict | None:
    """获取 Pinnacle 半场大小球 0.5 赔率"""
    resp = api(f"odds?fixture={fixture_id}&bookmaker=6")  # 6 = Pinnacle
    if not resp or not resp.get("response"):
        return None

    odds_data = resp["response"][0]
    result = {
        "fixture_id": fixture_id,
        "captured_at": odds_data.get("update", datetime.now().isoformat()),
    }

    for bo in odds_data.get("bookmakers", []):
        for bet in bo.get("bets", []):
            if "Over/Under - First Half" in bet.get("name", ""):
                for val in bet.get("values", []):
                    label = val.get("value", "")
                    odd_val = val.get("odd", "0")
                    if "Over" in label:
                        result["ht_over_0.5"] = float(odd_val)
                    elif "Under" in label:
                        result["ht_under_0.5"] = float(odd_val)

    return result


def compare_odds(new_odds: dict, prev_odds: dict) -> dict | None:
    """比较赔率变化，超过 15% 触发报警"""
    alert = None
    for key in ["ht_over_0.5", "ht_under_0.5"]:
        if key in new_odds and key in prev_odds:
            change = (new_odds[key] - prev_odds[key]) / prev_odds[key]
            if abs(change) > 0.15:
                if alert is None:
                    alert = {"fixture_id": new_odds["fixture_id"], "changes": []}
                alert["changes"].append({
                    "market": key,
                    "prev": prev_odds[key],
                    "now": new_odds[key],
                    "change_pct": round(change * 100, 1),
                    "direction": "升水" if change > 0 else "降水",
                })
                # 特殊标记：Over 大涨 + Under 大降 = 大球盘口在走强
                if key == "ht_over_0.5" and change < -0.15:
                    # Over 赔率下降 → 大球概率上升 → 好信号
                    alert.get("__pvt", ...)
    return alert


def poll_watchlist(watchlist: list[int]) -> list[dict]:
    """
    轮询监控列表中的所有比赛。
    
    Args:
        watchlist: fixture_id 列表
    
    Returns:
        报警列表
    """
    ODDS_SNAP_DIR.mkdir(exist_ok=True)
    alerts = []

    for fid in watchlist:
        odds = get_ht_odds(fid)
        if not odds:
            continue

        # 保存快照
        snap_path = ODDS_SNAP_DIR / f"{fid}_{int(time.time())}.json"
        with open(snap_path, "w") as f:
            json.dump(odds, f)

        # 找上一次快照
        prev_snaps = sorted(
            ODDS_SNAP_DIR.glob(f"{fid}_*.json"),
            key=lambda x: x.stat().st_mtime
        )
        if len(prev_snaps) >= 2:
            with open(prev_snaps[-2]) as f:
                prev = json.load(f)
            alert = compare_odds(odds, prev)
            if alert:
                alerts.append(alert)

        time.sleep(1.5)  # 限频

    return alerts


def save_alerts(alerts: list[dict]):
    """追加报警到日志"""
    existing = []
    if ALERT_LOG.exists():
        with open(ALERT_LOG) as f:
            existing = json.load(f)

    for alert in alerts:
        alert["timestamp"] = datetime.now().isoformat()
        existing.append(alert)

    with open(ALERT_LOG, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 odds_monitor.py <fixture_id> [fixture_id ...]")
        sys.exit(1)

    watchlist = [int(x) for x in sys.argv[1:]]
    print(f"监控 {len(watchlist)} 场比赛...")
    alerts = poll_watchlist(watchlist)

    if alerts:
        save_alerts(alerts)
        print(f"⚠️ {len(alerts)} 条水位报警:")
        for a in alerts:
            for ch in a.get("changes", []):
                print(f"  fixture {a['fixture_id']}: {ch['market']} "
                      f"{ch['prev']:.2f}→{ch['now']:.2f} ({ch['change_pct']:+.1f}% {ch['direction']})")
    else:
        print("无异常波动")
