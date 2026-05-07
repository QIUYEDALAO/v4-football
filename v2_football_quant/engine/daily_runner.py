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

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from config.secrets import API_KEY, API_HOST
from bankroll import Bankroll, calculate_stake
from engine.data_sources.apifootball_deep import InjuryAttritionEngine
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


# ===== Step 6: Edge 计算 =====
def calc_edge(fx: dict) -> Optional[dict]:
    odds = fx.get("_ht_1x2")
    if not odds or not ("H" in odds and "D" in odds and "A" in odds):
        return None

    row = fx["decile_info"]
    fair = {"H": row["fair_H"], "D": row["fair_D"], "A": row["fair_A"]}

    best = None
    for outcome in ["D"]:  # 首周只推 Draw，直接在循环中过滤，不误杀
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
    
    return best


# ===== Step 6: 日报生成 =====
def generate_report(fixtures: list[dict], bets: list[dict], stats: dict) -> str:
    td = date.today().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")

    lines = [
        f"## ⚽ V2 每日推荐 (HT 1X2) | {td} {now}",
        "",
        f"📊 今日扫描: {stats['total_scanned']} 场 (白名单) · 推荐: {len(bets)} 场",
        "",
        f"🔍 漏斗: 总{stats['total_fixtures']}场 → 扫描{stats['total_scanned']} "
        f"→ 无盘口{stats['skip_no_market']} → 无Edge{stats['skip_no_edge']} "
        f"→ 负EV{stats['skip_neg_ev']} → 熔断{stats['skip_meltdown']} "
        f"→ 低Kelly{stats['skip_low_kelly']} → ✅{stats['bet_placed']}",
        "",
        "模型: att_def_spread 10档分位定价 · 投注方向: HT 1X2 · 全量死因追踪",
        "",
        "---",
        "",
    ]

    if not bets:
        lines.append("> ⚠️ 今日无满足条件的推荐")
        return "\n".join(lines)

    for i, rec in enumerate(bets, 1):
        mprobs = rec["model_probs"]
        odds_D = rec["offered_odds_D"]
        
        lines.append(f"### {i}. {rec['home']} vs {rec['away']} → 推 **半场平局**")
        lines.append("")
        lines.append(f"| 维度 | 数据 |")
        lines.append(f"|------|------|")
        lines.append(f"| ⏰ 时间 | {rec.get('time_bj', '?')} |")
        lines.append(f"| 🏟 联赛 | {rec['league_name']} |")
        lines.append(f"| 📐 att_def_spread | {rec.get('att_def_spread', '?')} (档{rec['decile']}) |")
        lines.append(f"| 🎯 公平概率 | H={mprobs['H']:.3f} D={mprobs['D']:.3f} A={mprobs['A']:.3f} |")
        lines.append(f"| 🏦 市场概率 | H={rec['market_probs']['H']:.3f} D={rec['market_probs']['D']:.3f} A={rec['market_probs']['A']:.3f} |")
        lines.append(f"| 💰 {rec.get('bookmaker', '?')} 半场平 | **{odds_D:.2f}** |")
        lines.append(f"| 📊 保本概率 | {rec['break_even_prob']:.3f} |")
        lines.append(f"| 🎲 Edge | **{rec['edge_pp']*100:+.1f}%** |")
        lines.append(f"| 📈 EV | **{rec['ev_pct']*100:+.1f}%** |")
        si = rec.get("stake_info", {})
        if si:
            lines.append(f"| 💵 注码 | {si.get('stake', 0)} (Kelly {si.get('kelly_factor_used', 0)*4:.0f}/4) |")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("")
    lines.append(f"> 🤖 V2 v2.1 · HT 1X2 分档模型 · 全量死因追踪")
    lines.append(f"> ⚠️ 纸盘模式 — 仅记录，不下单")
    lines.append(f"> 💡 模型基于 2322 场历史 att_def_spread 分位概率")
    lines.append(f"> 🛡️ Kelly 1/4 · 软熔断15% · 硬熔断30% · 本金20000")

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

    # 💰 实例化真实资金池 (P0 修复: 打通 bankroll.py 经脉)
    br = Bankroll()
    # 🚑 早盘伤停折损引擎 (Phase 2)
    injury_engine = InjuryAttritionEngine()

    logger.info(f"[3/7] 计算 att_def_spread + 伤停折损修正...")
    for fx in fixtures:
        # 1. 算基础攻防差
        base_spread = calc_spread(fx)
        
        # 2. 算伤停折损 (早盘补丁)
        attrition = injury_engine.calculate_attrition(fx["id"], fx["homeId"], fx["awayId"])
        delta_home = attrition["delta_home"]
        delta_away = attrition["delta_away"]
        
        # 3. 如果有大哥伤停，进行物理学修正
        if delta_home > 0 or delta_away > 0:
            # 主队伤了，主队变弱(-)，客队伤了，主队相对变强(+)
            adj_spread = base_spread - delta_home + delta_away
            adj_spread = round(adj_spread, 1)
            
            # 覆盖原始数据，并重新映射档位
            fx["att_def_spread"] = adj_spread
            fx["decile_info"] = map_to_decile(adj_spread)
            
            # 记录在案，留给 JSON 审计
            fx["attrition_details"] = attrition["details"]
            fx["base_spread"] = base_spread
            
            logger.info(f"  🚑 伤停修正! {fx['home']} vs {fx['away']} | Base: {base_spread} -> Adj: {adj_spread}")
            for d in attrition["details"]:
                logger.info(f"     └─ 缺阵: {d}")

    logger.info(f"[4/7] 拉取 HT 1X2 赔率...")
    for fx in fixtures:
        odds = fetch_ht_1x2(fx["id"])
        fx["_ht_1x2"] = odds
        if odds and "H" in odds:
            print(f"  {fx['home']}vs{fx['away']}: H={odds.get('H','?')} D={odds.get('D','?')} A={odds.get('A','?')}")
        time.sleep(SLEEP_MS)

    logger.info(f"[5/7] Edge 计算 + 风控拦截 (上帝视角·全景死因追踪)...")
    
    # ── 漏斗统计容器 ──
    stats = {
        "total_fixtures": len(fixtures),
        "total_scanned": 0,
        "skip_no_market": 0,
        "skip_no_edge": 0,
        "skip_neg_ev": 0,
        "skip_meltdown": 0,
        "skip_low_kelly": 0,
        "bet_placed": 0
    }
    
    all_candidates = []  # 全量追踪：每场都有记录 (含SKIP死因)
    bets = []            # 仅 BET 的用于推荐+预测
    
    for fx in fixtures:
        row = fx.get("decile_info")
        if not row:
            continue
        stats["total_scanned"] += 1
        
        # ── 基础骨架：保证任何阶段 SKIP 都有完整记录 ──
        base_rec = {
            "fixture_id": fx["id"],
            "home": fx["home"],
            "away": fx["away"],
            "league_name": fx["league_name"],
            "league_id": fx["league"],
            "time_bj": fx.get("time_bj", ""),
            "att_def_spread": fx.get("att_def_spread", 0),
            "decile": row["decile"],
            "model_probs": {"H": row["fair_H"], "D": row["fair_D"], "A": row["fair_A"]},
            "market_probs": None,
            "offered_odds_D": None,
            "break_even_prob": None,
            "edge_pp": None,
            "ev_pct": None,
            "stake_info": None,
            "action": None,
            "skip_code": None,
            "skip_reason": None,
            # 伤停折损审计
            "base_spread": fx.get("base_spread"),
            "adj_spread": fx.get("att_def_spread") if fx.get("base_spread") != fx.get("att_def_spread") else None,
            "attrition_details": fx.get("attrition_details", []),
        }
        
        market_odds = fx.get("_ht_1x2", {})
        odds_D = market_odds.get("D")
        odds_H = market_odds.get("H")
        odds_A = market_odds.get("A")
        bookmaker = market_odds.get("bookmaker", "?")
        
        if not odds_D or not odds_H or not odds_A:
            stats["skip_no_market"] += 1
            base_rec.update({"action": "SKIP", "skip_code": "NO_MARKET", "skip_reason": "HT 1X2盘口未开"})
            all_candidates.append(base_rec)
            continue
        
        market_probs = {"H": round(1/odds_H, 4), "D": round(1/odds_D, 4), "A": round(1/odds_A, 4)}
        prob_D = row["fair_D"]
        edge_pp = round(prob_D - market_probs["D"], 4)
        ev_pct = round(prob_D * odds_D - 1, 4)
        break_even = round(1 / odds_D, 4)
        
        base_rec.update({
            "market_probs": market_probs,
            "offered_odds_D": odds_D,
            "break_even_prob": break_even,
            "edge_pp": edge_pp,
            "ev_pct": ev_pct,
            "bookmaker": bookmaker
        })
        
        if edge_pp <= 0:
            stats["skip_no_edge"] += 1
            base_rec.update({"action": "SKIP", "skip_code": "NO_EDGE", "skip_reason": f"Edge {edge_pp} <= 0"})
            all_candidates.append(base_rec)
            continue
        
        if ev_pct < 0:
            stats["skip_neg_ev"] += 1
            base_rec.update({"action": "SKIP", "skip_code": "NEG_EV", "skip_reason": f"EV {ev_pct} < 0"})
            all_candidates.append(base_rec)
            continue
        
        # ── 资金风控测算 ──
        stake_info = calculate_stake(br, prob_D, odds_D)
        base_rec["stake_info"] = stake_info
        
        action = stake_info["action"]
        if action.startswith("SKIP"):
            code = action.replace("SKIP_", "")
            if code == "MELTDOWN":
                stats["skip_meltdown"] += 1
            else:
                stats["skip_low_kelly"] += 1
            base_rec.update({"action": "SKIP", "skip_code": code, "skip_reason": stake_info.get("reason")})
            all_candidates.append(base_rec)
            # 熔断/低 Kelly 也有盘口数据，值得记录但不算推荐
            continue
        
        # ── 通过！计入推荐 ──
        stats["bet_placed"] += 1
        base_rec.update({"action": "BET", "skip_code": None, "skip_reason": None})
        all_candidates.append(base_rec)
        bets.append(base_rec)
        logger.success(f"  ✅ {fx['home']}vs{fx['away']}: 推D odds={odds_D:.2f} edge={edge_pp*100:+.1f}% ev={ev_pct*100:+.1f}%")
    
    # ── 同联赛去重：每天每联赛最多2场 ──
    bets.sort(key=lambda x: -(x["ev_pct"] or 0))
    lg_count = {}
    final_bets = []
    for r in bets:
        lg = r["league_name"]
        lg_count[lg] = lg_count.get(lg, 0) + 1
        if lg_count[lg] <= 2:
            final_bets.append(r)
    bets = final_bets
    
    # ── 漏斗日报 ──
    logger.info("="*40)
    logger.info("📊 V2 今日漏斗扫描日报")
    logger.info(f"📦 原始赛程总数: {stats['total_fixtures']}")
    logger.info(f"🔍 进模型分档场次: {stats['total_scanned']}")
    logger.info(f"❌ 过滤 (盘口未开): {stats['skip_no_market']}")
    logger.info(f"❌ 过滤 (无数学Edge): {stats['skip_no_edge']}")
    logger.info(f"❌ 过滤 (负期望EV): {stats['skip_neg_ev']}")
    logger.info(f"🛑 过滤 (硬熔断): {stats['skip_meltdown']}")
    logger.info(f"🛡️ 过滤 (低Kelly/资金红线): {stats['skip_low_kelly']}")
    logger.info(f"✅ 最终符合下注: {stats['bet_placed']}")
    logger.info("="*40)

    # ── 🌎 全量候选池快照 (基准防线 · 专家建议三) ──
    universe = []
    today_str = date.today().strftime('%Y%m%d')
    for fx in fixtures:
        odds = fx.get("_ht_1x2", {})
        row = fx.get("decile_info", {})
        if odds and "D" in odds:
            model_prob = 1 / row["fair_D"] if row.get("fair_D") else 0
            implied_prob = 1 / odds["D"] if odds.get("D") else 0
            universe.append({
                "fixture_id": fx["id"],
                "home": fx["home"],
                "away": fx["away"],
                "league": fx.get("league_name", ""),
                "time_bj": fx.get("time_bj", ""),
                "decile": row.get("decile", 0),
                "att_def_spread": fx.get("att_def_spread", 0),
                "odds_H": odds.get("H"),
                "odds_D": odds.get("D"),
                "odds_A": odds.get("A"),
                "fair_D": row.get("fair_D"),
                "model_prob_D": round(model_prob, 4) if model_prob else None,
                "implied_prob_D": round(implied_prob, 4) if implied_prob else None,
            })
    univ_path = REPORT_DIR / f"universe_candidates_{today_str}.json"
    with open(univ_path, "w") as f:
        json.dump(universe, f, ensure_ascii=False, indent=2)
    logger.info(f"\n🌎 全量候选池: {len(universe)} 场 → {univ_path}")

    logger.info(f"[6/7] 生成日报 + 保存全量死因追踪...")
    report = generate_report(fixtures, bets, stats)
    report_path = REPORT_DIR / f"daily_{date.today().strftime('%Y%m%d')}.md"
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"  → {report_path}")
    
    # ── 保存全量死因追踪 (包含所有SKIP记录) ──
    scan_path = REPORT_DIR / f"full_scan_{date.today().strftime('%Y%m%d')}.json"
    with open(scan_path, "w") as f:
        json.dump({"date": date.today().isoformat(), "stats": stats, "candidates": all_candidates}, f, ensure_ascii=False, indent=2)
    logger.info(f"📋 全量死因追踪: {len(all_candidates)} 场 → {scan_path}")

    logger.info(f"[7/7] 输出日报 + 保存预测")
    print()
    print(report)

    # 保存预测 (🔍 仅 BET 记录 → paper_trading.py 结算用)
    pred_save = []
    for rec in bets:
        pred_save.append({
            "fixture_id": rec["fixture_id"],
            "date": date.today().isoformat(),
            "home": rec["home"],
            "away": rec["away"],
            "league": rec["league_name"],
            "time_bj": rec.get("time_bj", ""),
            "att_def_spread": rec.get("att_def_spread", 0),
            "decile": rec["decile"],
            "outcome": "D",
            "model_probs": rec["model_probs"],
            "market_probs": rec["market_probs"],
            "placed_odds": rec["offered_odds_D"],
            "break_even_prob": rec["break_even_prob"],
            "edge_pp": rec["edge_pp"],
            "ev_pct": rec["ev_pct"],
            "stake_info": rec.get("stake_info", {}),
            "action": rec["action"],
            "bookmaker": rec.get("bookmaker", "?"),
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
