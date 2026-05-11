"""
V4 球探扫描器 (纯情报模式 — 不与任何策略/交易耦合)
=====================================================
每天独立运行。只做一件事：产出足球比赛的多维战术画像。

前置漏斗: 白名单联赛 + 12h 内开赛。
输出: data/daily_reports/scout_v4_YYYYMMDD.json

用法:
  python3 engine/v4_runner.py
  python3 engine/v4_runner.py --run_tag=AM0800
"""

from __future__ import annotations

import argparse
import json, ssl, certifi, time, sys
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.secrets import API_KEY, API_HOST
from engine.data_sources.api_coverage import evaluate_fixture_coverage
from engine.data_sources.h2h_engine import evaluate_h2h_edge
from engine.data_sources.league_baseline import baseline_for_fixture
from engine.data_sources.lineup_strength import LineupStrengthAnalyzer
from engine.data_sources.motivation import evaluate_match_motivation
from engine.data_sources.schedule_pressure import evaluate_match_schedule_pressure
from engine.data_sources.season_phase import season_phase_for_fixture
from engine.v4_data_logger import append_jsonl, universe_path
from engine.context_enrichment import fetch_fixture_context
try:
    from logger import logger
except ModuleNotFoundError:
    from engine.logger import logger

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# SSL
ctx = ssl.create_default_context(cafile=certifi.where())

# 白名单
with open(BASE_DIR / "config" / "leagues_whitelist.json") as f:
    LEAGUE_CN = json.load(f)["leagueId"]

WL_SET = set(str(k) for k in LEAGUE_CN.keys())


def api_get(endpoint: str):
    url = f"{API_HOST}/{endpoint}"
    req = urllib.request.Request(url, headers={
        "x-apisports-key": API_KEY,
        "User-Agent": "V2-Football-Quant/1.0"
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception:
            if attempt < 2: time.sleep(0.5)
    return None


def fetch_today_fixtures(lookahead_hours: float | None = None):
    """拉取白名单联赛 + 今日/明日未开赛比赛。

    lookahead_hours 仅作为可选收窄条件；默认不再硬卡 12h。
    V4 走地策略需要先建全天观察池，再在 T-30 / 开赛后做二次闸门。
    """
    td = date.today()
    nd = td + timedelta(days=1)
    all_fixtures = []

    for day in [td.strftime("%Y-%m-%d"), nd.strftime("%Y-%m-%d")]:
        resp = api_get(f"fixtures?date={day}&timezone=Asia/Shanghai")
        if not resp: continue
        for f in resp.get("response", []):
            lg_id = str(f["league"]["id"])
            if lg_id not in WL_SET: continue
            status = f["fixture"]["status"]["short"]
            if status not in ("NS", "TBD"): continue
            kickoff = f["fixture"]["date"]
            try:
                ko_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            except:
                ko_dt = datetime.fromisoformat(kickoff.split("+")[0] + "+00:00")

            if lookahead_hours is not None:
                hours_to_kickoff = (ko_dt - datetime.now(ko_dt.tzinfo)).total_seconds() / 3600
                if hours_to_kickoff < 0 or hours_to_kickoff > lookahead_hours:
                    continue

            all_fixtures.append({
                "id": f["fixture"]["id"],
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "homeId": f["teams"]["home"]["id"],
                "awayId": f["teams"]["away"]["id"],
                "league": lg_id,
                "league_name": LEAGUE_CN.get(lg_id, f["league"]["name"]),
                "kickoff": kickoff,
            })
        time.sleep(0.5)

    seen = set()
    unique = []
    for fx in all_fixtures:
        if fx["id"] not in seen:
            seen.add(fx["id"])
            unique.append(fx)

    return unique


def _capture_ht_ou_lines(odds_resp: dict) -> list:
    """从 Pinnacle 半场大小球中捕获所有可用盘口线（含 0.75/1.25）。"""
    lines = []
    if not odds_resp or not odds_resp.get("response"):
        return lines
    for bo in odds_resp["response"][0].get("bookmakers", []):
        if "Pinnacle" not in bo.get("name", ""):
            continue
        for bet in bo.get("bets", []):
            name_lower = bet.get("name", "").lower()
            if ("over/under" not in name_lower and "over under" not in name_lower) or "first half" not in name_lower:
                continue
            # 按盘口线聚合 Over/Under 配对
            line_map = {}
            for v in bet.get("values", []):
                val_str = v.get("value", "")  # e.g. "Over 0.5" or "0.5"
                odd_val = float(v.get("odd", 0))
                # 提取纯数字线
                import re
                nums = re.findall(r'[\d.]+', val_str)
                line_num = nums[0] if nums else val_str
                entry = line_map.setdefault(line_num, {"over": None, "under": None})
                if "over" in val_str.lower():
                    entry["over"] = odd_val
                elif "under" in val_str.lower():
                    entry["under"] = odd_val
                else:
                    # 无标签：先填over再填under
                    if entry["over"] is None:
                        entry["over"] = odd_val
                    else:
                        entry["under"] = odd_val
            # 按盘口数排序输出
            for line_num in sorted(line_map.keys(), key=float):
                entry = line_map[line_num]
                lines.append({
                    "line": line_num,
                    "over": entry["over"],
                    "under": entry["under"],
                })
            return lines
    return lines


def _best_pre_live_line(ht_ou_lines: list) -> dict | None:
    """选择最适合走地观察的赛前半场大球线。"""
    valid = []
    for ln in ht_ou_lines:
        try:
            line = float(str(ln.get("line", "")).replace("Over ", "").replace("Under ", ""))
        except (TypeError, ValueError):
            continue
        valid.append({**ln, "line_float": line})
    if not valid:
        return None
    valid.sort(key=lambda x: x["line_float"], reverse=True)
    return valid[0]


def _query_injury_health(api_client, team_id: int, team_name: str) -> dict:
    """查询球队伤病/停赛情况（轻量版）"""
    try:
        resp = api_client(f"injuries?team={team_id}&season=2025")
        if not resp or "response" not in resp:
            return {"status": "unknown", "missing": []}
        injuries = resp["response"]
        missing = []
        for inj in injuries:
            player = inj.get("player", {})
            reason = inj.get("fixture", {}).get("reason", "")
            if not reason:
                continue
            missing.append({
                "name": player.get("name", "?"),
                "reason": reason,
            })
        return {
            "status": "healthy" if len(missing) == 0 else "injured",
            "missing_count": len(missing),
            "missing": missing[:5],  # 最多5人
        }
    except Exception:
        return {"status": "unknown", "missing": []}


def run_v4_scan(run_tag="V4_DEFAULT", with_lineups=False, lookahead_hours=None):
    logger.info(f"🔭 V4 球探扫描 | {run_tag} | {datetime.now().strftime('%H:%M')}")
    lineup_analyzer = LineupStrengthAnalyzer(api_get) if with_lineups else None

    fixtures = fetch_today_fixtures(lookahead_hours=lookahead_hours)
    today_key = date.today().strftime("%Y%m%d")
    universe_out = universe_path(today_key)
    window_label = f"{lookahead_hours:g}h内" if lookahead_hours is not None else "今日+明日全部"
    logger.info(f"📥 前置漏斗: {len(fixtures)} 场白名单 + {window_label}")

    if not fixtures:
        logger.info("无符合条件的比赛")
        return

    scout_reports = []
    live_watchlist = []
    stats = {"total": len(fixtures), "no_h2h": 0, "below_threshold": 0,
             "api_error": 0, "scouted": 0, "no_odds": 0}

    for i, fx in enumerate(fixtures):
        if (i + 1) % 20 == 0:
            logger.info(f"  H2H 查询: {i+1}/{len(fixtures)}")

        result = evaluate_h2h_edge(fx["homeId"], fx["awayId"], api_get)
        time.sleep(0.5)
        h2h_valid = bool(result.get("valid"))
        h2h_reason = result.get("reason", "")

        if not result["valid"]:
            append_jsonl(universe_out, {
                "fixture_id": fx["id"],
                "date": date.today().isoformat(),
                "league_id": fx["league"],
                "league_name": fx["league_name"],
                "country": None,
                "home_team": fx["home"],
                "away_team": fx["away"],
                "kickoff_time": fx["kickoff"],
                "prematch_ht_line": None,
                "prematch_over_odds": None,
                "prematch_under_odds": None,
                "api_coverage_level": "UNKNOWN",
                "is_candidate": False,
                "candidate_score": None,
                "filter_result": "SKIP",
                "filter_reason": f"H2H_{h2h_reason or 'INVALID'}",
                "run_tag": run_tag,
                "logged_at": datetime.now().isoformat(),
            })
            if "API_ERROR" in result.get("reason", ""):
                stats["api_error"] += 1
            elif "样本量" in result.get("reason", ""):
                stats["no_h2h"] += 1
            else:
                stats["below_threshold"] += 1
            continue

        # ── 庄家盘口阵地：捕获所有 HT OU 线 ──
        odds_resp = api_get(f"odds?fixture={fx['id']}")
        ht_ou_lines = _capture_ht_ou_lines(odds_resp) if odds_resp else []
        time.sleep(0.5)

        # ── API-Football 数据覆盖闸门 ──
        data_coverage = evaluate_fixture_coverage(
            fx,
            api_get,
            h2h_result=result,
            pre_odds_resp=odds_resp,
            ht_ou_lines=ht_ou_lines,
        )
        time.sleep(0.2)

        # ── 联赛 HT/SH/FT 环境基准 ──
        league_baseline = baseline_for_fixture(fx, api_get)
        league_adjustment = league_baseline.get("adjustment", {})
        time.sleep(0.2)

        # ── 赛季阶段：初期/中期/末期/最后三轮 ──
        season_phase = season_phase_for_fixture(fx, api_get)
        phase_adjustment = season_phase.get("adjustment", {})
        time.sleep(0.2)

        # ── 排名与战意过滤 ──
        motivation = evaluate_match_motivation(fx, api_get, season_phase=season_phase)
        motivation_gate = motivation.get("gate", {})
        time.sleep(0.2)

        # ── 未来三场赛程压力 ──
        schedule_pressure = evaluate_match_schedule_pressure(fx, api_get)
        time.sleep(0.2)

        # ── 伤病侦查 ──
        home_health = _query_injury_health(api_get, fx["homeId"], fx["home"])
        time.sleep(0.3)
        away_health = _query_injury_health(api_get, fx["awayId"], fx["away"])
        time.sleep(0.3)
        # ── P8 观测层：天气/场地/裁判（先记录，不入模） ──
        context_obs = fetch_fixture_context(fx["id"], api_get)
        time.sleep(0.2)

        # ── 提取因子 ──
        factors = result.get("factors", {})
        tb = factors.get("time_bins", {})
        sh_tb = factors.get("second_half_bins", {})
        combined_bins = {**tb, **sh_tb}
        best_bin = max(combined_bins, key=combined_bins.get) if combined_bins else "31_45"

        # ── 🎯 滚球雷达：探测高开比赛 (>=1.25 才是走地回调候选) ──
        best_line = _best_pre_live_line(ht_ou_lines)
        market_focus = result.get("market_focus")
        has_high_line = bool(
            market_focus == "HT_LIVE_OVER"
            and data_coverage.get("data_gate_action") == "ALLOW_V4_LIVE"
            and league_adjustment.get("action") != "WATCH_ONLY"
            and motivation_gate.get("action") != "WATCH_ONLY"
            and schedule_pressure.get("action") != "WATCH_CAUTION"
            and best_line
            and best_line["line_float"] >= 1.25
        )
        lineup_gate = None
        if has_high_line and lineup_analyzer:
            lineup_gate = lineup_analyzer.analyze_fixture(fx)
            time.sleep(0.5)

        if has_high_line:
            live_watchlist.append({
                "fixture_id": fx["id"],
                "date": date.today().isoformat(),
                "home": fx["home"],
                "away": fx["away"],
                "league": fx["league_name"],
                "market_focus": market_focus,
                "market_type": result.get("market_type", "HT_OU"),
                "market_scores": result.get("market_scores", {}),
                "best_focus_by_score": result.get("best_focus_by_score"),
                "best_score": result.get("best_score"),
                "pre_live_target": "WAIT_0_10_NO_GOAL_THEN_BUY_PULLBACK",
                "pre_ht_line": best_line,
                "ht_ou_lines": ht_ou_lines,
                "time_bin_hotspot": f"{best_bin}分钟",
                "factors": factors,
                "data_coverage": data_coverage,
                "league_baseline": league_baseline,
                "season_phase": season_phase,
                "motivation": motivation,
                "schedule_pressure": schedule_pressure,
                "lineup_gate": lineup_gate,
                "lineup_action": lineup_gate.get("lineup_action") if lineup_gate else "NOT_CHECKED",
            })

        append_jsonl(universe_out, {
            "fixture_id": fx["id"],
            "date": date.today().isoformat(),
            "league_id": fx["league"],
            "league_name": fx["league_name"],
            "country": None,
            "home_team": fx["home"],
            "away_team": fx["away"],
            "kickoff_time": fx["kickoff"],
            "prematch_ht_line": best_line["line_float"] if best_line else None,
            "prematch_over_odds": best_line.get("over") if best_line else None,
            "prematch_under_odds": best_line.get("under") if best_line else None,
            "api_coverage_level": data_coverage.get("coverage_level", "UNKNOWN"),
            "is_candidate": has_high_line,
            "candidate_score": result.get("best_score"),
            "filter_result": "PASS" if has_high_line else "SKIP",
            "filter_reason": (
                "PASS_LIVE_WATCHLIST"
                if has_high_line else
                f"NO_CANDIDATE|h2h_valid={h2h_valid}|data_gate={data_coverage.get('data_gate_action')}|"
                f"league={league_adjustment.get('action')}|motivation={motivation_gate.get('action')}|"
                f"schedule={schedule_pressure.get('action')}|best_line={best_line['line_float'] if best_line else 'NONE'}|"
                f"focus={market_focus}"
            ),
            "run_tag": run_tag,
            "logged_at": datetime.now().isoformat(),
        })

        # ── 球探快照（纯数据，零交易字段）──
        scout_reports.append({
            "fixture_id": fx["id"],
            "date": date.today().isoformat(),
            "kickoff": fx["kickoff"],
            "home": fx["home"],
            "away": fx["away"],
            "league": fx["league_name"],
            "market_focus": result.get("market_focus", "HT_LIVE_OVER"),
            "market_type": result.get("market_type", "HT_OU"),
            "market_scores": result.get("market_scores", {}),
            "best_focus_by_score": result.get("best_focus_by_score"),
            "best_score": result.get("best_score"),
            "factors": factors,
            "ht_ou_lines": ht_ou_lines,
            "data_coverage": data_coverage,
            "league_baseline": league_baseline,
            "season_phase": season_phase,
            "motivation": motivation,
            "schedule_pressure": schedule_pressure,
            "injury": {
                "home": home_health,
                "away": away_health,
            },
            "context_observation": context_obs,
            "lineup_gate": lineup_gate,
        })
        stats["scouted"] += 1

    # 保存
    today_str = date.today().strftime("%Y%m%d")
    out_path = REPORT_DIR / f"scout_v4_{today_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scout_reports, f, ensure_ascii=False, indent=2)

    logger.info(f"\n🔭 V4 球探扫描完成:")
    logger.info(f"  总数: {stats['total']} → H2H不足: {stats['no_h2h']} → 未达标: {stats['below_threshold']} → API错误: {stats['api_error']} → 无盘口: {stats.get('no_odds',0)} → 🔭球探报告: {stats['scouted']}")
    logger.info(f"  保存: {out_path} ({len(scout_reports)} 条)")
    logger.info(f"  🎯 滚球雷达: {len(live_watchlist)} 场")
    logger.info(f"  🧾 Universe日志: {universe_out}")

    if live_watchlist:
        live_path = REPORT_DIR / f"live_watchlist_{today_str}.json"
        with open(live_path, "w", encoding="utf-8") as f:
            json.dump(live_watchlist, f, ensure_ascii=False, indent=2)
        logger.info(f"  🎯 滚球雷达池: {live_path} ({len(live_watchlist)} 场)")

    try:
        from engine.v4_dashboard import render_dashboard
        dashboard_path = render_dashboard(today_str)
        logger.info(f"  🖥 交互仪表盘: {dashboard_path}")
    except Exception as e:
        logger.warning(f"  ⚠️ 仪表盘生成失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_tag", default="V4_DEFAULT")
    parser.add_argument(
        "--with-lineups",
        action="store_true",
        help="开赛前30分钟使用首发名单做 KEEP_WATCH/BOOST/DROP 阵容闸门",
    )
    parser.add_argument(
        "--lookahead-hours",
        type=float,
        default=None,
        help="可选：只扫描未来 N 小时比赛。默认不限制，扫描今天+明天所有白名单未开赛比赛",
    )
    args = parser.parse_args()
    run_v4_scan(
        run_tag=args.run_tag,
        with_lineups=args.with_lineups,
        lookahead_hours=args.lookahead_hours,
    )
