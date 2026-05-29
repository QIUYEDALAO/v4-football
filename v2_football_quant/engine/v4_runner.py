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
from urllib.parse import urlsplit, parse_qsl, urlencode
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.secrets import API_KEY, API_HOST
from engine.data_sources.api_coverage import evaluate_fixture_coverage
from engine.net_utils import _rpm_wait, api_get as _net_api_get, api_preflight, get_api_guard_snapshot
from engine.task_watchdog import v4_scan_watchdog
from engine.data_sources.h2h_engine import (
    evaluate_h2h_edge,
    warm_recent_goal_profiles,
    recent_profile_cache_stats,
    reset_recent_profile_cache_stats,
)
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
LEAGUE_TIER_REPORT = REPORT_DIR / "v4_league_replay_tiers.json"
CANDIDATE_RULES_PATH = BASE_DIR / "config" / "v4_candidate_rules.yaml"

# SSL
ctx = ssl.create_default_context(cafile=certifi.where())

# 绕过 macOS 系统代理 (127.0.0.1:10808)，API-Football 直连更快更稳
_no_proxy_handler = urllib.request.ProxyHandler({})
_no_proxy_opener = urllib.request.build_opener(_no_proxy_handler)
urllib.request.install_opener(_no_proxy_opener)

# 白名单
with open(BASE_DIR / "config" / "leagues_whitelist.json") as f:
    LEAGUE_CN = json.load(f)["leagueId"]

WL_SET = set(str(k) for k in LEAGUE_CN.keys())
SCAN_PROFILE_STABLE_FULL_24H = "stable_full_24h"
LOCAL_TZ = timezone(timedelta(hours=8))

# Match-date validation must use the match-local calendar date, not the
# operator/CST scan date. Country mapping is intentionally conservative; if a
# league is unmapped the row is marked timezone_unknown instead of being silently
# forced into the operator day.
COUNTRY_TZ = {
    "England": "Europe/London",
    "Belgium": "Europe/Brussels",
    "Netherlands": "Europe/Amsterdam",
    "Czech-Republic": "Europe/Prague",
    "Czech Republic": "Europe/Prague",
    "Ukraine": "Europe/Kyiv",
    "Sweden": "Europe/Stockholm",
    "Finland": "Europe/Helsinki",
    "USA": "America/New_York",
    "Brazil": "America/Sao_Paulo",
    "Uruguay": "America/Montevideo",
    "Iceland": "Atlantic/Reykjavik",
    "Indonesia": "Asia/Jakarta",
}
LEAGUE_TZ = {
    "英超": "Europe/London",
    "比甲": "Europe/Brussels",
    "荷甲": "Europe/Amsterdam",
    "捷克甲": "Europe/Prague",
    "乌克超": "Europe/Kyiv",
    "瑞典超": "Europe/Stockholm",
    "芬超": "Europe/Helsinki",
    "美职业": "America/New_York",
    "巴西甲": "America/Sao_Paulo",
    "乌拉甲": "America/Montevideo",
    "冰岛超": "Atlantic/Reykjavik",
    "印尼超": "Asia/Jakarta",
    "挪超": "Europe/Oslo",
    "立陶甲": "Europe/Vilnius",
    "西乙": "Europe/Madrid",
    "罗甲": "Europe/Bucharest",
    "意甲": "Europe/Rome",
}


def _resolve_match_timezone(country: str | None = None, league_name: str | None = None, fixture_timezone: str | None = None):
    for value, source in ((country, "country"), (league_name, "league_name")):
        if value:
            tz_name = COUNTRY_TZ.get(str(value)) or LEAGUE_TZ.get(str(value))
            if tz_name:
                return ZoneInfo(tz_name), source, False
    if fixture_timezone and fixture_timezone not in {"Asia/Shanghai", "Asia/Singapore"}:
        try:
            return ZoneInfo(str(fixture_timezone)), "fixture_timezone", False
        except Exception:
            pass
    return LOCAL_TZ, "operator_timezone_fallback", True


def _parse_kickoff_local(kickoff: str, *, country: str | None = None, league_name: str | None = None, fixture_timezone: str | None = None) -> tuple[datetime, bool, str]:
    """Return match-local kickoff time and whether timezone was unresolved."""
    raw = str(kickoff or "").strip()
    if not raw:
        raise ValueError("missing kickoff")
    normalized = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    parsed_tz_missing = dt.tzinfo is None
    if parsed_tz_missing:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    match_tz, source, unresolved = _resolve_match_timezone(country=country, league_name=league_name, fixture_timezone=fixture_timezone)
    return dt.astimezone(match_tz), bool(parsed_tz_missing or unresolved), source


def _scout_date_fields(kickoff: str, scan_dt: date, scout_file_date: str, source_window: str | None = None, *, country: str | None = None, league_name: str | None = None, fixture_timezone: str | None = None) -> dict:
    """Formal V4 scout date schema: date is match date, never scan date."""
    kickoff_local, timezone_unknown, timezone_source = _parse_kickoff_local(kickoff, country=country, league_name=league_name, fixture_timezone=fixture_timezone)
    match_date = kickoff_local.date().isoformat()
    fields = {
        "date": match_date,
        "match_date": match_date,
        "scan_date": scan_dt.isoformat(),
        "scout_file_date": scout_file_date,
        "kickoff_local": kickoff_local.isoformat(),
        "timezone_unknown": timezone_unknown,
        "timezone_source": timezone_source,
    }
    if source_window:
        fields["source_window"] = source_window
    return fields


def _load_candidate_rules() -> dict:
    if not CANDIDATE_RULES_PATH.exists():
        return {}
    with open(CANDIDATE_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_league_status_map() -> dict[str, dict]:
    if not LEAGUE_TIER_REPORT.exists():
        return {}
    try:
        with open(LEAGUE_TIER_REPORT, encoding="utf-8") as f:
            data = json.load(f)
        out = {}
        for row in data.get("leagues", []) if isinstance(data, dict) else []:
            code = str(row.get("league_code") or "")
            if code:
                out[code] = row
        return out
    except Exception:
        return {}


def api_get(endpoint: str):
    """API请求 → net_utils.api_get (urllib + curl兜底, 防IPv6卡死)"""
    return _net_api_get(endpoint, api_key=API_KEY, api_host=API_HOST, retries=3)


def _cached_api_client(base_client):
    cache: dict[str, dict | None] = {}
    stats = {"calls_total": 0, "cache_hits": 0, "cache_misses": 0}

    def _normalize_endpoint(endpoint: str) -> str:
        if "?" not in endpoint:
            return endpoint
        split = urlsplit(endpoint)
        q = parse_qsl(split.query, keep_blank_values=True)
        q_sorted = sorted(q, key=lambda x: (x[0], x[1]))
        normalized_q = urlencode(q_sorted, doseq=True)
        return f"{split.path}?{normalized_q}"

    def _get(endpoint: str):
        stats["calls_total"] += 1
        key = _normalize_endpoint(endpoint)
        if key in cache:
            stats["cache_hits"] += 1
            return cache[key]
        stats["cache_misses"] += 1
        resp = base_client(endpoint)
        cache[key] = resp
        return resp

    _get._stats = stats
    _get._cache = cache
    return _get


def fetch_today_fixtures(
    lookahead_hours: float | None = None,
    min_hours_to_kickoff: float | None = None,
    api_client=api_get,
    scan_base_date: date | None = None,
    include_outside_57: bool = False,
):
    """拉取白名单联赛 + 今日/明日未开赛比赛。

    北京时间业务日窗口: 当日 12:00 → 次日 12:00。
    lookahead_hours 仅作为额外收窄条件，不替代业务日窗口。
    """
    BJ_TZ = timezone(timedelta(hours=8))
    td = scan_base_date or date.today()
    nd = td + timedelta(days=1)
    td_str = td.strftime("%Y-%m-%d")
    nd_str = nd.strftime("%Y-%m-%d")
    all_fixtures = []

    for day in [td_str, nd_str]:
        resp = api_client(f"fixtures?date={day}&timezone=Asia/Shanghai")
        if not resp: continue
        for f in resp.get("response", []):
            lg_id = str(f["league"]["id"])
            if not include_outside_57 and lg_id not in WL_SET: continue
            status = f["fixture"]["status"]["short"]
            # Backfill mode (historical date) should keep all statuses.
            # Real-time mode:
            # - base day(td): keep not-finished matches so started fixtures stay visible on dashboard.
            # - next day(nd): keep pre-match only.
            if td >= date.today():
                is_base_day = (day == td_str)
                terminal_status = {"FT", "AET", "PEN", "CANC", "ABD", "AWD", "WO", "PST"}
                prematch_status = {"NS", "TBD"}
                if is_base_day:
                    if status in terminal_status:
                        continue
                else:
                    if status not in prematch_status:
                        continue

            kickoff = f["fixture"]["date"]
            try:
                ko_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            except:
                ko_dt = datetime.fromisoformat(kickoff.split("+")[0] + "+00:00")

            # Convert to Beijing time for business window check
            bj_dt = ko_dt.astimezone(BJ_TZ)
            bj_date_str = bj_dt.strftime("%Y-%m-%d")
            bj_hour = bj_dt.hour

            # Business window: today 12:00 BJ <= kickoff < next-day 12:00 BJ
            business_window_start_bj = f"{td_str} 12:00"
            business_window_end_bj = f"{nd_str} 12:00"
            kickoff_bj = bj_dt.strftime("%Y-%m-%d %H:%M")
            filtered_by_business_window = False

            if td >= date.today():
                in_window = False
                if bj_date_str == td_str and bj_hour >= 12:
                    in_window = True
                elif bj_date_str == nd_str and bj_hour < 12:
                    in_window = True

                if not in_window:
                    filtered_by_business_window = True
                    continue

                hours_to_kickoff = (ko_dt - datetime.now(ko_dt.tzinfo)).total_seconds() / 3600
                if min_hours_to_kickoff is not None and hours_to_kickoff < min_hours_to_kickoff:
                    continue
                if lookahead_hours is not None and (hours_to_kickoff < 0 or hours_to_kickoff > lookahead_hours):
                    continue

            all_fixtures.append({
                "id": f["fixture"]["id"],
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "homeId": f["teams"]["home"]["id"],
                "awayId": f["teams"]["away"]["id"],
                "league": lg_id,
                "league_name": LEAGUE_CN.get(lg_id, f["league"]["name"]),
                "country": f.get("league", {}).get("country"),
                "fixture_timezone": f.get("fixture", {}).get("timezone"),
                "kickoff": kickoff,
                # Business window trace fields
                "business_window_start_bj": business_window_start_bj,
                "business_window_end_bj": business_window_end_bj,
                "kickoff_bj": kickoff_bj,
                "filtered_by_business_window": filtered_by_business_window,
            })
        time.sleep(0.1)

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


def run_v4_scan(
    run_tag="V4_DEFAULT",
    with_lineups=False,
    lookahead_hours=None,
    min_hours_to_kickoff=None,
    scan_mode: str = "fast",
    recent_prewarm: str = "on",
    scan_date: str | None = None,
    use_watchdog: bool = True,
    generate_dashboard: bool = False,
):
    t0 = time.perf_counter()
    logger.info(f"🔭 V4 球探扫描 | {run_tag} | {datetime.now().strftime('%H:%M')}")

    if scan_date:
        scan_dt = datetime.strptime(scan_date.replace("-", ""), "%Y%m%d").date()
    else:
        scan_dt = date.today()
    today_key = scan_dt.strftime("%Y%m%d")

    preflight = api_preflight(today_key, api_key=API_KEY, api_host=API_HOST, strict=False, write_status=True)
    if not preflight.get("safe_to_scan"):
        blocked = {
            "schema_version": "v4_scan_api_blocked.v1",
            "date": today_key,
            "scan_status": "API_BLOCKED",
            "run_tag": run_tag,
            "generated_at": datetime.now().isoformat(),
            "preflight_required": True,
            "preflight_api_status": preflight.get("api_status"),
            "active_provider": preflight.get("active_provider"),
            "endpoint_host": preflight.get("endpoint_host"),
            "key_fingerprint": preflight.get("key_fingerprint"),
            "safe_to_scan": False,
            "remote_scan_started": False,
            "per_fixture_loop_started": False,
            "curl_fallback_on_403": False,
            "last_good_preserved": True,
            "dashboard_message": "API数据源异常，候选未刷新，保留 last_good。",
            "capture_ran": False,
            "QQ_push": False,
            "cloud_publish": False,
            "auto_retry": False,
            "auto_kill": False,
            "timeout_change": False,
            "api_guard": get_api_guard_snapshot(),
        }
        status_path = BASE_DIR / "data/runtime/status" / f"v4_scan_api_blocked_{today_key}.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(blocked, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.error("[GUARD] V4_SCAN_API_BLOCKED | preflight=%s | no remote scan", preflight.get("api_status"))
        return blocked

    api_client = _cached_api_client(api_get)
    lineup_analyzer = LineupStrengthAnalyzer(api_client) if with_lineups else None

    fixtures = fetch_today_fixtures(
        lookahead_hours=lookahead_hours,
        min_hours_to_kickoff=min_hours_to_kickoff,
        api_client=api_client,
        scan_base_date=scan_dt,
    )
    
    # ── 任务监控（仅独立运行时启用；wrapper模式下由调用方管理）──
    wd = None
    window = "midday" if "NOON" in run_tag else ("evening" if "PM" in run_tag else ("late" if "LATE" in run_tag else "manual"))
    if use_watchdog:
        wd = v4_scan_watchdog(window)
        if not wd.acquire_lock():
            logger.warning(f"[WATCHDOG] V4扫描-{window} 已有实例运行，跳过")
            return {"skipped": True, "reason": "concurrent_scan"}
        wd.start(total_items=len(fixtures))
    
    universe_out = universe_path(today_key)
    if universe_out.exists():
        universe_out.unlink()
    league_status_map = _load_league_status_map()
    window_label = f"{lookahead_hours:g}h内" if lookahead_hours is not None else "今日+明日全部"
    logger.info(f"📥 前置漏斗: {len(fixtures)} 场白名单 + {window_label}")

    if not fixtures:
        logger.info("无符合条件的比赛")
        return

    scout_reports = []
    live_watchlist = []
    stats = {"total": len(fixtures), "no_h2h": 0, "below_threshold": 0,
             "api_error": 0, "scouted": 0, "no_odds": 0, "valid_h2h_count": 0}

    # 预热 recent profile：按 team_id 去重，只拉一次，H2H 阶段直接复用缓存
    prewarm_info = {"enabled": False, "teams_total": 0, "warmed": 0, "skipped": 0, "cache_size": 0}
    if str(recent_prewarm).lower() == "on":
        prewarm_team_ids = []
        for fx in fixtures:
            if fx.get("homeId"):
                prewarm_team_ids.append(int(fx["homeId"]))
            if fx.get("awayId"):
                prewarm_team_ids.append(int(fx["awayId"]))
        prewarm_info = warm_recent_goal_profiles(
            api_client,
            prewarm_team_ids,
            last_n=10,
            include_events=False,
        )
        prewarm_info["enabled"] = True
        logger.info(
            f"  ♨️ recent预热: teams={prewarm_info['teams_total']} | warmed={prewarm_info['warmed']} | "
            f"skipped={prewarm_info['skipped']} | cache={prewarm_info['cache_size']}"
        )
    # 只统计“预热之后扫描阶段”的缓存命中率，避免被预热miss污染
    reset_recent_profile_cache_stats()

    rules = _load_candidate_rules()
    strict_rule = (rules or {}).get("A_strict_v3_pullback") or {}
    strict_min_cov = str(strict_rule.get("coverage_min", "BASIC")).upper()
    strict_focus = str(strict_rule.get("market_focus", "HT_LIVE_OVER"))
    strict_min_ht_score = float(strict_rule.get("min_ht_live_score", 55.0))
    strict_min_prematch_line = float(strict_rule.get("min_prematch_ht_line", 1.25))
    strict_pullback_fit = {str(x).upper() for x in (strict_rule.get("allowed_pullback_fit") or ["STRONG", "OK"])}
    strict_early_only_required = bool(strict_rule.get("early_only_required", False))
    strict_min_pressure = float(strict_rule.get("min_pressure_11_45", 0.5))

    cov_rank = {"UNKNOWN": 1, "BASIC": 2, "GOOD": 3, "FULL": 4}

    for i, fx in enumerate(fixtures):
        if (i + 1) % 10 == 0 and wd:
            wd.heartbeat(current=i+1, total=len(fixtures), item=f"{fx.get('home','?')} vs {fx.get('away','?')}", api_calls=getattr(api_client, "_stats", {}).get("calls_total",0))
        if (i + 1) % 20 == 0:
            logger.info(f"  H2H 查询: {i+1}/{len(fixtures)}")

        lg_policy = league_status_map.get(str(fx["league"]), {})
        lg_status = str(lg_policy.get("status") or "UNKNOWN")
        if lg_status == "DISABLED":
            append_jsonl(universe_out, {
                "fixture_id": fx["id"],
                **_scout_date_fields(fx["kickoff"], scan_dt, today_key, window, country=fx.get("country"), league_name=fx.get("league_name"), fixture_timezone=fx.get("fixture_timezone")),
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
                "filter_reason": "LEAGUE_DISABLED_BY_REPLAY_TIER",
                "league_replay_status": lg_status,
                "run_tag": run_tag,
                "logged_at": datetime.now().isoformat(),
            })
            continue

        logger.info(f"  ⏳ H2H: {fx.get('league_name','?')} | {fx['home']} vs {fx['away']}")
        import traceback, sys
        result = evaluate_h2h_edge(
            fx["homeId"],
            fx["awayId"],
            api_client,
            mode=scan_mode,
            current_league_id=fx["league"],
            current_league_name=fx["league_name"],
            current_country=fx.get("country"),
        )
        if not result.get("valid"):
            logger.info(f"  ⏭️ SKIP: {result.get('reason','?')}")
        h2h_valid = bool(result.get("valid"))
        h2h_reason = result.get("reason", "")

        if not result["valid"]:
            append_jsonl(universe_out, {
                "fixture_id": fx["id"],
                **_scout_date_fields(fx["kickoff"], scan_dt, today_key, window, country=fx.get("country"), league_name=fx.get("league_name"), fixture_timezone=fx.get("fixture_timezone")),
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
        stats["valid_h2h_count"] += 1

        # ── 庄家盘口阵地：捕获所有 HT OU 线 ──
        odds_resp = api_client(f"odds?fixture={fx['id']}")
        ht_ou_lines = _capture_ht_ou_lines(odds_resp) if odds_resp else []

        # fast模式：先做轻量前筛，避免每场都触发 5-6 个重模块
        factors = result.get("factors", {})
        market_focus = result.get("market_focus")
        best_line = _best_pre_live_line(ht_ou_lines)
        prelim_candidate = bool(market_focus == "HT_LIVE_OVER" and best_line and best_line["line_float"] >= 1.25)

        # 覆盖率评估始终执行（轻量+有缓存），避免 fast 模式出现“假 BASIC/WATCH_ONLY”。
        data_coverage = evaluate_fixture_coverage(
            fx,
            api_client,
            h2h_result=result,
            pre_odds_resp=odds_resp,
            ht_ou_lines=ht_ou_lines,
        )

        # ── 重模块：full模式全部跑；fast模式仅对预候选跑 ──
        run_heavy = (scan_mode == "full") or prelim_candidate
        if run_heavy:
            league_baseline = baseline_for_fixture(fx, api_client)
            season_phase = season_phase_for_fixture(fx, api_client)
            motivation = evaluate_match_motivation(fx, api_client, season_phase=season_phase)
            schedule_pressure = evaluate_match_schedule_pressure(fx, api_client)
            home_health = _query_injury_health(api_client, fx["homeId"], fx["home"])
            away_health = _query_injury_health(api_client, fx["awayId"], fx["away"])
            context_obs = fetch_fixture_context(fx["id"], api_client)
        else:
            league_baseline = {"adjustment": {"action": "KEEP"}}
            season_phase = {"adjustment": {"action": "KEEP"}}
            motivation = {"gate": {"action": "KEEP", "reason": "FAST_MODE_PRECHECK"}}
            schedule_pressure = {"action": "KEEP", "reason": "FAST_MODE_PRECHECK"}
            home_health = {"status": "unknown", "missing": []}
            away_health = {"status": "unknown", "missing": []}
            context_obs = {"weather": {"status": "SKIPPED_FAST_MODE"}, "pitch": {"status": "SKIPPED_FAST_MODE"}, "referee": {"status": "SKIPPED_FAST_MODE"}}
        league_adjustment = league_baseline.get("adjustment", {})
        motivation_gate = (motivation.get("gate") or {})

        # ── 提取因子 ──
        tb = factors.get("time_bins", {})
        sh_tb = factors.get("second_half_bins", {})
        combined_bins = {**tb, **sh_tb}
        best_bin = max(combined_bins, key=combined_bins.get) if combined_bins else "31_45"

        # ── 🎯 滚球雷达：探测高开比赛 (>=1.25 才是走地回调候选) ──
        ht_score = float((result.get("market_scores") or {}).get("HT_LIVE_OVER") or 0.0)
        pre_line_value = best_line["line_float"] if best_line else None
        pullback_fit = str((factors.get("pullback_fit") or "WEAK")).upper()
        early_only_flag = bool(factors.get("early_only_flag", False))
        pressure_11_45 = float((factors.get("time_bins") or {}).get("11_45") or 0.0)
        cov_level = str(data_coverage.get("coverage_level", "UNKNOWN")).upper()
        cov_pass = cov_rank.get(cov_level, 0) >= cov_rank.get(strict_min_cov, 0)

        has_high_line = bool(
            cov_pass
            and ht_score >= strict_min_ht_score
            and str(strict_focus) == "HT_LIVE_OVER"
            and pre_line_value is not None
            and pre_line_value >= strict_min_prematch_line
            and pullback_fit in strict_pullback_fit
            and early_only_flag == strict_early_only_required
            and pressure_11_45 >= strict_min_pressure
            and league_adjustment.get("action") != "WATCH_ONLY"
            and motivation_gate.get("action") != "WATCH_ONLY"
            and schedule_pressure.get("action") != "WATCH_CAUTION"
        )
        if lg_status == "WATCH_ONLY":
            has_high_line = False
        lineup_gate = None
        if has_high_line and lineup_analyzer:
            lineup_gate = lineup_analyzer.analyze_fixture(fx)

        if has_high_line:
            priority_boost = 0
            if lg_status == "AUTO_TRADE":
                priority_boost = 5
            elif lg_status == "PAPER_ONLY":
                priority_boost = 2
            live_watchlist.append({
                "fixture_id": fx["id"],
                **_scout_date_fields(fx["kickoff"], scan_dt, today_key, window, country=fx.get("country"), league_name=fx.get("league_name"), fixture_timezone=fx.get("fixture_timezone")),
                "home": fx["home"],
                "away": fx["away"],
                "league": fx["league_name"],
                "market_focus": "HT_LIVE_OVER",
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
                "league_replay_status": lg_status,
                "priority_boost": priority_boost,
                "strict_rule": "strict_v3_pullback",
                "strict_diagnostics": {
                    "ht_score": ht_score,
                    "pre_line": pre_line_value,
                    "pullback_fit": pullback_fit,
                    "early_only_flag": early_only_flag,
                    "pressure_11_45": pressure_11_45,
                    "coverage_level": cov_level,
                },
            })

        append_jsonl(universe_out, {
            "fixture_id": fx["id"],
            **_scout_date_fields(fx["kickoff"], scan_dt, today_key, window, country=fx.get("country"), league_name=fx.get("league_name"), fixture_timezone=fx.get("fixture_timezone")),
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
                f"focus={market_focus}|ht_score={ht_score}|pullback_fit={pullback_fit}|"
                f"early_only={early_only_flag}|pressure_11_45={pressure_11_45}"
            ),
            "league_replay_status": lg_status,
            "run_tag": run_tag,
            "logged_at": datetime.now().isoformat(),
        })

        # ── 球探快照（纯数据，零交易字段）──
        scout_reports.append({
            "fixture_id": fx["id"],
            **_scout_date_fields(fx["kickoff"], scan_dt, today_key, window, country=fx.get("country"), league_name=fx.get("league_name"), fixture_timezone=fx.get("fixture_timezone")),
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
    today_str = scan_dt.strftime("%Y%m%d")
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

    if generate_dashboard:
        try:
            from engine.v4_dashboard import render_dashboard
            dashboard_path = render_dashboard(today_str)
            logger.info(f"  🖥 交互仪表盘: {dashboard_path}")
        except Exception as e:
            logger.warning(f"  ⚠️ 仪表盘生成失败: {e}")
    else:
        logger.info("  🖥 dashboard skipped by generate_dashboard=False")

    elapsed = round(time.perf_counter() - t0, 2)
    api_stats = getattr(api_client, "_stats", {})
    perf = {
        "date": scan_dt.isoformat(),
        "scan_date": scan_dt.isoformat(),
        "scout_file_date": today_key,
        "run_tag": run_tag,
        "scan_mode": scan_mode,
        "scan_profile": SCAN_PROFILE_STABLE_FULL_24H,
        "lookahead_hours": lookahead_hours,
        "elapsed_seconds": elapsed,
        "total_fixtures": stats["total"],
        "valid_h2h_count": stats["valid_h2h_count"],
        "scouted_count": stats["scouted"],
        "watchlist_count": len(live_watchlist),
        "api_calls_total": api_stats.get("calls_total", 0),
        "api_cache_hits": api_stats.get("cache_hits", 0),
        "api_cache_misses": api_stats.get("cache_misses", 0),
        "api_guard": get_api_guard_snapshot(),
        "api_calls_attempted": get_api_guard_snapshot().get("api_calls_attempted", 0),
        "api_calls_blocked_by_preflight": get_api_guard_snapshot().get("api_calls_blocked_by_preflight", 0),
        "api_calls_blocked_by_circuit_breaker": get_api_guard_snapshot().get("api_calls_blocked_by_circuit_breaker", 0),
        "remote_requests": get_api_guard_snapshot().get("remote_requests", 0),
        "forbidden_count": get_api_guard_snapshot().get("forbidden_count", 0),
        "fallback_count": get_api_guard_snapshot().get("fallback_count", 0),
        "recent_prewarm": prewarm_info,
        "recent_profile_cache": recent_profile_cache_stats(),
        "generated_at": datetime.now().isoformat(),
    }
    perf_path = REPORT_DIR / f"scan_perf_v4_{today_str}.json"
    with open(perf_path, "w", encoding="utf-8") as f:
        json.dump(perf, f, ensure_ascii=False, indent=2)
    logger.info(
        f"  ⚙️ 性能摘要: fixtures={perf['total_fixtures']} | valid_h2h={perf['valid_h2h_count']} | "
        f"api_calls={perf['api_calls_total']} | cache_hit={perf['api_cache_hits']} | {elapsed}s"
    )
    logger.info(f"  ⚙️ 性能文件: {perf_path}")
    
    # ── 任务监控：完成 ──
    if wd:
        scout_ok = out_path.exists() and out_path.stat().st_size > 0
        wd.finish(
            status="DONE" if scout_ok else "PARTIAL_DONE",
            output_files={"scout": str(out_path), "perf": str(perf_path)},
            error="" if scout_ok else "scout文件为空或不存在",
        )


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
    parser.add_argument(
        "--scan-mode",
        choices=["fast", "full"],
        default="fast",
        help="fast: 先轻筛再跑重模块（推荐）；full: 每场全量引擎",
    )
    parser.add_argument(
        "--recent-prewarm",
        choices=["on", "off"],
        default="off",
        help="recent画像是否在扫描前预热（40场规模默认off更快）",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="可选：扫描基准日期 YYYYMMDD（用于回填universe文件）",
    )
    args = parser.parse_args()
    run_v4_scan(
        run_tag=args.run_tag,
        with_lineups=args.with_lineups,
        lookahead_hours=args.lookahead_hours,
        scan_mode=args.scan_mode,
        recent_prewarm=args.recent_prewarm,
        scan_date=args.date,
    )
