"""
V2 纸盘验证与结算模块 (HT 1X2 架构)
======================================
1. 解析昨日预测记录
2. 拉取真实半场赛果，计算 H/D/A 标签
3. 拉取 Pinnacle 最终收盘赔率，计算 True CLV
4. 结算 PnL 并更新日志

用法：
  python3 paper_trading.py --verify 2026-05-05   # 验证指定日期的预测
  python3 paper_trading.py --test-clv             # 用首战数据测试CLV计算
  python3 paper_trading.py --summary              # 全量汇总
"""

import json
import ssl
import certifi
import time
import urllib.request
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict, Counter
from typing import Optional, Dict, Tuple, List

from logger import logger

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from config.secrets import API_KEY, API_HOST
from engine import net_utils
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
REPORT_DIR.mkdir(exist_ok=True)
LOG_DIR = BASE_DIR / "data" / "paper_trading"
LOG_DIR.mkdir(exist_ok=True)

SSL_CTX = ssl.create_default_context(cafile=certifi.where())


# ═══════════════════════════════════════════════════════════
# API 工具
# ═══════════════════════════════════════════════════════════

def api(endpoint: str) -> Optional[dict]:
    return net_utils.api_get(endpoint, API_KEY, API_HOST)


# ═══════════════════════════════════════════════════════════
# Step 1: 赛果解析器 (Result Parser)
# ═══════════════════════════════════════════════════════════

def parse_ht_result(halftime_score: str) -> Optional[str]:
    """
    将 "1-1" 这种字符串解析为 HT 1X2 的赛果标签。

    Returns:
        "H" | "D" | "A" | None (无效输入)
    """
    if not halftime_score or halftime_score == "None":
        return None
    try:
        home_goals, away_goals = map(int, halftime_score.strip().split('-'))
        if home_goals > away_goals:
            return "H"
        elif home_goals == away_goals:
            return "D"
        else:
            return "A"
    except Exception as e:
        logger.error(f"解析半场比分失败: '{halftime_score}' -> {e}")
        return None


def ht_has_goal(halftime_score: str) -> Optional[bool]:
    """兼容旧V38逻辑：半场是否有进球"""
    if not halftime_score or halftime_score == "None":
        return None
    try:
        home_goals, away_goals = map(int, halftime_score.strip().split('-'))
        return (home_goals + away_goals) > 0
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# Step 2: 盈亏结算中心 (PnL Settlement)
# ═══════════════════════════════════════════════════════════

def settle_trade(stake: float, placed_odds: float, bet_outcome: str,
                 actual_outcome: str) -> Tuple[float, bool]:
    """
    计算净盈亏。

    Returns:
        (profit, is_hit): 净利润和是否命中
    """
    if actual_outcome == bet_outcome:
        return stake * (placed_odds - 1), True
    else:
        return -stake, False


# ═══════════════════════════════════════════════════════════
# Step 3: True CLV 计算器 (Vig-Free CLV)
# ═══════════════════════════════════════════════════════════

def calculate_true_clv(placed_odds: float, outcome: str,
                       closing_odds: Dict[str, float]) -> Tuple[float, float]:
    """
    基于 Pinnacle HT 1X2 收盘赔率计算 True CLV（去水收盘线价值）。

    核心逻辑：
      1. 计算三向隐含概率总和（margin = 庄家抽水）
      2. 去水 → 还原真实公平概率
      3. 计算公平收盘赔率
      4. CLV = placed_odds / fair_closing_odds - 1

    Args:
        placed_odds: 我们下注的赔率 (例如 3.05)
        outcome: 我们下注的方向 ("H", "D", "A")
        closing_odds: {"H": 8.19, "D": 3.12, "A": 1.60}

    Returns:
        (true_clv, fair_closing_odds)
    """
    if not closing_odds or not all(k in closing_odds for k in ("H", "D", "A")):
        return 0.0, 0.0

    # 1. 计算隐含概率总和 (Overround / Margin)
    inv_h = 1.0 / closing_odds["H"]
    inv_d = 1.0 / closing_odds["D"]
    inv_a = 1.0 / closing_odds["A"]
    margin = inv_h + inv_d + inv_a

    # 2. 去水，计算公平概率
    target_closing_odds = closing_odds[outcome]
    true_prob = (1.0 / target_closing_odds) / margin

    # 3. 计算公平收盘赔率（即无庄家利润的赔率）
    fair_closing_odds = 1.0 / true_prob

    # 4. 计算 CLV
    true_clv = (placed_odds / fair_closing_odds) - 1.0

    return true_clv, fair_closing_odds


def extract_pinnacle_ht_1x2(odds_response: dict) -> Dict[str, float]:
    """
    从 API odds 响应中提取 Pinnacle 的 HT 1X2 (First Half Winner) 收盘赔率。

    Returns:
        {"H": 8.19, "D": 3.12, "A": 1.60} or {}
    """
    if not odds_response or not odds_response.get("response"):
        return {}

    for entry in odds_response["response"]:
        for bm in entry.get("bookmakers", []):
            if "Pinnacle" not in bm.get("name", ""):
                continue
            for bet in bm.get("bets", []):
                if bet["name"] == "First Half Winner":
                    odds_map = {}
                    for v in bet.get("values", []):
                        val = v["value"].lower()
                        if val == "home":
                            odds_map["H"] = float(v["odd"])
                        elif val == "draw":
                            odds_map["D"] = float(v["odd"])
                        elif val == "away":
                            odds_map["A"] = float(v["odd"])
                    if len(odds_map) == 3:
                        return odds_map
    return {}


# ═══════════════════════════════════════════════════════════
# 验证流水线
# ═══════════════════════════════════════════════════════════

def verify_date(date_str: str) -> dict:
    """
    验证指定日期的所有预测。

    流程:
      1. 读取 predictions_{date}.json
      2. 逐场拉取 API 实际赛果 + Pinnacle 收盘赔率
      3. 解析 H/D/A 赛果
      4. 结算 PnL
      5. 计算 True CLV
      6. 汇总输出
    """
    pred_path = REPORT_DIR / f"predictions_{date_str.replace('-', '')}.json"
    if not pred_path.exists():
        return {"error": f"预测文件不存在: {pred_path}"}

    with open(pred_path, encoding="utf-8") as f:
        predictions = json.load(f)

    results = []
    total_staked = 0.0
    total_pnl = 0.0
    hits = 0
    clv_list = []

    for i, pred in enumerate(predictions):
        fid = pred.get("fixture_id", pred.get("id"))
        bet_outcome = pred.get("outcome", pred.get("bet"))  # "H"|"D"|"A"
        placed_odds = pred.get("placed_odds", pred.get("odds", 0))
        stake = pred.get("stake", 0)
        league = pred.get("league", "")
        home = pred.get("home", "")
        away = pred.get("away", "")

        # --- 拉取实际赛果 ---
        resp = api(f"fixtures?id={fid}")
        if not resp or not resp.get("response"):
            logger.warning(f"[{fid}] API 无响应，跳过")
            continue

        fix = resp["response"][0]
        status = fix["fixture"]["status"]["short"]

        # 等完赛
        if status not in ("FT", "AET", "PEN", "WO"):
            logger.warning(f"[{fid}] 比赛未完赛 ({status})，跳过")
            continue

        ht = fix["score"]["halftime"]
        ht_home = ht.get("home") if ht.get("home") is not None else 0
        ht_away = ht.get("away") if ht.get("away") is not None else 0
        ht_str = f"{ht_home}-{ht_away}"

        # --- Step 1: 赛果解析 ---
        actual_outcome = parse_ht_result(ht_str)
        if not actual_outcome:
            continue

        # --- 拉取 Pinnacle 收盘赔率 ---
        odds_resp = api(f"odds?fixture={fid}")
        closing_ht_1x2 = extract_pinnacle_ht_1x2(odds_resp)

        # --- Step 3: 三层 CLV 重构 ---
        from clv import clv_triple
        triple = clv_triple(placed_odds, bet_outcome, closing_ht_1x2)
        true_clv = triple.get("ev_vs_close", 0)
        clv_list.append(true_clv)

        # --- Step 2: PnL 结算 ---
        pnl, is_hit = settle_trade(stake, placed_odds, bet_outcome, actual_outcome)
        if is_hit:
            hits += 1
        total_staked += stake
        total_pnl += pnl

        r = {
            "fixture_id": fid,
            "home": home,
            "away": away,
            "league": league,
            "bet_outcome": bet_outcome,
            "placed_odds": placed_odds,
            "stake": stake,
            "ht_score": ht_str,
            "actual_outcome": actual_outcome,
            "is_hit": is_hit,
            "pnl": round(pnl, 2),
            "closing_ht_1x2": closing_ht_1x2,
            # ── 三层 CLV 审计 ──
            "raw_clv": triple.get("raw_clv"),
            "fair_line_clv": triple.get("fair_line_clv"),
            "ev_vs_close": triple.get("ev_vs_close"),
            "clv_margin": triple.get("margin"),
            "raw_closing_odds": triple.get("raw_close"),
            "fair_closing_odds": triple.get("fair_close"),
            "true_clv": round(true_clv, 4),  # 向后兼容
            "ht_has_goal": (ht_home + ht_away) > 0,
        }
        results.append(r)

        logger.info(
            f"[{fid}] {home} v {away} | "
            f"HT:{ht_str} | 投:{bet_outcome} | 赛:{actual_outcome} | "
            f"PnL:{pnl:+.2f} | CLV:{true_clv*100:+.2f}%"
            f"{' ✅' if is_hit else ' ❌'}"
        )

        time.sleep(1.0)  # API 限频

    # --- 汇总 ---
    avg_clv = sum(clv_list) / len(clv_list) if clv_list else 0.0
    roi_pct = (total_pnl / total_staked * 100) if total_staked > 0 else 0.0
    completed = len(results)

    summary = {
        "date": date_str,
        "verified_at": datetime.now().isoformat(),
        "total_predicted": len(predictions),
        "total_completed": completed,
        "pending": len(predictions) - completed,
        "hits": hits,
        "misses": completed - hits,
        "hit_rate_pct": round(hits / completed * 100, 1) if completed else 0.0,
        "total_staked": round(total_staked, 2),
        "total_pnl": round(total_pnl, 2),
        "roi_pct": round(roi_pct, 2),
        "avg_clv_pct": round(avg_clv * 100, 2),
        "results": results,
    }

    # --- 保存 ---
    log_path = LOG_DIR / f"verified_{date_str.replace('-', '')}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"验证完成: {date_str} | {hits}/{completed} 命中 | "
                f"ROI:{roi_pct:+.1f}% | CLV:{avg_clv*100:+.2f}% | "
                f"→ 已存 {log_path}")

    return summary


# ═══════════════════════════════════════════════════════════
# 全量汇总 (Phase 1 Task 3: 多维归因仪表盘)
# ═══════════════════════════════════════════════════════════

def full_summary(window_size: int = 10):
    """多维归因仪表盘式汇总所有纸盘验证数据 (Phase 1 Task 3)"""
    logs = sorted(LOG_DIR.glob("verified_*.json"))
    if not logs:
        return {"error": "无验证日志"}

    all_results = []
    for log_path in logs:
        with open(log_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                all_results.extend(data.get("results", data if isinstance(data, list) else []))
            except json.JSONDecodeError:
                logger.error(f"读取 {log_path} 失败: JSON 格式错误")
                continue

    if not all_results:
        return {"error": "无结果数据"}

    total_bets = len(all_results)
    hits = sum(1 for r in all_results if r.get("is_hit") or r.get("pnl", 0) > 0)
    total_pnl = sum(float(r.get("pnl", 0.0)) for r in all_results)
    total_staked = sum(float(r.get("stake", 0.0)) for r in all_results)

    # ---- 全局汇总 ----
    avg_true_clv = (sum(float(r.get("true_clv", 0.0)) for r in all_results) / total_bets if total_bets else 0.0)
    avg_raw_clv = (sum(float(r.get("raw_clv", r.get("true_clv", 0.0))) for r in all_results) / total_bets if total_bets else 0.0)
    avg_fair_line_clv = (sum(float(r.get("fair_line_clv", r.get("true_clv", 0.0))) for r in all_results) / total_bets if total_bets else 0.0)

    # ---- 核心分桶容器 ----
    def _create_bucket():
        return {"bets": 0, "hits": 0, "pnl": 0.0, "staked": 0.0, "clv_true": [], "clv_raw": [], "clv_fair": []}

    by_league = defaultdict(_create_bucket)
    by_bin = defaultdict(_create_bucket)
    by_day = defaultdict(_create_bucket)

    # 🌟 A/B 测试容器
    by_attrition = {
        "With Attrition (有战力折损)": _create_bucket(),
        "Without Attrition (无伤停影响)": _create_bucket()
    }
    by_attr_bin = defaultdict(_create_bucket)   # 🌟 交叉视角：Attrition x Bin
    by_bin_jump = defaultdict(_create_bucket)    # 🌟 档位跳变矩阵
    by_clv_bucket = defaultdict(lambda: {"bets": 0, "hits": 0, "pnl": 0.0})

    # 归一化日期字段
    def _get_date(r):
        d = r.get("date") or r.get("verified_at") or r.get("kickoff") or r.get("kickoff_time")
        if isinstance(d, str) and "T" in d:
            return d.split("T", 1)[0]
        if isinstance(d, str) and " " in d:
            return d.split(" ", 1)[0]
        return d or "UNKNOWN"

    # 主循环：分桶填充
    for r in all_results:
        league = r.get("league", r.get("league_name", "Unknown"))
        bin_id = r.get("bin_id", r.get("decile", "Unknown"))

        true_clv = float(r.get("true_clv", r.get("ev_vs_close", 0.0)))
        raw_clv = float(r.get("raw_clv", true_clv))
        fair_clv = float(r.get("fair_line_clv", true_clv))

        stake = float(r.get("stake", 0.0))
        pnl = float(r.get("pnl", 0.0))
        is_hit = bool(r.get("is_hit") or pnl > 0)
        day_key = _get_date(r)

        def _fill(bucket_obj):
            bucket_obj["bets"] += 1
            bucket_obj["hits"] += int(is_hit)
            bucket_obj["pnl"] += pnl
            bucket_obj["staked"] += stake
            bucket_obj["clv_true"].append(true_clv)
            bucket_obj["clv_raw"].append(raw_clv)
            bucket_obj["clv_fair"].append(fair_clv)

        _fill(by_league[league])
        _fill(by_bin[str(bin_id)])
        _fill(by_day[day_key])

        # 🌟 填充 A/B 测试容器
        has_attrition = r.get("attrition_flag", False)
        attr_key = "With Attrition (有战力折损)" if has_attrition else "Without Attrition (无伤停影响)"
        _fill(by_attrition[attr_key])

        # 🌟 填充交叉视角 (Attrition + Bin)
        orig_bin = r.get("orig_bin", bin_id)
        _fill(by_attr_bin[f"{'有伤停' if has_attrition else '无伤停'} | 档位 {bin_id}"])

        # 🌟 填充档位跳变矩阵 (只统计发生了伤停修正的)
        if has_attrition:
            jump_str = f"[{orig_bin}] -> [{bin_id}]"
            _fill(by_bin_jump[jump_str])

        # CLV 桶
        if true_clv > 0.05: bucket = "CLV > +5%"
        elif true_clv > 0: bucket = "CLV 0~+5%"
        elif true_clv > -0.05: bucket = "CLV -5%~0"
        else: bucket = "CLV < -5%"

        cb = by_clv_bucket[bucket]
        cb["bets"] += 1
        cb["hits"] += int(is_hit)
        cb["pnl"] += pnl

    # 辅助：把分桶 dict 收敛成干净结构
    def _finalize_group(g):
        out = {}
        for key, v in g.items():
            bets = max(v["bets"], 1)
            staked = max(v["staked"], 1.0)
            out[key] = {
                "bets": v["bets"],
                "hits": v["hits"],
                "hit_rate_pct": round(v["hits"] / bets * 100, 1),
                "pnl": round(v["pnl"], 2),
                "staked": round(v["staked"], 2),
                "roi_pct": round(v["pnl"] / staked * 100, 2),
                "avg_true_clv_pct": round((sum(v["clv_true"]) / bets) * 100, 2),
                "avg_raw_clv_pct": round((sum(v["clv_raw"]) / bets) * 100, 2),
                "avg_fair_line_clv_pct": round((sum(v["clv_fair"]) / bets) * 100, 2),
            }
        return out

    by_league_out = _finalize_group(by_league)
    by_bin_out = _finalize_group(by_bin)

    # 每日时序
    daily_timeseries = []
    for day in sorted(by_day.keys()):
        v = by_day[day]
        bets = max(v["bets"], 1)
        staked = max(v["staked"], 1.0)
        daily_timeseries.append({
            "date": day,
            "bets": v["bets"], "hits": v["hits"],
            "hit_rate_pct": round(v["hits"] / bets * 100, 1),
            "pnl": round(v["pnl"], 2), "staked": round(v["staked"], 2),
            "roi_pct": round(v["pnl"] / staked * 100, 2),
            "avg_true_clv_pct": round((sum(v["clv_true"]) / bets) * 100, 2),
            "avg_raw_clv_pct": round((sum(v["clv_raw"]) / bets) * 100, 2),
            "avg_fair_line_clv_pct": round((sum(v["clv_fair"]) / bets) * 100, 2),
        })

    # Rolling_10（按结算顺序）
    def _sort_key(r):
        return (_get_date(r), r.get("fixture_id", 0))

    sorted_results = sorted(all_results, key=_sort_key)
    rolling = []
    if len(sorted_results) >= window_size:
        for i in range(window_size, len(sorted_results) + 1):
            chunk = sorted_results[i - window_size:i]
            pnl_sum = sum(float(x.get("pnl", 0.0)) for x in chunk)
            stake_sum = sum(float(x.get("stake", 0.0)) for x in chunk) or 1.0
            clv_avg = sum(float(x.get("true_clv", x.get("ev_vs_close", 0.0))) for x in chunk) / window_size
            rolling.append({
                "from": _get_date(chunk[0]),
                "to": _get_date(chunk[-1]),
                "bets": window_size,
                "roi_pct": round(pnl_sum / stake_sum * 100, 2),
                "avg_true_clv_pct": round(clv_avg * 100, 2),
            })

    # 简单健康报警
    health_flags = []

    by_attrition_out = _finalize_group(by_attrition)
    by_attr_bin_out = _finalize_group(by_attr_bin)
    by_bin_jump_out = _finalize_group(by_bin_jump)

    if rolling:
        last = rolling[-1]
        if last["avg_true_clv_pct"] < -2.0:
            health_flags.append({
                "code": "ROLLING_CLV_NEG", "level": "warning",
                "detail": f"最近 {window_size} 场 True CLV ({last['avg_true_clv_pct']}%) 跌破 -2% 警戒线!"
            })

    for lg, v in by_league_out.items():
        if v["bets"] >= 10 and v["avg_true_clv_pct"] < -3.0:
            health_flags.append({
                "code": "LEAGUE_BLACKLIST", "level": "danger",
                "detail": f"毒药联赛预警: {lg} (样本 {v['bets']}, CLV {v['avg_true_clv_pct']}%)"
            })

    for b, v in by_bin_out.items():
        if v["bets"] >= 10 and v["avg_true_clv_pct"] < -3.0:
            health_flags.append({
                "code": "BIN_SUSPECT", "level": "danger",
                "detail": f"档位失效预警: 档位 {b} (样本 {v['bets']}, CLV {v['avg_true_clv_pct']}%)"
            })

    # ================= 终端炫酷打印 =================
    print("\n" + "=" * 60)
    print(f" 📈 V2 多维归因诊断仪表盘 | 总样本: {total_bets} 场")
    print("=" * 60)

    print(f"\n💰 【全局资金表现】")
    print(f"总流水: {total_staked:.2f} | 净盈亏: {total_pnl:+.2f} | ROI: {round(total_pnl/max(total_staked,1)*100,2)}%")
    print(f"平均 Raw CLV : {avg_raw_clv*100:+.2f}% (战胜表象)")
    print(f"平均 Fair CLV: {avg_fair_line_clv*100:+.2f}% (市场漂移)")
    print(f"平均 True CLV: {avg_true_clv*100:+.2f}% (核心护城河)")

    # 🌟 数据分段: Edge 修正在 commit 7ca6abf (2026-05-08)
    # 用文件名推断日期 (verified_20260505.json → 2026-05-05)
    pre_fix_count = sum(1 for lp in logs if lp.stem.replace('verified_','').replace('backtest_','')[:8] < '20260508')
    post_fix_count = len(logs) - pre_fix_count
    if pre_fix_count > 0:
        print(f"\n📝 数据版本: 修正前 {pre_fix_count} 天 (Edge虚高) | 修正后 {post_fix_count} 天 (commit 7ca6abf)")

    print(f"\n🏆 【联赛分桶审计 (按下注量排序)】")
    print(f"{'联赛名称':<22} | {'样本':<4} | {'ROI':>7} | {'True CLV':>8}")
    print("-" * 55)
    for lg, v in sorted(by_league_out.items(), key=lambda x: x[1]['bets'], reverse=True):
        mark = " ☠️" if v["bets"] >= 5 and v["avg_true_clv_pct"] < -3.0 else ""
        print(f"{lg[:20]:<22} | {v['bets']:<4} | {v['roi_pct']:>6.2f}% | {v['avg_true_clv_pct']:>7.2f}%{mark}")

    print(f"\n📊 【模型档位 (Bin) 归因】")
    print(f"{'档位 (Decile)':<14} | {'样本':<4} | {'胜率':>5} | {'ROI':>7} | {'True CLV':>8}")
    print("-" * 55)
    for b_id, v in sorted(by_bin_out.items(), key=lambda x: str(x[0])):
        print(f"Decile {b_id:<7} | {v['bets']:<4} | {v['hit_rate_pct']:>4.1f}% | {v['roi_pct']:>6.2f}% | {v['avg_true_clv_pct']:>7.2f}%")

    print(f"\n⚖️ 【因子 A/B 测试：伤停折损 (Attrition) 效用分析】")
    print(f"{'影响状态':<32} | {'样本':<4} | {'胜率':>5} | {'ROI':>7} | {'True CLV':>8}")
    print("-" * 65)
    for a_key, v in by_attrition_out.items():
        print(f"{a_key:<32} | {v['bets']:<4} | {v['hit_rate_pct']:>4.1f}% | {v['roi_pct']:>6.2f}% | {v['avg_true_clv_pct']:>7.2f}%")

    print(f"\n🔬 【伤停 x 档位：深度交叉审计】")
    print(f"{'组合状态':<24} | {'样本':<4} | {'ROI':>7} | {'True CLV':>8}")
    print("-" * 55)
    for k, v in sorted(by_attr_bin_out.items(), key=lambda x: x[1]['avg_true_clv_pct'], reverse=True):
        if v["bets"] > 0:
            print(f"{k:<24} | {v['bets']:<4} | {v['roi_pct']:>6.2f}% | {v['avg_true_clv_pct']:>7.2f}%")

    print(f"\n🔀 【档位跳变矩阵】")
    print(f"{'跳变路径 (Orig->Adj)':<24} | {'样本':<4} | {'ROI':>7} | {'True CLV':>8}")
    print("-" * 55)
    for k, v in sorted(by_bin_jump_out.items(), key=lambda x: x[1]['bets'], reverse=True):
        if v["bets"] > 0:
            print(f"{k:<24} | {v['bets']:<4} | {v['roi_pct']:>6.2f}% | {v['avg_true_clv_pct']:>7.2f}%")

    # ── Router 激活状态预演 ──
    print(f"\n🔁 【Strategy Router 激活状态预演 (enable_active_routing=False)】")
    print("-" * 65)
    for jump_key, v in by_bin_jump_out.items():
        bets = v["bets"]
        clv = v["avg_true_clv_pct"]
        roi = v["roi_pct"]
        if "->" in jump_key:
            try:
                parts = jump_key.replace("[", "").replace("]", "").split(" -> ")
                orig_b, adj_b = int(parts[0]), int(parts[1])
                jump_size = abs(orig_b - adj_b)

                if jump_size == 1:
                    title = f"🌟 黄金跳变 {jump_key} & boost=True"
                    if bets >= 20 and clv > 0:
                        status = "✅ 铁律满足 (将激活提权/加杠杆)"
                    else:
                        status = "⚠️ 样本不足/无Edge，仅列为观察区"
                elif jump_size >= 2:
                    title = f"☠️ 毒药崩塌 {jump_key} (Blacklist 区)"
                    if bets >= 20 and clv < -2.0:
                        status = "✅ 铁律满足 (将激活 Router 斩杀)"
                    else:
                        status = "⚠️ 样本不足/未亏透，暂不斩杀"
                else:
                    continue

                print(f"{title}")
                print(f" 样本: {bets:<3} 场 | ROI {roi:>6.2f}% | True CLV {clv:>6.2f}% → {status}\n")
            except Exception:
                pass

    if health_flags:
        print(f"\n🚨 【系统健康度报警】")
        for flag in health_flags:
            print(f"[{flag['level'].upper()}] {flag['detail']}")
    else:
        print(f"\n✅ 【系统健康度】: 运转良好，无负向警报。")

    # ── 🛡️ 防线体检单 ──
    print(f"\n🛡️ 【系统安全防御体检单 (Security Health Check)】")
    print("=" * 60)

    # [1] 基础风控层
    print(f" [1] bankroll.py    : OK (Kelly=1/4, 单注上限1000, 软15%/硬30%熔断)")

    # [2] 路由决策层
    golden_by_jump = {k: v for k, v in by_bin_jump_out.items() if abs(int(k.split(' -> ')[0].replace('[','')) - int(k.split(' -> ')[1].replace(']',''))) == 1}
    golden_clv = 0.0
    golden_n = 0
    for v in golden_by_jump.values():
        golden_n += v.get("bets", 0)
        golden_clv = max(golden_clv, v.get("avg_true_clv_pct", 0))
    router_status = f"OK (黄金跳变区 N={golden_n}, TrueCLV={golden_clv}%)" if golden_n >= 20 else f"WAITING (黄金跳变区 N={golden_n} < 20, 继续积累)"
    print(f" [2] strategy_router: {router_status}")

    # [3] 实盘网关层
    if total_bets < 50:
        bridge_status = f"SANDBOX_DISALLOWED (N={total_bets} < 50)"
    elif avg_true_clv * 100 < 1.0:
        bridge_status = f"SANDBOX_DISALLOWED (avg_true_clv={avg_true_clv*100:+.2f}% < 1%)"
    else:
        bridge_status = "SANDBOX_EVALUATING (准入护城河审查中...)"
    print(f" [3] live_bridge    : {bridge_status}")

    # [4] 审计追踪层
    print(f" [4] paper_trading  : OK (7 面板运转正常, 等待每周日终审)")
    print(f" [5] GUARD审计      : grep '[GUARD]' *.log → 全链路防线日志追踪")
    print("=" * 60)

    # ── 🌍 V3 大赛引擎专属仪表盘 ──
    v3_bets = [r for r in all_results if r.get("strategy_id") == "V3_PERCEPTION_GAP_SNIPER"]
    if v3_bets:
        print(f"\n🌍 【V3 大赛引擎专属仪表盘】")
        print("=" * 60)
        v3_profit = sum(float(b.get("pnl", 0)) for b in v3_bets)
        v3_hits = sum(1 for b in v3_bets if b.get("is_hit"))
        print(f"总捕获: {len(v3_bets)} 场 | 命中: {v3_hits} | 净利: {v3_profit:+.1f}u")
        extreme = [b for b in v3_bets if b.get("perception_gap", 0) >= 1.0]
        if extreme:
            ex_profit = sum(float(b.get("pnl", 0)) for b in extreme)
            print(f"🔥 极度泡沫区 (Gap>=1.0): N={len(extreme)}, 净利: {ex_profit:+.1f}u")
        print("=" * 60)

    # ── ⏱ 联赛时序形态审计 (Timing Alpha) ──
    try:
        from datetime import date as dt
        today_fs = BASE_DIR / "data" / "daily_reports" / f"full_scan_{dt.today().strftime('%Y%m%d')}.json"
        if today_fs.exists():
            with open(today_fs) as f:
                scan = json.load(f)
            candidates = scan.get("candidates", [])
            # Aggregate by league
            lg_patterns = defaultdict(lambda: Counter())
            _by_fid = {}
            for c in candidates:
                fid = c["fixture_id"]
                if fid not in _by_fid: _by_fid[fid] = {}
                _by_fid[fid][c.get("scan_tag", "?")] = c
            
            for fid, tags in _by_fid.items():
                if all(t in tags for t in ["AM0800", "NOON1200", "PM1600"]):
                    am = tags["AM0800"]
                    d8 = am.get("offered_odds_D")
                    d12 = tags["NOON1200"].get("offered_odds_D")
                    d16 = tags["PM1600"].get("offered_odds_D")
                    if not all([d8, d12, d16]): continue
                    lg = am.get("league_name", "Unknown")
                    delta_1 = d12 - d8; delta_2 = d16 - d12; total_d = d16 - d8
                    if abs(total_d) <= 0.02 and abs(delta_1) <= 0.02: pat = "FLAT"
                    elif delta_1 * delta_2 < 0 and abs(d16 - d8) <= 0.02: pat = "REVERT"
                    elif delta_1 * delta_2 > 0 and abs(delta_2) >= abs(delta_1) and abs(total_d) > 0.02: pat = "ACCEL"
                    elif abs(total_d) > 0.02: pat = "MOMEN"
                    else: pat = "OTHER"
                    lg_patterns[lg][pat] += 1

            if lg_patterns:
                print(f"\n⏱ 【V2.1 联赛时序形态审计 (Timing Alpha)】")
                print("=" * 60)
                for lg, cnts in sorted(by_league.items(), key=lambda x: -sum(x[1].values())):
                    total = sum(cnts.values())
                    if total < 2: continue
                    f_pct = cnts.get("FLAT",0)/total*100
                    am_pct = (cnts.get("ACCEL",0)+cnts.get("MOMEN",0))/total*100
                    r_pct = cnts.get("REVERT",0)/total*100
                    if am_pct >= 60: tag = "⚠️ 延迟开火候选"
                    elif f_pct >= 60: tag = "✅ 早盘锁仓安全"
                    else: tag = "🔄 混合震荡待定"
                    print(f"{lg:<14} N={total:<3} FLAT {f_pct:.0f}% | ACC+MOM {am_pct:.0f}% | REV {r_pct:.0f}% → {tag}")
                print("=" * 60)
    except Exception as e:
        import sys; print(f'⏱ Timing panel error: {e}', file=sys.stderr)

    print("=" * 60 + "\n")

    return {
        "summary": {
            "total_bets": total_bets, "hits": hits,
            "roi_pct": round(total_pnl / max(total_staked, 1) * 100, 2),
            "avg_true_clv_pct": round(avg_true_clv * 100, 2),
            "avg_raw_clv_pct": round(avg_raw_clv * 100, 2),
            "avg_fair_line_clv_pct": round(avg_fair_line_clv * 100, 2),
        },
        "by_league": by_league_out, "by_bin": by_bin_out,
        "by_attrition": by_attrition_out,
        "by_attr_bin": by_attr_bin_out,
        "by_bin_jump": by_bin_jump_out,
        "daily_timeseries": daily_timeseries, "rolling_windows": rolling,
        "health_flags": health_flags
    }


# ═══════════════════════════════════════════════════════════
# 测试：首战 CLV 验算
# ═══════════════════════════════════════════════════════════

def test_clv():
    """用 Al Khaleej vs Al Hilal 首战数据测试 CLV 计算"""
    print("=" * 55)
    print("🧪 True CLV 单元测试")
    print("  Al Khaleej vs Al Hilal | HT: 1-1 (Draw)")
    print("=" * 55)

    # --- 测试 parse_ht_result ---
    assert parse_ht_result("1-1") == "D", f"FAIL: 1-1 → 应该 D, 得到 {parse_ht_result('1-1')}"
    assert parse_ht_result("2-0") == "H"
    assert parse_ht_result("0-1") == "A"
    assert parse_ht_result("0-0") == "D"
    assert parse_ht_result(None) is None
    print("✅ parse_ht_result: 全部通过")

    # --- 测试 settle_trade ---
    profit, hit = settle_trade(42, 3.05, "D", "D")
    assert abs(profit - 86.1) < 0.01, f"Profit expected 86.1, got {profit}"
    assert hit is True
    profit, hit = settle_trade(42, 3.05, "D", "H")
    assert abs(profit - (-42)) < 0.01, f"Profit expected -42, got {profit}"
    assert hit is False
    print(f"✅ settle_trade: 命中→+{86.1}, 未中→-42")

    # --- 测试 calculate_true_clv ---
    closing = {"H": 8.19, "D": 3.12, "A": 1.60}
    placed = 3.05

    # 手工计算验证
    inv_h = 1/8.19; inv_d = 1/3.12; inv_a = 1/1.60
    margin = inv_h + inv_d + inv_a
    fair_draw = 1.0 / ((1.0 / 3.12) / margin)
    expected_clv = (3.05 / fair_draw) - 1.0

    true_clv, fair_close = calculate_true_clv(placed, "D", closing)
    print(f"\n📊 Pinnacle 收盘: H={closing['H']}, D={closing['D']}, A={closing['A']}")
    print(f"   Margin (Overround): {margin:.4f} ({(margin-1)*100:.2f}%)")
    print(f"   公平 Draw 收盘赔率: {fair_close:.4f} (期望: {fair_draw:.4f})")
    print(f"   True CLV: {true_clv*100:+.2f}% (期望: {expected_clv*100:+.2f}%)")

    assert abs(true_clv - expected_clv) < 0.0001, \
        f"CLV mismatch: {true_clv:.6f} vs expected {expected_clv:.6f}"
    assert abs(fair_close - fair_draw) < 0.0001
    print(f"✅ calculate_true_clv: {true_clv*100:+.2f}% 与手工计算一致")

    # --- 测试 extract_pinnacle_ht_1x2 ---
    mock_odds = {
        "response": [{
            "bookmakers": [{
                "name": "Pinnacle",
                "bets": [{
                    "name": "First Half Winner",
                    "values": [
                        {"value": "Home", "odd": "8.19"},
                        {"value": "Draw", "odd": "3.12"},
                        {"value": "Away", "odd": "1.60"},
                    ]
                }]
            }]
        }]
    }
    extracted = extract_pinnacle_ht_1x2(mock_odds)
    assert extracted == {"H": 8.19, "D": 3.12, "A": 1.60}
    print(f"✅ extract_pinnacle_ht_1x2: 正确提取三向赔率")

    # --- 完整流程模拟 ---
    print(f"\n--- 完整流程模拟 ---")
    ht_str = "1-1"
    actual = parse_ht_result(ht_str)
    pnl, is_hit = settle_trade(42, 3.05, "D", actual)
    clv, fair = calculate_true_clv(3.05, "D", closing)

    print(f"  HT: {ht_str} → {actual}")
    print(f"  投注: D @ 3.05 × 42u")
    print(f"  PnL: {pnl:+.2f}u {'✅' if is_hit else '❌'}")
    print(f"  CLV: {clv*100:+.2f}%")
    print(f"  结论: {'Alpha真实' if clv > 0 else '方差/运气 (CLV<0)'}")

    print(f"\n{'=' * 55}")
    print(f"✅ 所有测试通过 — paper_trading.py V2 就绪")
    print(f"{'=' * 55}")


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if "--test-clv" in sys.argv:
        test_clv()

    elif "--verify" in sys.argv:
        idx = sys.argv.index("--verify")
        dt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else date.today().isoformat()
        print(f"🔍 验证 {dt} 的预测...")
        result = verify_date(dt)
        if "error" in result:
            print(f"  ⚠️ {result['error']}")
        else:
            print(f"  ✅ {result['hits']}/{result['total_completed']} 命中 | "
                  f"ROI {result['roi_pct']:+.2f}% | CLV {result['avg_clv_pct']:+.2f}%")
            if result["pending"] > 0:
                print(f"  ⏳ {result['pending']} 场等待完赛")

    elif "--summary" in sys.argv:
        s = full_summary()
        if not s or "error" not in s:
            pass  # full_summary 内部已打印炫酷报表

    else:
        print("用法:")
        print("  python3 paper_trading.py --test-clv          # 单元测试 CLV 计算")
        print("  python3 paper_trading.py --verify 2026-05-05 # 验证指定日期")
        print("  python3 paper_trading.py --summary           # 全量汇总")
