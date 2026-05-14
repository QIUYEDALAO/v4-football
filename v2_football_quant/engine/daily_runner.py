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

import json, ssl, time, os, math, certifi, sys, argparse
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional
from logger import logger, log_event

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from config.secrets import API_KEY, API_HOST
from bankroll import Bankroll, calculate_stake
from engine.data_sources.apifootball_deep import InjuryAttritionEngine
from engine import net_utils
from engine.task_watchdog import v2_window_checker_watchdog, v2_pool_watchdog
DATA_DIR = BASE_DIR / "data" / "raw_fixtures"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
REPORT_DIR.mkdir(exist_ok=True)
STATE_DIR = BASE_DIR / "data" / "state"
STATE_DIR.mkdir(exist_ok=True)

SSL_CTX = ssl.create_default_context(cafile=certifi.where())

SLEEP_MS = 0.1  # Pro版 75000/天, 0.1s足够安全

# 加载白名单 + Fair Odds Matrix
with open(BASE_DIR / "config" / "leagues_whitelist.json") as f:
    wl_data = json.load(f)
    LEAGUE_CN = wl_data["leagueId"]

with open(BASE_DIR / "engine" / "fair_odds_matrix.json") as f:
    FAIR_MATRIX = json.load(f)

# 🌟 五大联赛专项矩阵 (双轨制)
MATRIX_TOP5 = None
MATRIX_CONFIG = {}
MATRIX_CONFIG_PATH = BASE_DIR / "config" / "matrix_config.json"
if MATRIX_CONFIG_PATH.exists():
    with open(MATRIX_CONFIG_PATH) as f:
        MATRIX_CONFIG = json.load(f)
    top5_path = BASE_DIR / "data_pipeline" / "data" / MATRIX_CONFIG.get("matrix_routing", {}).get("top5_special", "")
    if top5_path.exists():
        with open(top5_path) as f:
            MATRIX_TOP5 = json.load(f)
        logger.info(f"🧬 五大联赛专项矩阵已加载 ({len(MATRIX_TOP5)} 档)")

TOP5_IDS = set(MATRIX_CONFIG.get("top5_league_ids", [39, 140, 135, 78, 61]))

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

def get_ops_date(now=None):
    """运营日: 12:00切换。午夜后凌晨比赛仍归前一天运营窗口"""
    now = now or datetime.now(LOCAL_TZ)
    if now.hour < 12:
        return now.date() - timedelta(days=1)
    return now.date()


def get_matrix_for_league(league_id):
    """双轨制: 五大联赛用专项矩阵, 其余用默认"""
    if MATRIX_TOP5 and league_id in TOP5_IDS:
        return MATRIX_TOP5
    return FAIR_MATRIX


def api(endpoint: str) -> Optional[dict]:
    return net_utils.api_get(endpoint, API_KEY, API_HOST)


def map_to_decile(att_def_spread: float, league_id: int = None) -> dict:
    """将 att_def_spread 映射到 Fair Odds Matrix 的档位 (支持双轨制)"""
    matrix = get_matrix_for_league(league_id) if league_id else FAIR_MATRIX
    for row in matrix:
        if row["spread_lo"] <= att_def_spread < row["spread_hi"]:
            return row
    if att_def_spread < matrix[0]["spread_lo"]:
        return matrix[0]
    return matrix[-1]


# ===== Step 1: 赛程拉取 =====
def fetch_today_fixtures() -> list[dict]:
    """
    北京时间 12:00 到次日 12:00 为一天。
    对应拉取今天+明天的 api-football 数据，再按北京时间过滤。
    """
    td = get_ops_date()
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

def fetch_details(fixtures: list[dict], quick_mode: bool = False) -> list[dict]:
    logger.info(f"[2/7] 拉取 Predictions...")
    enriched = []

    for i, fx in enumerate(fixtures):
        fid = fx["id"]
        if quick_mode:
            # 快速模式：跳过 Predictions API，用缓存数据
            fx["_predictions"] = fx.get("_predictions", {})
            fx["_fallback"] = True
            enriched.append(fx)
            continue
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
    # 概率百分比 → 小数 (att: 67% → 0.67)
    att_h = float(str(last_5_h.get("att", "0")).rstrip("%") or 0) / 100
    att_a = float(str(last_5_a.get("att", "0")).rstrip("%") or 0) / 100
    def_h = float(str(last_5_h.get("def", "0")).rstrip("%") or 0) / 100
    def_a = float(str(last_5_a.get("def", "0")).rstrip("%") or 0) / 100

    spread = (att_h - def_a) - (att_a - def_h)
    
    # 🛡️ 防暴击 Sanity Check (物理极限 ±30)
    if abs(spread) > 30.0:
        logger.warning(f"🚨 [GUARD] DIRTY_SPREAD | fixture={fx.get('id')} spread={spread:.1f} | att_h={att_h:.3f} att_a={att_a:.3f} def_h={def_h:.3f} def_a={def_a:.3f}")
        fx["att_def_spread"] = 0.0
        fx["decile_info"] = map_to_decile(0.0, fx.get("league"))  # 降级为均衡档
        return 0.0
    
    fx["att_def_spread"] = round(spread, 1)
    fx["decile_info"] = map_to_decile(spread, fx.get("league"))
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
def generate_report(fixtures: list[dict], bets: list[dict], stats: dict, all_candidates: list[dict] = None, already_selected: set = None) -> str:
    td = get_ops_date().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")

    new_bet_count = len(bets)
    historical_count = len(already_selected) if already_selected else 0  # 包含本轮+历史
    
    lines = [
        f"## ⚽ V2 每日扫描 (HT 1X2) | {td} {now}",
        "",
        f"📊 扫描: {stats['total_scanned']}场 | 本轮新增BET_LOCKED: {new_bet_count}场 | 历史锁定池: {historical_count}场",
        "",
    ]

    # 状态分布摘要
    from collections import Counter
    action_counts = Counter(r.get("action_code", r.get("action", "?")) for r in (all_candidates or []) if r.get("action_code"))
    status_lines = []
    status_lines.append(f"本轮新增BET_LOCKED: {new_bet_count}场")
    today_total = sum(1 for r in all_candidates if r.get("action_code") == "BET_LOCKED")
    if today_total != new_bet_count:
        status_lines.append(f"今日累计BET_LOCKED: {today_total}场")
    status_lines.append(f"历史锁定池: {historical_count}场")
    if action_counts.get("WATCH_EARLY"): status_lines.append(f"👁️ WATCH_EARLY: {action_counts['WATCH_EARLY']}场")
    if action_counts.get("CANDIDATE"): status_lines.append(f"🟡 CANDIDATE: {action_counts['CANDIDATE']}场")
    if action_counts.get("ODDS_OUT"): status_lines.append(f"⚠️ ODDS_OUT: {action_counts['ODDS_OUT']}场")
    if action_counts.get("WATCH_HIGH"): status_lines.append(f"👁️ WATCH_HIGH(≥2.90): {action_counts['WATCH_HIGH']}场")
    if action_counts.get("SKIP_LOW"): status_lines.append(f"❌ SKIP_LOW(<2.00): {action_counts['SKIP_LOW']}场")
    lines.extend(status_lines)
    
    # 口径冲突检测
    if new_bet_count == 0 and today_total > 0:
        lines.append("⚠️ 口径冲突: 历史锁定池有累计但本轮0新增")
    lines.append("")

    if not bets:
        lines.append("> 本轮无正式 BET_LOCKED，不执行投注。")
        return "\n".join(lines)

    for i, rec in enumerate(bets, 1):
        mprobs = rec["model_probs"]
        odds_D = rec["offered_odds_D"]
        ac = rec.get("action_code", rec.get("action", "-"))
        ss = rec.get("scan_stage", "-")
        lk_odds = rec.get("locked_odds_D")
        fos = rec.get("final_odds_status", "")
        
        # 状态标签
        status_tag = "🔒 正式锁定" if ac == "BET_LOCKED" else ("🟡 候选" if ac == "CANDIDATE" else ("👁️ 观察" if "WATCH" in str(ac) else ac))
        lines.append(f"### {i}. {rec['home']} vs {rec['away']} → {status_tag}")
        lines.append("")
        lines.append(f"| 维度 | 数据 |")
        lines.append(f"|------|------|")
        lines.append(f"| ⏰ 开赛 | {rec.get('time_bj', '?')} |")
        lines.append(f"| ⏱ 扫描阶段 | {ss} ({rec.get('minutes_to_kickoff', '?')}分钟) |")
        lines.append(f"| 🏟 联赛 | {rec['league_name']} |")
        lines.append(f"| 💰 {rec.get('bookmaker', '?')} 半场平 | **{odds_D:.2f}** |")
        lines.append(f"| 📐 att_def_spread | {rec.get('att_def_spread', '?')} (档{rec['decile']}) |")
        lines.append(f"| 🎯 公平概率 | H={mprobs['H']:.3f} D={mprobs['D']:.3f} A={mprobs['A']:.3f} |")
        lines.append(f"| 🏦 市场概率 | H={rec['market_probs']['H']:.3f} D={rec['market_probs']['D']:.3f} A={rec['market_probs']['A']:.3f} |")
        lines.append(f"| 💰 {rec.get('bookmaker', '?')} 半场平 | **{odds_D:.2f}** |")
        lines.append(f"| 📊 保本概率 | {rec['break_even_prob']:.3f} |")
        lines.append(f"| 🎲 Edge | {rec.get('edge_pp', 0)*100:+.1f}% (仅记录) |")
        lines.append(f"| 📈 EV | {rec.get('ev_pct', 0)*100:+.1f}% (仅记录) |")
        si = rec.get("stake_info", {})
        if si:
            lines.append(f"| 💵 注码 | {si.get('stake', 1.0):.0f}u (固定1u · Kelly暂停) |")
        if lk_odds and lk_odds != odds_D:
            lines.append(f"| 🔐 锁定价 | {lk_odds:.2f} (结算用) |")
        if fos == "MOVED_OUT_AFTER_LOCK":
            lines.append(f"| ⚠️ 状态 | 锁定后赔率漂出，按锁定价结算 |")
        elif fos == "MOVED_OUT_BEFORE_LOCK":
            lines.append(f"| ⚠️ 状态 | 曾入区间但未锁定已漂出 |")
        lines.append("")

    lines.append("")
    lines.append(f"> 🤖 V2 v2.3.1 · T-90m/T-45m唯一锁定 · 早盘候选不锁")
    lines.append(f"> ⚠️ 本轮无正式 BET_LOCKED，不执行投注。" if new_bet_count == 0 else f"> 🔒 本轮 {new_bet_count} 场 BET_LOCKED")

    return "\n".join(lines)


def run_once(run_tag="DEFAULT", quick_mode=False):
    """quick_mode: 只刷新赔率，跳过 Predictions 和矩阵重建"""
    print("=" * 60)
    print(f"V2 Daily Runner v2.3.1 KICKOFF_RELATIVE (HT 1X2) | TAG: {run_tag} | {'QUICK' if quick_mode else 'FULL'}")
    print(f"启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── 任务监控 ──
    is_pool = "DAILY_POOL" in str(run_tag)
    wd = v2_pool_watchdog() if is_pool else v2_window_checker_watchdog(str(run_tag).lower())
    wd.start(total_items=0)

    # 🌟 读取今日已锁定比赛 (防止三频重复下单)
    today_str = get_ops_date().strftime("%Y%m%d")
    state_file = STATE_DIR / f"selected_fixtures_{today_str}.json"
    already_selected = set()
    fixture_state = {}
    if state_file.exists():
        with open(state_file, "r") as f:
            state_payload = json.load(f)
            if isinstance(state_payload, list):
                # Backward compatible with old format
                already_selected = set(state_payload)
                fixture_state = {}
            elif isinstance(state_payload, dict):
                already_selected = set(state_payload.get("selected_fixture_ids", []))
                fixture_state = state_payload.get("fixtures", {}) or {}
        logger.info(f"💾 状态机: 今日已有 {len(already_selected)} 场被锁定")

    fixtures = fetch_today_fixtures()
    if not fixtures:
        print("\n> 今日无比赛，退出")
        return

    fixtures = fetch_details(fixtures, quick_mode=quick_mode)

    # 💰 实例化真实资金池 (P0 修复: 打通 bankroll.py 经脉)
    br = Bankroll()
    # 🚑 早盘伤停折损引擎 (Phase 2)
    injury_engine = InjuryAttritionEngine()

    logger.info(f"[3/7] 计算 att_def_spread + 伤停折损修正 (Phase 2.2)...")
    for fx in fixtures:
        base_spread = calc_spread(fx)
        orig_bin = fx["decile_info"]["decile"]

        attrition = injury_engine.calculate_attrition(fx["id"], fx["homeId"], fx["awayId"])
        delta_home = attrition["delta_home"]
        delta_away = attrition["delta_away"]

        # 初始化
        fx["attrition_flag"] = False
        fx["delta_home"] = delta_home
        fx["delta_away"] = delta_away
        fx["base_spread"] = base_spread
        fx["adj_spread"] = base_spread
        fx["orig_bin"] = orig_bin
        fx["adj_bin"] = orig_bin
        fx["bin_jump_size"] = 0
        fx["attrition_boost_candidate"] = False  # 🌟 Boost 地基

        if delta_home > 0 or delta_away > 0:
            adj_spread = round(base_spread - delta_home + delta_away, 1)
            adj_decile_info = map_to_decile(adj_spread, fx.get("league"))
            adj_bin = adj_decile_info["decile"]
            jump_size = abs(orig_bin - adj_bin)

            fx["att_def_spread"] = adj_spread
            fx["decile_info"] = adj_decile_info
            fx["attrition_flag"] = True
            fx["adj_spread"] = adj_spread
            fx["adj_bin"] = adj_bin
            fx["bin_jump_size"] = jump_size
            fx["attrition_details"] = attrition["details"]

            # 🌟 触发 Boost: 有伤停且引起实质性档位跳变
            if jump_size >= 1:
                fx["attrition_boost_candidate"] = True

            logger.info(f"  🚑 伤停修正! {fx['home']} vs {fx['away']} | 档位: [{orig_bin}]->[{adj_bin}] | Boost: {fx['attrition_boost_candidate']}")
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
        "skip_odds_band": 0,
        "watch_odds_high": 0,
        "bet_placed": 0,
        "stage_early_watch": 0,
        "stage_candidate": 0,
        "stage_too_late": 0,
    }
    
    all_candidates = []  # 全量追踪：每场都有记录 (含SKIP死因)
    bets = []            # 仅 BET 的用于推荐+预测
    
    for fx in fixtures:
        row = fx.get("decile_info")
        if not row:
            continue
        stats["total_scanned"] += 1
        
        # ── 基础骨架：保证任何阶段 SKIP 都有完整记录 ──
        fid_key = str(fx["id"])
        fstate = fixture_state.get(fid_key, {}) or {}
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
            "attrition_flag": fx.get("attrition_flag", False),
            "delta_home": fx.get("delta_home", 0),
            "delta_away": fx.get("delta_away", 0),
            "base_spread": fx.get("base_spread"),
            "adj_spread": fx.get("adj_spread"),
            "origin_bin": fx.get("orig_bin", row["decile"]),
            "adj_bin": fx.get("adj_bin", row["decile"]),
            "bin_jump_size": fx.get("bin_jump_size", 0),
            "attrition_boost_candidate": fx.get("attrition_boost_candidate", False),
            "attrition_details": fx.get("attrition_details", []),
            # 🌟 Strategy Router 数据契约 (Phase 3)
            "strategy_id": "V2_HT_DRAW",
            "priority": 50,
            "max_risk_units": 1,
            # 🌟 时序雷达字段
            "scan_tag": run_tag,
            "scan_time_utc": datetime.now(timezone.utc).isoformat(),
            "scan_time_local": datetime.now().isoformat(),
            # v2.3.1 action/state extensions
            "action_code": None,
            "locked_stage": fstate.get("locked_stage"),
            "locked_odds_D": fstate.get("locked_odds_D"),
            "locked_time": fstate.get("locked_time"),
            "final_observed_odds_D": fstate.get("final_observed_odds_D"),
            "final_odds_status": fstate.get("final_odds_status"),
        }
        
        # ── V2.3 开赛相对时间扫描阶段 ──
        try:
            ko_str = str(fx.get("date", "")).replace("Z", "+00:00")
            ko_dt = datetime.fromisoformat(ko_str)
            if ko_dt.tzinfo is None:
                ko_dt = ko_dt.replace(tzinfo=LOCAL_TZ)
            else:
                ko_dt = ko_dt.astimezone(LOCAL_TZ)
        except Exception:
            ko_dt = None
        minutes_to_ko = None
        scan_stage = "FAR_FUTURE"
        if ko_dt:
            now_local = datetime.now(LOCAL_TZ)
            minutes_to_ko = int((ko_dt - now_local).total_seconds() / 60)
            if minutes_to_ko < 0:
                scan_stage = "STARTED_OR_CLOSED"
            elif minutes_to_ko <= 15:
                scan_stage = "T_MINUS_15M"
            elif minutes_to_ko <= 45:
                scan_stage = "T_MINUS_45M"
            elif minutes_to_ko <= 90:
                scan_stage = "T_MINUS_90M"
            elif minutes_to_ko <= 180:
                scan_stage = "T_MINUS_3H"
            elif minutes_to_ko <= 360:
                scan_stage = "T_MINUS_6H"
            elif minutes_to_ko <= 720:
                scan_stage = "T_MINUS_12H"
        base_rec["scan_stage"] = scan_stage
        base_rec["minutes_to_kickoff"] = minutes_to_ko
        
        market_odds = fx.get("_ht_1x2") or {}
        odds_D = market_odds.get("D")
        odds_H = market_odds.get("H")
        odds_A = market_odds.get("A")
        bookmaker = market_odds.get("bookmaker", "?")
        
        if not odds_D or not odds_H or not odds_A:
            stats["skip_no_market"] += 1
            base_rec.update({
                "action": "SKIP",
                "action_code": "FINAL_RECORD" if scan_stage in ("T_MINUS_45M", "T_MINUS_15M", "STARTED_OR_CLOSED") else "WATCH_EARLY",
                "skip_code": "NO_MARKET",
                "skip_reason": "HT 1X2盘口未开",
            })
            # persist final state
            fixture_state[fid_key] = {
                **fstate,
                "seen_in_band": bool(fstate.get("seen_in_band", False)),
                "last_seen_time": datetime.now(timezone.utc).isoformat(),
                "final_observed_odds_D": None,
                "final_odds_status": "NO_MARKET",
                "locked_stage": fstate.get("locked_stage"),
                "locked_odds_D": fstate.get("locked_odds_D"),
                "locked_time": fstate.get("locked_time"),
            }
            all_candidates.append(base_rec)
            continue
        
        market_probs = {"H": round(1/odds_H, 4), "D": round(1/odds_D, 4), "A": round(1/odds_A, 4)}
        prob_D = 1 / row["fair_D"] if row.get("fair_D") else 0  # fair_D 存的是赔率, 需转概率
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
        
        # ── V2.2 赔率带筛选（替代 EV 排序）──
        # EV/edge 只记录不筛选，暂存原值供后续校准
        base_rec["ev_pct"] = ev_pct
        base_rec["edge_pp"] = edge_pp
        
        # update state snapshot
        now_utc = datetime.now(timezone.utc).isoformat()
        seen_in_band = bool(fstate.get("seen_in_band", False))
        in_band_now = 2.00 <= odds_D < 2.90
        if in_band_now:
            seen_in_band = True
        final_status = "IN_BAND" if in_band_now else ("ABOVE_BAND" if odds_D >= 2.90 else "BELOW_BAND")
        fixture_state[fid_key] = {
            **fstate,
            "seen_in_band": seen_in_band,
            "last_seen_time": now_utc,
            "last_seen_stage": scan_stage,
            "last_seen_odds_D": odds_D,
            "final_observed_odds_D": odds_D,
            "final_odds_status": final_status,
            "locked_stage": fstate.get("locked_stage"),
            "locked_odds_D": fstate.get("locked_odds_D"),
            "locked_time": fstate.get("locked_time"),
        }

        # 赔率过低：不做
        if odds_D < 2.00:
            stats["skip_odds_band"] = stats.get("skip_odds_band", 0) + 1
            if seen_in_band:
                moved_status = "MOVED_OUT_AFTER_LOCK" if fstate.get("locked_odds_D") else "MOVED_OUT_BEFORE_LOCK"
                st = fixture_state.get(fid_key, {}) or {}
                st["final_odds_status"] = moved_status
                st["final_observed_odds_D"] = odds_D
                fixture_state[fid_key] = st
                base_rec.update({
                    "action": "WATCH_ONLY",
                    "action_code": "ODDS_OUT",
                    "skip_code": "ODDS_OUT_LOW",
                    "skip_reason": f"曾在区间内，现漂出到 {odds_D:.2f} (<2.00)",
                    "final_odds_status": moved_status,
                })
            else:
                base_rec.update({
                    "action": "SKIP",
                    "action_code": "SKIP_LOW",
                    "skip_code": "ODDS_TOO_LOW",
                    "skip_reason": f"赔率 {odds_D:.2f} < 2.00",
                })
            all_candidates.append(base_rec)
            continue
        
        # 赔率过高：进入观察池
        if odds_D >= 2.90:
            stats["watch_odds_high"] = stats.get("watch_odds_high", 0) + 1
            if seen_in_band:
                moved_status = "MOVED_OUT_AFTER_LOCK" if fstate.get("locked_odds_D") else "MOVED_OUT_BEFORE_LOCK"
                st = fixture_state.get(fid_key, {}) or {}
                st["final_odds_status"] = moved_status
                st["final_observed_odds_D"] = odds_D
                fixture_state[fid_key] = st
                base_rec.update({
                    "action": "WATCH_ONLY",
                    "action_code": "ODDS_OUT",
                    "skip_code": "ODDS_OUT_HIGH",
                    "skip_reason": f"曾在区间内，现漂出到 {odds_D:.2f} (>=2.90)",
                    "strategy_id": "V2_HT_DRAW_ODDS_OUT",
                    "final_odds_status": moved_status,
                })
            else:
                base_rec.update({
                    "action": "WATCH_ONLY",
                    "action_code": "WATCH_HIGH",
                    "skip_code": "ODDS_WATCH_HIGH",
                    "skip_reason": f"赔率 {odds_D:.2f} >= 2.90，进入观察池",
                    "strategy_id": "V2_HT_DRAW_WATCH",
                })
            all_candidates.append(base_rec)
            continue
        
        # ── 主策略 V2_MAIN 2.00-2.90 ──
        # Kelly 暂停，固定 1u
        base_rec["strategy_id"] = "V2_HT_DRAW_v2.3.1_KICKOFF_RELATIVE"
        stake_info = {
            "action": "BET",
            "stake": 1.0,
            "reason": "FIXED_1U | Kelly_OFF | EV_record_only",
            "raw_kelly": 0.0,
            "effective_kelly": 0.0,
            "kelly_factor_used": 0.0,
        }
        base_rec["stake_info"] = stake_info
        
        # ── V2.3.1 开赛相对时间 gating ──
        # T-12h/FAR_FUTURE: WATCH_EARLY
        # T-6h: WATCH_EARLY
        # T-3h: CANDIDATE（不锁）
        # T-90m/T-45m: 唯一允许 BET_LOCKED
        # T-15m/开赛后: FINAL_RECORD
        if scan_stage == "STARTED_OR_CLOSED":
            base_rec.update({
                "action": "WATCH_ONLY",
                "action_code": "FINAL_RECORD",
                "skip_code": "FINAL_RECORD_ONLY",
                "skip_reason": "已开赛/已关闭，仅记录最终状态",
            })
            all_candidates.append(base_rec)
            continue
        if scan_stage in ("FAR_FUTURE", "T_MINUS_12H", "T_MINUS_6H"):
            stats["stage_early_watch"] = stats.get("stage_early_watch", 0) + 1
            base_rec.update({
                "action": "WATCH_ONLY",
                "action_code": "WATCH_EARLY",
                "skip_code": "STAGE_EARLY",
                "skip_reason": f"{scan_stage} 只记录赔率，不进入锁定",
            })
            all_candidates.append(base_rec)
            continue
        if scan_stage == "T_MINUS_3H":
            stats["stage_candidate"] = stats.get("stage_candidate", 0) + 1
            base_rec.update({
                "action": "WATCH_ONLY",
                "action_code": "CANDIDATE",
                "skip_code": "STAGE_CANDIDATE",
                "skip_reason": "T-3h 候选观察，不锁定",
            })
            all_candidates.append(base_rec)
            continue

        if scan_stage == "T_MINUS_15M":
            stats["stage_too_late"] = stats.get("stage_too_late", 0) + 1
            base_rec.update({
                "action": "WATCH_ONLY",
                "action_code": "FINAL_RECORD",
                "skip_code": "STAGE_TOO_LATE",
                "skip_reason": "T-15m 仅最终记录，不新增推荐",
            })
            all_candidates.append(base_rec)
            continue
        # 非 T-90m/T-45m 不允许锁定
        if scan_stage not in ("T_MINUS_90M", "T_MINUS_45M"):
            base_rec.update({
                "action": "WATCH_ONLY",
                "action_code": "WATCH_EARLY",
                "skip_code": "STAGE_NOT_LOCK_WINDOW",
                "skip_reason": f"{scan_stage} 非锁定窗口",
            })
            all_candidates.append(base_rec)
            continue
        
        # ── 🌟 首次触发去重锁 (Time-Series Signal Lock) ──
        if fx["id"] in already_selected:
            # Keep tracking post-lock status for CLV diagnostics
            st = fixture_state.get(fid_key, {})
            if st.get("locked_odds_D") and odds_D and not (2.00 <= odds_D < 2.90):
                st["final_odds_status"] = "MOVED_OUT_AFTER_LOCK"
            fixture_state[fid_key] = st
            base_rec.update({
                "action": "ALREADY_SELECTED",
                "action_code": "FINAL_RECORD",
                "skip_code": "DUPLICATE",
                "skip_reason": f"今日 [{run_tag}] 前已被锁定",
                "strategy_note": "multi_scan_duplicate",
                "locked_stage": st.get("locked_stage"),
                "locked_odds_D": st.get("locked_odds_D"),
                "locked_time": st.get("locked_time"),
                "final_observed_odds_D": st.get("final_observed_odds_D"),
                "final_odds_status": st.get("final_odds_status"),
            })
            all_candidates.append(base_rec)
            continue

        # ── 通过！暂入候选池，联赛去重+日上限稍后统一处理 ──
        stats["bet_placed"] += 1
        lock_time = datetime.now(timezone.utc).isoformat()
        fixture_state[fid_key] = {
            **fixture_state.get(fid_key, {}),
            "seen_in_band": True,
            "last_seen_time": lock_time,
            "last_seen_stage": scan_stage,
            "last_seen_odds_D": odds_D,
            "locked": True,
            "locked_stage": scan_stage,
            "locked_odds_D": odds_D,
            "locked_time": lock_time,
            "lock_cancelled": False,
            "lock_cancel_reason": None,
            "final_observed_odds_D": odds_D,
            "final_odds_status": "LOCKED_IN_BAND",
        }
        base_rec.update({
            "action": "BET",
            "action_code": "BET_LOCKED",
            "skip_code": None,
            "skip_reason": None,
            "locked_stage": scan_stage,
            "locked_odds_D": odds_D,
            "locked_time": lock_time,
            "final_observed_odds_D": odds_D,
            "final_odds_status": "LOCKED_IN_BAND",
        })
        all_candidates.append(base_rec)
        bets.append(base_rec)
        already_selected.add(fx["id"])
        logger.success(f"  ✅ {fx['home']}vs{fx['away']}: 推D odds={odds_D:.2f} edge={edge_pp*100:+.1f}% ev={ev_pct*100:+.1f}%")
    
    # ── 联赛去重：每天每联赛最多2场 ──
    bets.sort(key=lambda x: -(x["ev_pct"] or 0))
    lg_count = {}
    league_deduped = []
    league_skipped = []
    for r in bets:
        lg = r["league_name"]
        lg_count[lg] = lg_count.get(lg, 0) + 1
        if lg_count[lg] <= 2:
            league_deduped.append(r)
        else:
            league_skipped.append(r)
            r["action"] = "SKIP"
            r["action_code"] = "FINAL_RECORD"
            r["skip_code"] = "LEAGUE_CAP"
            r["skip_reason"] = f"{lg} 已满2场"
            # unlock if it was pre-locked in this pass
            fid = r.get("fixture_id")
            if fid in already_selected:
                already_selected.discard(fid)
            st = fixture_state.get(str(fid), {}) or {}
            st["locked"] = False
            st["locked_stage"] = None
            st["locked_odds_D"] = None
            st["locked_time"] = None
            st["lock_cancelled"] = True
            st["lock_cancel_reason"] = "LEAGUE_CAP"
            st["final_odds_status"] = "LOCK_CANCELLED_LEAGUE_CAP"
            fixture_state[str(fid)] = st
    
    # ── 日上限20场（在联赛去重之后）──
    final_bets = league_deduped[:20]
    daily_capped = league_deduped[20:]
    for r in daily_capped:
        r["action"] = "SKIP"
        r["action_code"] = "FINAL_RECORD"
        r["skip_code"] = "DAILY_CAP"
        r["skip_reason"] = "日上限20场（联赛去重后）"
        fid = r.get("fixture_id")
        if fid in already_selected:
            already_selected.discard(fid)
        st = fixture_state.get(str(fid), {}) or {}
        st["locked"] = False
        st["locked_stage"] = None
        st["locked_odds_D"] = None
        st["locked_time"] = None
        st["lock_cancelled"] = True
        st["lock_cancel_reason"] = "DAILY_CAP"
        st["final_odds_status"] = "LOCK_CANCELLED_DAILY_CAP"
        fixture_state[str(fid)] = st
    bets = final_bets
    stats["league_skipped"] = len(league_skipped)
    stats["daily_capped"] = len(daily_capped)
    
    # ── 漏斗日报 ──
    logger.info("="*40)
    logger.info("📊 V2 今日漏斗扫描日报")
    logger.info(f"📦 原始赛程总数: {stats['total_fixtures']}")
    logger.info(f"🔍 进模型分档场次: {stats['total_scanned']}")
    logger.info(f"❌ 过滤 (盘口未开): {stats['skip_no_market']}")
    logger.info(f"❌ 过滤 (赔率<2.00): {stats.get('skip_odds_band',0)}")
    logger.info(f"👁️ 观察池 (赔率>=2.90): {stats.get('watch_odds_high',0)}")
    logger.info(f"✅ 主策略 V2_MAIN (2.00-2.90 固定1u): {stats['bet_placed']}")
    logger.info(f"🔻 联赛去重: {stats.get('league_skipped',0)}")
    logger.info(f"🔻 日上限截断: {stats.get('daily_capped',0)}")
    logger.info(f"👁️ WATCH_ONLY (>=2.90): {stats.get('watch_odds_high',0)}")
    logger.info(f"❌ SKIP (<2.00): {stats.get('skip_odds_band',0)}")
    logger.info(f"🎯 最终推荐: {len(bets)}")
    logger.info(f"⏰ 早盘观察 (T-12h/T-6h): {stats.get('stage_early_watch',0)}")
    logger.info(f"⏰ 候选观察 (T-3h): {stats.get('stage_candidate',0)}")
    logger.info(f"⏰ 过晚跳过 (T-15m): {stats.get('stage_too_late',0)}")
    logger.info(f"📊 漏斗: 候选{stats['bet_placed']} → 去重后{stats['bet_placed']-stats.get('league_skipped',0)} → 上限后{len(bets)}")
    logger.info(f"📏 Kelly暂停 · EV仅记录 · 每日上限20场")
    logger.info("="*40)

    # ── 🌎 全量候选池快照 (基准防线 · 专家建议三) ──
    universe = []
    today_str = get_ops_date().strftime('%Y%m%d')
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
    report = generate_report(fixtures, bets, stats, all_candidates, already_selected)
    report_path = REPORT_DIR / f"daily_{get_ops_date().strftime('%Y%m%d')}.md"
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"  → {report_path}")
    
    # ── 保存全量死因追踪 (三频合并, 复合主键去重) ──
    scan_path = REPORT_DIR / f"full_scan_{get_ops_date().strftime('%Y%m%d')}.json"
    existing_full = []
    existing_scan_keys = set()
    if scan_path.exists():
        try:
            with open(scan_path) as f:
                existing_data = json.load(f)
                existing_full = existing_data.get("candidates", [])
                # 🌟 复合主键: fixture_id + scan_tag, 三频快照互不吞食
                existing_scan_keys = {
                    f"{p['fixture_id']}_{p.get('scan_tag', 'DEFAULT')}"
                    for p in existing_full if isinstance(p, dict)
                }
                # 累计漏斗统计
                if isinstance(existing_data.get("stats"), dict):
                    for k in stats:
                        stats[k] = stats.get(k, 0) + existing_data["stats"].get(k, 0)
        except Exception:
            pass
    merged_full = existing_full + [
        p for p in all_candidates
        if f"{p['fixture_id']}_{p.get('scan_tag', 'DEFAULT')}" not in existing_scan_keys
    ]
    with open(scan_path, "w") as f:
        json.dump({"date": get_ops_date().isoformat(), "stats": stats, "candidates": merged_full}, f, ensure_ascii=False, indent=2)
    logger.info(f"📋 全量死因追踪: {len(merged_full)} 场 (新增 {len(all_candidates)}) → {scan_path}")

    logger.info(f"[7/7] 输出日报 + 保存预测")
    print()
    print(report)

    # 保存预测 (🔍 仅 BET_LOCKED 记录 → paper_trading.py 结算用)
    pred_save = []
    for rec in bets:
        st = fixture_state.get(str(rec["fixture_id"]), {})
        pred_save.append({
            "fixture_id": rec["fixture_id"],
            "date": get_ops_date().isoformat(),
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
            "locked_stage": rec.get("locked_stage") or st.get("locked_stage"),
            "locked_odds_D": rec.get("locked_odds_D") or st.get("locked_odds_D"),
            "locked_time": rec.get("locked_time") or st.get("locked_time"),
            "lock_cancelled": bool(st.get("lock_cancelled", False)),
            "lock_cancel_reason": st.get("lock_cancel_reason"),
            "final_observed_odds_D": st.get("final_observed_odds_D"),
            "final_odds_status": st.get("final_odds_status"),
            "break_even_prob": rec["break_even_prob"],
            "edge_pp": rec["edge_pp"],
            "ev_pct": rec["ev_pct"],
            "stake_info": rec.get("stake_info", {}),
            "action": rec["action"],
            "action_code": rec.get("action_code"),
            "bookmaker": rec.get("bookmaker", "?"),
            # Strategy Router 契约
            "strategy_id": rec.get("strategy_id", "V2_HT_DRAW"),
            "attrition_flag": rec.get("attrition_flag", False),
            "attrition_boost_candidate": rec.get("attrition_boost_candidate", False),
        })

    pred_path = REPORT_DIR / f"predictions_{get_ops_date().strftime('%Y%m%d')}.json"
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
    # Merge by fixture_id and keep latest state fields for already-locked fixtures.
    merged_map = {int(p["fixture_id"]): p for p in existing if isinstance(p, dict) and p.get("fixture_id") is not None}
    for p in pred_save:
        merged_map[int(p["fixture_id"])] = p
    # Backfill final observed odds/status from state for any locked fixture already in prediction file.
    for fid_int, p in list(merged_map.items()):
        st = fixture_state.get(str(fid_int), {})
        p["lock_cancelled"] = bool(st.get("lock_cancelled", p.get("lock_cancelled", False)))
        p["lock_cancel_reason"] = st.get("lock_cancel_reason", p.get("lock_cancel_reason"))
        if st.get("lock_cancelled"):
            p["locked_stage"] = None
            p["locked_odds_D"] = None
            p["locked_time"] = None
            p["moved_out_after_lock"] = False
            p["final_odds_status"] = st.get("final_odds_status", p.get("final_odds_status"))
            p["final_observed_odds_D"] = st.get("final_observed_odds_D", p.get("final_observed_odds_D"))
            continue
        if st.get("locked_odds_D"):
            p["locked_stage"] = p.get("locked_stage") or st.get("locked_stage")
            p["locked_odds_D"] = p.get("locked_odds_D") or st.get("locked_odds_D")
            p["locked_time"] = p.get("locked_time") or st.get("locked_time")
            p["final_observed_odds_D"] = st.get("final_observed_odds_D")
            p["final_odds_status"] = st.get("final_odds_status")
            if st.get("final_odds_status") == "MOVED_OUT_AFTER_LOCK":
                p["moved_out_after_lock"] = True
    merged = [merged_map[k] for k in sorted(merged_map.keys())]
    with open(pred_path, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    logger.info(f"\n预测数据: {pred_path}")

    # 🌟 写入状态机，把锁定的比赛传给下一个 Cron
    with open(state_file, "w") as f:
        json.dump(
            {
                "selected_fixture_ids": sorted(list(already_selected)),
                "fixtures": fixture_state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"🔒 状态机: {len(already_selected)} 场比赛已锁定 → {state_file}")

    # ── 任务监控：完成 ──
    bets_count = len([r for r in all_candidates if r.get("action_code") == "BET_LOCKED"])
    wd.finish(status="DONE", output_files={"predictions": str(pred_path), "state": str(state_file)})

    # 结算已分离至独立 Cron: python3 engine/paper_trading.py --verify-yesterday


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_tag", type=str, default="MANUAL", help="运行时段标识")
    parser.add_argument("--quick", action="store_true", help="快速模式：只刷新赔率，跳过Predictions")
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()

    if args.watch:
        print("持续监控模式 (不再推荐，请使用 Cron)")
        import schedule as sched
        sched.every().day.at("12:00").do(run_once, run_tag="DAILY_POOL", quick_mode=False)
        for hour in range(24):
            sched.every().day.at(f"{hour:02d}:00").do(run_once, run_tag=f"HOURLY_{hour:02d}", quick_mode=True)
        while True:
            sched.run_pending()
            time.sleep(60)
    else:
        run_once(run_tag=args.run_tag, quick_mode=args.quick)
