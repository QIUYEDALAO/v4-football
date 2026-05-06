"""
V2 每日自动运行脚本 v2.0 (HT 1X2)
=====================================
每天 08:00 自动执行，基于 att_def_spread 分档定价 HT 1X2。

废弃：V38 HT OU 逻辑
新增：HT 1X2 Fair Odds Matrix + Edge 计算

用法：
  python3 daily_runner.py           # 手动触发
  python3 daily_runner.py --watch   # 持续运行（定时器）
"""

import json, ssl, time, os, math
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
from logger import logger, log_event

API_KEY = "你的API-KEY请替换"
API_HOST = "https://v3.football.api-sports.io"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw_fixtures"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
REPORT_DIR.mkdir(exist_ok=True)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

SLEEP_MS = 1.5

# 加载白名单 + Fair Odds Matrix
with open(BASE_DIR / "config" / "leagues_whitelist.json") as f:
    wl_data = json.load(f)
    LEAGUE_CN = wl_data["leagueId"]

with open(BASE_DIR / "engine" / "fair_odds_matrix.json") as f:
    FAIR_MATRIX = json.load(f)


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
            else:
                return None


def map_to_decile(att_def_spread: float) -> dict:
    """将 att_def_spread 映射到 Fair Odds Matrix 的档位"""
    for row in FAIR_MATRIX:
        if row["spread_lo"] <= att_def_spread < row["spread_hi"]:
            return row
    # 超出范围 → 最极端档
    if att_def_spread < FAIR_MATRIX[0]["spread_lo"]:
        return FAIR_MATRIX[0]
    return FAIR_MATRIX[-1]


# ===== Step 1: 赛程拉取 =====
def fetch_today_fixtures() -> list[dict]:
    """
    北京时间 12:00 到次日 12:00 为一天。
    对应拉取今天+明天的 api-football 数据，再按北京时间过滤。
    """
    td = date.today()
    td_str = td.strftime("%Y-%m-%d")
    nd_str = (td + timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"[1/7] 拉取赛程 (BJ {td_str} 12:00 → {nd_str} 12:00)...")

    wl_set = set(str(k) for k in LEAGUE_CN.keys())
    all_fixtures = []

    for day_str in [td_str, nd_str]:
        resp = api(f"fixtures?date={day_str}&timezone=Asia/Shanghai")
        if not resp:
            continue
        for f in resp.get("response", []):
            fixture = f["fixture"]
            league = f["league"]
            teams = f["teams"]

            league_id_str = str(league["id"])
            if league_id_str not in wl_set:
                continue

            status_short = fixture["status"]["short"]
            if status_short not in ("NS", "TBD"):
                continue

            kickoff = fixture["date"]
            try:
                bj_time = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            except:
                bj_time = datetime.fromisoformat(kickoff.split("+")[0] + "+00:00")

            bj_date = bj_time.strftime("%Y-%m-%d")
            bj_hour = bj_time.hour

            # 时间窗口过滤：今天12:00 → 明天12:00（北京时间）
            in_window = False
            if bj_date == td_str and bj_hour >= 12:
                in_window = True
            elif bj_date == nd_str and bj_hour < 12:
                in_window = True

            if not in_window:
                continue

            bj_str = bj_time.strftime("%H:%M")

            all_fixtures.append({
                "id": fixture["id"],
                "date": kickoff,
                "time_bj": bj_str,
                "league": league["id"],
                "league_name": LEAGUE_CN.get(league_id_str, league["name"]),
                "home": teams["home"]["name"],
                "away": teams["away"]["name"],
                "homeId": teams["home"]["id"],
                "awayId": teams["away"]["id"],
                "status": status_short,
            })

    # 去重
    seen = set()
    unique = []
    for fx in all_fixtures:
        if fx["id"] not in seen:
            seen.add(fx["id"])
            unique.append(fx)

    unique.sort(key=lambda x: x["date"])
    logger.info(f"  → {len(unique)} 场未开始")
    return unique

def fetch_details(fixtures: list[dict]) -> list[dict]:
    logger.info(f"[2/7] 拉取 Predictions...")
    enriched = []

    for i, fx in enumerate(fixtures):
        fid = fx["id"]
        try:
            pred_resp = api(f"predictions?fixture={fid}")
        except Exception as e:
            pred_resp = None
            logger.warning(f"  ⚠️ Predictions失败 {fid}")
        time.sleep(SLEEP_MS)

        pred_data = pred_resp.get("response", [{}])[0] if pred_resp else {}
        fx["_predictions"] = pred_data
        fx["_fallback"] = pred_resp is None
        enriched.append(fx)

        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(fixtures)}")

    logger.info(f"  → {len(enriched)} 场")
    return enriched


# ===== Step 3: att_def_spread + decile 映射 =====
def calc_spread(fx: dict) -> float:
    pred = fx.get("_predictions", {})
    teams = pred.get("teams", {}) or {}
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}

    last_5_h = home.get("last_5") or {}
    last_5_a = away.get("last_5") or {}
    att_h = float(str(last_5_h.get("att", "0")).rstrip("%") or 0)
    att_a = float(str(last_5_a.get("att", "0")).rstrip("%") or 0)
    def_h = float(str(last_5_h.get("def", "0")).rstrip("%") or 0)
    def_a = float(str(last_5_a.get("def", "0")).rstrip("%") or 0)

    spread = (att_h - def_a) - (att_a - def_h)
    fx["att_def_spread"] = round(spread, 1)
    fx["decile_info"] = map_to_decile(spread)
    return spread


# ===== Step 4: 抓取 HT 1X2 赔率 =====
def fetch_ht_1x2(fixture_id: int) -> Optional[dict]:
    resp = api(f"odds?fixture={fixture_id}")
    if not resp or not resp.get("response"):
        return None

    odds_data = resp["response"][0]
    bookmakers = odds_data.get("bookmakers", [])
    if len(bookmakers) < 3:
        return None

    result = {"fixture_id": fixture_id, "bookmaker_count": len(bookmakers)}

    for target_bm in ["Pinnacle", "Bet365", None]:
        for bo in bookmakers:
            if target_bm and bo["name"] != target_bm:
                continue
            for bet in bo.get("bets", []):
                nm = bet.get("name", "").lower()
                is_ht = any(k in nm for k in ["first half winner", "1st half winner"])
                if not is_ht:
                    continue
                for val in bet.get("values", []):
                    v = val.get("value", "").lower()
                    odd = float(val.get("odd", 0))
                    if odd <= 0:
                        continue
                    if "home" in v:
                        result["H"] = odd
                    elif "draw" in v:
                        result["D"] = odd
                    elif "away" in v:
                        result["A"] = odd
                if "H" in result and "D" in result and "A" in result:
                    result["bookmaker"] = bo["name"]
                    return result

    return None


# ===== Step 5: Kelly 仓位 =====
def calc_stake(model_prob: float, odds: float, decile: int, bankroll: float = 2000,
               fraction: float = 1/6) -> float:
    """
    1/6 Kelly + 首周保守策略
    - Draw (档4/5/8): 标准 1/6 Kelly
    - H/A: 1/8 Kelly（观察期）
    - 硬顶 150
    """
    if odds <= 1:
        return 0
    b = odds - 1
    p = model_prob
    f_star = (b * p - (1 - p)) / b
    
    if f_star <= 0:
        return 0
    
    # H/A 方向观察期：降低仓位
    kf = fraction
    raw = f_star * kf
    stake = bankroll * max(0, raw)
    
    # 硬顶
    return round(min(stake, 150), 2)


# ===== Step 6: Edge 计算 =====
def calc_edge(fx: dict) -> Optional[dict]:
    odds = fx.get("_ht_1x2")
    if not odds or not ("H" in odds and "D" in odds and "A" in odds):
        return None

    row = fx["decile_info"]
    fair = {"H": row["fair_H"], "D": row["fair_D"], "A": row["fair_A"]}

    best = None
    for outcome in ["H", "D", "A"]:
        market_odds = odds.get(outcome)
        if not market_odds or market_odds < 1.70 or market_odds > 4.50:
            continue

        model_prob = 1 / fair[outcome]
        implied_prob = 1 / market_odds
        edge = model_prob - implied_prob

        if edge > 0.05:
            ev = model_prob * market_odds - 1
            candidate = {
                "outcome": outcome,
                "odds": market_odds,
                "fair": fair[outcome],
                "model_prob": round(model_prob, 4),
                "implied_prob": round(implied_prob, 4),
                "edge": round(edge, 4),
                "ev": round(ev, 4),
            }
            if best is None or candidate["ev"] > best["ev"]:
                best = candidate

    # 首周策略：只推 Draw（档4/5/8），H/A 只观察
    if best and best["outcome"] != "D":
        return None  # 首周不推 H/A
    
    if best and best["outcome"] == "A" and best["odds"] > 4.0:
        best = None

    return best


# ===== Step 6: 日报生成 =====
def generate_report(fixtures: list[dict], recs: list[dict]) -> str:
    td = date.today().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")

    lines = [
        f"## ⚽ V2 每日推荐 (HT 1X2) | {td} {now}",
        "",
        f"📊 今日比赛: {len(fixtures)} 场 (白名单) · 推荐: {len(recs)} 场",
        "",
        "模型: att_def_spread 10档分位定价 · 投注方向: HT 1X2",
        "",
        "---",
        "",
    ]

    if not recs:
        lines.append("> ⚠️ 今日无满足 edge > 5% 的推荐")
        return "\n".join(lines)

    for i, rec in enumerate(recs, 1):
        fx = rec["fixture"]
        edge = rec["edge"]
        label = {"H": "半场主胜", "D": "半场平局", "A": "半场客胜"}[edge["outcome"]]

        lines.append(f"### {i}. {fx['home']} vs {fx['away']} → 推 **{label}**")
        lines.append("")
        lines.append(f"| 维度 | 数据 |")
        lines.append(f"|------|------|")
        lines.append(f"| ⏰ 时间 | {fx.get('time_bj', '?')} |")
        lines.append(f"| 🏟 联赛 | {fx['league_name']} |")
        lines.append(f"| 📐 att_def_spread | {fx.get('att_def_spread', '?')} (档{rec['decile']}) |")
        lines.append(f"| 🎯 公平赔率 | H={edge['fair_H']:.2f} D={edge['fair_D']:.2f} A={edge['fair_A']:.2f} |")
        lines.append(f"| 💰 {rec['bookmaker']} {label} | **{edge['odds']:.2f}** |")
        lines.append(f"| 📊 模型概率 | {edge['model_prob']*100:.1f}% |")
        lines.append(f"| 🏦 隐含概率 | {edge['implied_prob']*100:.1f}% |")
        lines.append(f"| 🎲 Edge | **{edge['edge']*100:+.1f}%** |")
        lines.append(f"| 📈 EV | **{edge['ev']*100:+.1f}%** |")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("")
    lines.append(f"> 🤖 V2 v2.0 · HT 1X2 分档模型 · Edge > 5% 触发")
    lines.append(f"> ⚠️ 纸盘模式 — 仅记录，不下单")
    lines.append(f"> 💡 模型基于 2322 场历史 att_def_spread 分位概率")

    return "\n".join(lines)


def run_once():
    print("=" * 60)
    print(f"V2 Daily Runner v2.0 (HT 1X2)")
    print(f"启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    fixtures = fetch_today_fixtures()
    if not fixtures:
        print("\n> 今日无比赛，退出")
        return

    fixtures = fetch_details(fixtures)

    logger.info(f"[3/7] 计算 att_def_spread + decile 映射...")
    for fx in fixtures:
        calc_spread(fx)

    logger.info(f"[4/7] 拉取 HT 1X2 赔率...")
    for fx in fixtures:
        odds = fetch_ht_1x2(fx["id"])
        fx["_ht_1x2"] = odds
        if odds and "H" in odds:
            print(f"  {fx['home']}vs{fx['away']}: H={odds.get('H','?')} D={odds.get('D','?')} A={odds.get('A','?')}")
        time.sleep(SLEEP_MS)

    logger.info(f"[5/7] Edge 计算...")
    recommendations = []
    for fx in fixtures:
        edge = calc_edge(fx)
        if edge:
            row = fx["decile_info"]
            recommendations.append({
                "fixture": fx,
                "edge": {
                    **edge,
                    "fair_H": row["fair_H"],
                    "fair_D": row["fair_D"],
                    "fair_A": row["fair_A"],
                },
                "decile": row["decile"],
                "bookmaker": fx.get("_ht_1x2", {}).get("bookmaker", "?"),
                "stake": calc_stake(edge["model_prob"], edge["odds"], row["decile"]),
            })
            logger.success(f"  ✅ {fx['home']}vs{fx['away']}: 推{edge['outcome']} "
                  f"odds={edge['odds']:.2f} edge={edge['edge']*100:+.1f}%")

    # 按 EV 排序，全部推荐（不限场次），同联赛最多2场
    recommendations.sort(key=lambda x: -x["edge"]["ev"])
    # 同联赛去重：每天每联赛最多2场
    lg_count = {}
    final_recs = []
    for rec in recommendations:
        lg = rec["fixture"]["league_name"]
        lg_count[lg] = lg_count.get(lg, 0) + 1
        if lg_count[lg] <= 2:
            final_recs.append(rec)
    recommendations = final_recs

    logger.info(f"[6/7] 生成日报...")
    report = generate_report(fixtures, recommendations)
    report_path = REPORT_DIR / f"daily_{date.today().strftime('%Y%m%d')}.md"
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"  → {report_path}")

    logger.info(f"[7/7] 保存预测 + 输出")
    print()
    print(report)

    # 保存
    pred_save = []
    for rec in recommendations:
        fx = rec["fixture"]
        edge = rec["edge"]
        pred_save.append({
            "fixture_id": fx["id"],
            "date": date.today().isoformat(),
            "home": fx["home"],
            "away": fx["away"],
            "league": fx["league_name"],
            "time_bj": fx.get("time_bj", ""),
            "att_def_spread": fx.get("att_def_spread", 0),
            "decile": rec["decile"],
            "outcome": edge["outcome"],
            "fair_odds": edge["fair_odds"] if "fair_odds" in edge else {
                "H": edge["fair_H"], "D": edge["fair_D"], "A": edge["fair_A"],
            },
            "placed_odds": edge["odds"],
            "model_prob": edge["model_prob"],
            "implied_prob": edge["implied_prob"],
            "edge": edge["edge"],
            "ev": edge["ev"],
            "stake": rec.get("stake", 0),
            "bookmaker": rec["bookmaker"],
        })

    pred_path = REPORT_DIR / f"predictions_{date.today().strftime('%Y%m%d')}.json"
    # 读取现有 → 合并 → 去重（防止重复运行覆盖之前的结果）
    existing = []
    existing_ids = set()
    if pred_path.exists():
        try:
            with open(pred_path) as f:
                existing = json.load(f)
            existing_ids = {p["fixture_id"] for p in existing if isinstance(p, dict)}
        except:
            pass
    merged = existing + [p for p in pred_save if p["fixture_id"] not in existing_ids]
    with open(pred_path, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    logger.info(f"\n预测数据: {pred_path}")

    # 昨日验证
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        import sys; sys.path.insert(0, str(BASE_DIR / "engine"))
        from paper_trading import verify_date as pt_verify
        result = pt_verify(yesterday)
        if "error" not in result and result.get("total_completed", 0) > 0:
            logger.info(f"\n📊 昨日 ({yesterday}) 验证: "
                  f"{result['hits']}/{result['total_completed']} 命中, "
                  f"ROI {result['roi_pct']:+.1f}%")
    except Exception as e:
        logger.warning(f"\n⚠️ 昨日验证跳过: {e}")


if __name__ == "__main__":
    import sys
    if "--watch" in sys.argv:
        print("持续监控模式...")
        import schedule as sched
        sched.every().day.at("08:00").do(run_once)
        while True:
            sched.run_pending()
            time.sleep(60)
    else:
        run_once()
