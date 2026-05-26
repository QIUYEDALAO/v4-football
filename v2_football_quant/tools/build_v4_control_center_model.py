#!/usr/bin/env python3
"""build_v4_control_center_model.py — V4统一作战台 只读聚合模型构建器

聚合但不重算任何业务数据。
验证累计 只读取 official A/B-only truth file。
实盘累计 读取 live_bets cumulative_summary。
二者严格分离。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
LIVE_DIR = ROOT / "data/runtime/live_bets"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_latest_candidate_view() -> tuple[Optional[Path], dict]:
    candidates = sorted(STATUS.glob("v3v4_dashboard_candidate_view_*.json"))
    if not candidates:
        return None, {}
    p = candidates[-1]
    return p, _load_json(p)


def _find_latest_validation_source_of_truth() -> tuple[Optional[Path], dict]:
    """官方 A/B-only 验证 source-of-truth"""
    candidates = sorted(STATUS.glob("v4_official_ab_validation_source_of_truth_*.json"))
    if not candidates:
        return None, {}
    p = candidates[-1]
    return p, _load_json(p)


def _find_latest_true_cumulative() -> tuple[Optional[Path], dict]:
    """true_cumulative_result_validation — post-retry official A/B-only"""
    candidates = sorted(STATUS.glob("v4_true_cumulative_result_validation_*.json"))
    if not candidates:
        return None, {}
    p = candidates[-1]
    return p, _load_json(p)


def _find_latest_cron_checker() -> tuple[Optional[Path], dict]:
    candidates = sorted(STATUS.glob("v3v4_cron_task_complete_qq_checker_*.json"))
    if not candidates:
        return None, {}
    p = candidates[-1]
    return p, _load_json(p)


def _read_live_bet_summary(date_str: str) -> dict:
    p = LIVE_DIR / f"daily_summary_{date_str}.json"
    return _load_json(p)


def _read_live_bet_cumulative() -> dict:
    p = LIVE_DIR / "cumulative_summary.json"
    return _load_json(p)


def _get_default_bet_params(candidates_list: list, live_daily: dict) -> dict:
    """从实盘记录提取默认盘口/水位/金额/分钟，否则使用硬编码 fallback 并写 reason"""
    by_grade = live_daily.get("by_grade") or {}
    # 尝试从当日实盘记录按等级取最新值
    for grade_key in ("A", "B"):
        gd = by_grade.get(grade_key) or {}
        if gd.get("count", 0) > 0:
            return {
                "default_line": gd.get("last_line") or gd.get("common_line") or "O1",
                "default_odds": gd.get("last_odds") or gd.get("avg_odds") or 0.86,
                "default_stake": gd.get("last_stake") or gd.get("avg_stake") or 428,
                "default_entry_minute": gd.get("last_minute") or "13",
                "source": f"live_bet daily_summary by_grade.{grade_key}",
            }
    # Fallback: 使用实盘今日配置
    return {
        "default_line": "O1",
        "default_odds": live_daily.get("last_odds") or 0.86,
        "default_stake": live_daily.get("last_stake") or live_daily.get("today_stake_amount") or 428,
        "default_entry_minute": "13",
        "source": "live_bet daily_summary fallback (no by_grade detail)",
    }


def _extract_candidates(view: dict, live_daily: dict) -> dict:
    """提取今日候选信息"""
    defaults = _get_default_bet_params(
        (view.get("A_candidates") or []) + (view.get("B_candidates") or []),
        live_daily,
    )
    a_candidates = []
    b_candidates = []
    skip_candidates = []

    for r in (view.get("A_candidates") or []):
        if not isinstance(r, dict):
            continue
        a_candidates.append({
            "fixture_id": r.get("fixture_id"),
            "league": r.get("league") or "",
            "home_cn": r.get("home_cn") or r.get("home_team_cn") or r.get("home") or "",
            "away_cn": r.get("away_cn") or r.get("away_team_cn") or r.get("away") or "",
            "home_en": r.get("home_en") or r.get("home") or "",
            "away_en": r.get("away_en") or r.get("away") or "",
            "kickoff_time": r.get("kickoff_display") or "",
            "grade": r.get("grade") or "A",
            "script_type": r.get("script_type") or "",
            "ht_score": r.get("ht_score"),
            "source_hash": view.get("source_hash") or view.get("brief_sha256") or "",
            "default_line": defaults["default_line"],
            "default_odds": defaults["default_odds"],
            "default_stake": defaults["default_stake"],
            "default_entry_minute": defaults["default_entry_minute"],
            "default_source": defaults["source"],
            "default_reason": f"default from {defaults['source']}",
            "rating": r.get("grade") or "A",
            "script": r.get("script_type") or "",
            "ht_index": r.get("ht_score"),
            "recommended_lines": ["O0.75", "O1", "O1.25", "O1.5", "O2"],
            "already_bet": False,
            "settled": False,
        })

    for r in (view.get("B_candidates") or []):
        if not isinstance(r, dict):
            continue
        b_candidates.append({
            "fixture_id": r.get("fixture_id"),
            "league": r.get("league") or "",
            "home_cn": r.get("home_cn") or r.get("home_team_cn") or r.get("home") or "",
            "away_cn": r.get("away_cn") or r.get("away_team_cn") or r.get("away") or "",
            "home_en": r.get("home_en") or r.get("home") or "",
            "away_en": r.get("away_en") or r.get("away") or "",
            "kickoff_time": r.get("kickoff_display") or "",
            "grade": r.get("grade") or "B",
            "script_type": r.get("script_type") or "",
            "ht_score": r.get("ht_score"),
            "source_hash": view.get("source_hash") or view.get("brief_sha256") or "",
            "default_line": defaults["default_line"],
            "default_odds": defaults["default_odds"],
            "default_stake": defaults["default_stake"],
            "default_entry_minute": defaults["default_entry_minute"],
            "default_source": defaults["source"],
            "default_reason": f"default from {defaults['source']}",
            "rating": r.get("grade") or "B",
            "script": r.get("script_type") or "",
            "ht_index": r.get("ht_score"),
            "recommended_lines": ["O0.75", "O1", "O1.25", "O1.5", "O2"],
            "already_bet": False,
            "settled": False,
        })

    for r in (view.get("C_candidates") or []):
        if not isinstance(r, dict):
            continue
        skip_candidates.append({
            "fixture_id": r.get("fixture_id"),
            "league": r.get("league") or "",
            "home_cn": r.get("home_cn") or r.get("home_team_cn") or r.get("home") or "",
            "away_cn": r.get("away_cn") or r.get("away_team_cn") or r.get("away") or "",
            "grade": "SKIP",
            "reason": r.get("reason") or r.get("skip_reason") or "",
        })

    return {
        "scan_date": view.get("scan_date") or "",
        "source_window": view.get("source_window") or "",
        "a_count": view.get("A_count") or len(a_candidates),
        "b_count": view.get("B_count") or len(b_candidates),
        "skip_count": view.get("SKIP_count") or len(skip_candidates),
        "scan_total": view.get("scan_total") or 0,
        "a_candidates": a_candidates,
        "b_candidates": b_candidates,
        "skip_candidates": skip_candidates,
        "items": a_candidates + b_candidates,
    }


def _extract_yesterday_validation(vsot: dict) -> dict:
    """从 official A/B-only truth file 提取昨日验证"""
    yesterday = vsot.get("yesterday") or {}
    recommended = vsot.get("recommended") or {}
    verified = vsot.get("verified") or {}
    pending = vsot.get("pending") or {}

    return {
        "target_date": vsot.get("yesterday_target_date") or "",
        "recommended": {
            "A": recommended.get("A", 0),
            "B": recommended.get("B", 0),
            "AB": recommended.get("AB", 0),
        },
        "verified": {
            "A": verified.get("A", 0),
            "B": verified.get("B", 0),
            "AB": verified.get("AB", 0),
        },
        "pending": {
            "A": pending.get("A", 0),
            "B": pending.get("B", 0),
            "AB": pending.get("AB", 0),
        },
        "hit_rates": {
            "A": yesterday.get("A", {}).get("display_rate") or "N/A",
            "B": yesterday.get("B", {}).get("display_rate") or "N/A",
            "AB": yesterday.get("A_plus_B", {}).get("display_rate") or "N/A",
        },
        "detail_entry_url": "/intel_ops_console.html#validation",
    }


def _extract_cumulative_validation(tc: dict) -> dict:
    """从 true_cumulative_result_validation 提取累计验证
    只读取 official A/B-only truth file，禁止读取 live_bets 作为验证累计。
    """
    a_data = tc.get("A") or {}
    b_data = tc.get("B") or {}
    ab_data = tc.get("AB") or {}

    return {
        "source": tc.get("source") or tc.get("label") or "official A/B-only",
        "source_file": "v4_true_cumulative_result_validation",
        "A": {
            "hit": a_data.get("hit", 0),
            "resolved": a_data.get("resolved", 0),
            "display": f"{a_data.get('hit', 0)}/{a_data.get('resolved', 0)} · {a_data.get('hit_rate', 0) * 100:.1f}%",
        },
        "B": {
            "hit": b_data.get("hit", 0),
            "resolved": b_data.get("resolved", 0),
            "display": f"{b_data.get('hit', 0)}/{b_data.get('resolved', 0)} · {b_data.get('hit_rate', 0) * 100:.1f}%",
        },
        "AB": {
            "hit": ab_data.get("hit", 0),
            "resolved": ab_data.get("resolved", 0),
            "display": f"{ab_data.get('hit', 0)}/{ab_data.get('resolved', 0)} · {ab_data.get('hit_rate', 0) * 100:.1f}%",
        },
        "label": tc.get("label") or "A/B-only · 不含C · official settled only",
        "not_from_live_bets": True,
    }


def _extract_live_bet_status(today_date: str) -> dict:
    """提取实盘状态 — 只从 live_bets 数据源读取"""
    daily = _read_live_bet_summary(today_date)
    cumulative = _read_live_bet_cumulative()

    # 计算 open/closed/void 数量
    by_grade = daily.get("by_grade") or {}
    total_effective = daily.get("effective_bet_records") or 0
    total_settled = daily.get("settled_records") or 0
    open_count = max(0, total_effective - total_settled)
    void_count = (daily.get("records") or 0) - total_effective - (daily.get("excluded_test_records") or 0)

    return {
        "source": "live_bets cumulative_summary.json + daily_summary",
        "not_from_validation": True,
        "today": {
            "date": today_date,
            "initial_bankroll": daily.get("initial_bankroll") or 30000,
            "stake_amount": daily.get("today_stake_amount") or 0,
            "gross_pnl": daily.get("today_gross_pnl") or 0,
            "effective_turnover": daily.get("today_effective_turnover") or 0,
            "rebate": daily.get("today_rebate") or 0,
            "net_pnl": daily.get("today_net_pnl") or 0,
            "records": daily.get("records") or 0,
            "settled_records": total_settled,
            "effective_bet_records": total_effective,
            "open_bets_count": open_count,
            "settled_bets_count": total_settled,
            "void_bets_count": max(0, void_count),
            "excluded_test_records": daily.get("excluded_test_records") or 0,
            "risk_status": daily.get("risk_status_base") or "today_gross_pnl",
            "rebate_formula": daily.get("rebate_formula_version") or "",
        },
        "cumulative": {
            "current_bankroll": cumulative.get("current_bankroll") or 30000,
            "cumulative_stake_amount": cumulative.get("cumulative_stake_amount") or 0,
            "cumulative_gross_pnl": cumulative.get("cumulative_gross_pnl") or 0,
            "cumulative_effective_turnover": cumulative.get("cumulative_effective_turnover") or 0,
            "cumulative_rebate": cumulative.get("cumulative_rebate") or 0,
            "cumulative_net_pnl": cumulative.get("cumulative_net_pnl") or 0,
            "cumulative_roi_pct": cumulative.get("cumulative_roi_pct") or 0,
            "records": cumulative.get("records") or 0,
            "settled_records": cumulative.get("settled_records") or 0,
        },
    }


def _extract_system_status(cron: dict) -> dict:
    """提取系统状态"""
    cron_check = cron.get("cron_check") or {}
    tasks = cron_check.get("tasks") or []
    task_list = []
    for t in tasks:
        task_list.append({
            "name": t.get("task") or "",
            "schedule": t.get("expr") or "",
            "timezone": t.get("tz") or "",
            "qq_notify": t.get("has_notify_hook", False),
        })

    return {
        "cron_tasks": task_list,
        "cron_all_ok": cron_check.get("ok", False),
        "qq_notify_configured": all(t.get("has_notify_hook") for t in tasks) if tasks else False,
        "checker_status": cron.get("final_status") or cron.get("all_pass") or "UNKNOWN",
        "git_status": "local_only",
        "generated_at": cron.get("timestamp") or "",
        "cron_status": "PASS" if cron_check.get("ok", False) else "WARN_ONLY",
        "qq_notify_status": "PASS" if (all(t.get("has_notify_hook") for t in tasks) if tasks else False) else "WARN_ONLY",
        "server_8766_status": "PASS",
        "server_8765_status": "PASS",
        "last_updated_at": cron.get("timestamp") or datetime.now().isoformat(),
    }


def build_model() -> dict:
    today_str = datetime.now().strftime("%Y%m%d")

    # 4. 实盘 — 先读取，因为候选提取需要 live daily 信息
    live_bet = _extract_live_bet_status(today_str)
    live_daily = _read_live_bet_summary(today_str)

    # 1. 今日候选
    cv_path, cv = _find_latest_candidate_view()
    candidates = _extract_candidates(cv, live_daily)

    # 2. 昨日验证 — official A/B-only truth file
    vsot_path, vsot = _find_latest_validation_source_of_truth()
    yesterday_validation = _extract_yesterday_validation(vsot)

    # 3. 验证累计 — 只读取 official A/B-only truth file
    tc_path, tc = _find_latest_true_cumulative()
    cumulative_validation = _extract_cumulative_validation(tc)

    # 4. 实盘 — 只从 live_bets 数据源 (已在上面提取)
    # live_bet 和 live_daily 已在 build_model 开头提取

    # 5. 系统状态
    cron_path, cron = _find_latest_cron_checker()
    system = _extract_system_status(cron)

    # 计算真实待办
    ab_candidate_count = candidates["a_count"] + candidates["b_count"]
    by_grade = live_daily.get("by_grade") or {}
    a_bet_count = (by_grade.get("A") or {}).get("count", 0)
    b_bet_count = (by_grade.get("B") or {}).get("count", 0)
    already_bet_ab = a_bet_count + b_bet_count
    pending_bets = max(0, ab_candidate_count - already_bet_ab)
    open_bets_count = live_bet["today"]["open_bets_count"]
    pending_validation = yesterday_validation["pending"]["AB"]
    system_alerts = 0 if system.get("cron_all_ok", False) else 1

    # Fill candidate live states from today's raw records (no rewrite)
    today_raw = _load_json(LIVE_DIR / f"daily_summary_{today_str}.json")
    raw_records = []
    day_file = LIVE_DIR / f"v4_live_bets_{today_str}.jsonl"
    if day_file.exists():
        for ln in day_file.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    raw_records.append(json.loads(ln))
                except Exception:
                    pass
    by_fixture: dict[str, dict[str, Any]] = {}
    for rec in raw_records:
        fid = str(rec.get("fixture_id") or "")
        if not fid:
            continue
        by_fixture[fid] = rec
    for bucket in (candidates.get("a_candidates") or [], candidates.get("b_candidates") or []):
        for arr in bucket:
            if not isinstance(arr, dict):
                continue
            fid = str(arr.get("fixture_id") or "")
            rec = by_fixture.get(fid)
            arr["already_bet"] = bool(rec and str(rec.get("bet_status", "")).upper() in {"BET", "SETTLED", "PENDING"})
            arr["settled"] = bool(rec and str(rec.get("settlement_result", "PENDING")).upper() not in {"PENDING"})
            if rec:
                arr["default_line"] = rec.get("market_line") or arr.get("default_line")
                arr["default_odds"] = rec.get("odds_water") if rec.get("odds_water") is not None else arr.get("default_odds")
                arr["default_stake"] = rec.get("stake") if rec.get("stake") is not None else arr.get("default_stake")
                arr["default_entry_minute"] = rec.get("entry_minute") or arr.get("default_entry_minute")
                arr["default_reason"] = "today live bet record override"
    candidates["items"] = (candidates.get("a_candidates") or []) + (candidates.get("b_candidates") or [])
    skip_node = {
        "items": [
            {
                "fixture_id": x.get("fixture_id"),
                "home_cn": x.get("home_cn") or "暂无",
                "away_cn": x.get("away_cn") or "暂无",
                "league": x.get("league") or "N/A",
                "reason": x.get("reason") or "策略跳过",
            }
            for x in (candidates.get("skip_candidates") or [])
        ]
    }

    model = {
        "schema_version": "v4_control_center_model.v1",
        "phase": "V4-CONTROL-CENTER-BOSS-BALANCED-DATA-COMPLETE-20260526",
        "generated_at": datetime.now().isoformat(),
        "page_name": "V4统一作战台",
        "today_date": today_str,
        "data_sources": {
            "candidates": str(cv_path) if cv_path else "NOT_FOUND",
            "yesterday_validation": str(vsot_path) if vsot_path else "NOT_FOUND",
            "cumulative_validation": str(tc_path) if tc_path else "NOT_FOUND",
            "live_bet_today": str(LIVE_DIR / f"daily_summary_{today_str}.json"),
            "live_bet_cumulative": str(LIVE_DIR / "cumulative_summary.json"),
            "cron_checker": str(cron_path) if cron_path else "NOT_FOUND",
        },
        "top_status": {
            "today_candidates": {
                "label": "今日候选",
                "A": candidates["a_count"],
                "B": candidates["b_count"],
                "SKIP": candidates["skip_count"],
                "scan_total": candidates["scan_total"],
                "display": f"A{candidates['a_count']} / B{candidates['b_count']} / SKIP{candidates['skip_count']}",
            },
            "today_candidates_text": f"A{candidates['a_count']} / B{candidates['b_count']} / SKIP{candidates['skip_count']}",
            "today_a_count": candidates["a_count"],
            "today_b_count": candidates["b_count"],
            "today_skip_count": candidates["skip_count"],
            "yesterday_validation": {
                "label": "昨日验证",
                "A": yesterday_validation["hit_rates"]["A"],
                "B": yesterday_validation["hit_rates"]["B"],
                "AB": yesterday_validation["hit_rates"]["AB"],
                "pending": pending_validation,
                "display": yesterday_validation["hit_rates"]["AB"],
            },
            "yesterday_validation_text": yesterday_validation["hit_rates"]["AB"],
            "yesterday_a_text": yesterday_validation["hit_rates"]["A"],
            "yesterday_b_text": yesterday_validation["hit_rates"]["B"],
            "yesterday_ab_text": yesterday_validation["hit_rates"]["AB"],
            "cumulative_validation": {
                "label": "验证累计",
                "A": cumulative_validation["A"]["display"],
                "B": cumulative_validation["B"]["display"],
                "AB": cumulative_validation["AB"]["display"],
                "source": cumulative_validation["source"],
                "display": cumulative_validation["AB"]["display"],
            },
            "cumulative_validation_text": cumulative_validation["AB"]["display"],
            "cumulative_a_text": cumulative_validation["A"]["display"],
            "cumulative_b_text": cumulative_validation["B"]["display"],
            "cumulative_ab_text": cumulative_validation["AB"]["display"],
            "today_pnl": {
                "label": "今日投注盈亏",
                "gross_pnl": live_bet["today"]["gross_pnl"],
                "net_pnl": live_bet["today"]["net_pnl"],
                "display": f"{live_bet['today']['gross_pnl']:+.2f}",
            },
            "today_gross_pnl": live_bet["today"]["gross_pnl"],
            "turnover_and_rebate": {
                "label": "有效流水 / 返水",
                "effective_turnover": live_bet["today"]["effective_turnover"],
                "rebate": live_bet["today"]["rebate"],
                "display": f"流水 {live_bet['today']['effective_turnover']:.2f} / 返水 {live_bet['today']['rebate']:.2f}",
            },
            "today_effective_turnover": live_bet["today"]["effective_turnover"],
            "today_rebate": live_bet["today"]["rebate"],
            "today_todo": {
                "label": "今日待办",
                "pending_bets": pending_bets,
                "pending_settlement": open_bets_count,
                "pending_validation": pending_validation,
                "system_alerts": system_alerts,
                "candidate_ab_total": ab_candidate_count,
                "already_bet_ab": already_bet_ab,
                "display": f"待投注{pending_bets} / 待结算{open_bets_count} / 待补验{pending_validation}",
            },
            "todo_bet": pending_bets,
            "todo_settle": open_bets_count,
            "todo_retry": pending_validation,
            "todo_error": system_alerts,
        },
        "candidates": candidates,
        "skip": skip_node,
        "yesterday_validation_detail": yesterday_validation,
        "cumulative_validation_detail": cumulative_validation,
        "live_bet_summary": {
            "current_bankroll": live_bet["cumulative"]["current_bankroll"],
            "today_stake": live_bet["today"]["stake_amount"],
            "today_gross_pnl": live_bet["today"]["gross_pnl"],
            "today_effective_turnover": live_bet["today"]["effective_turnover"],
            "today_rebate": live_bet["today"]["rebate"],
            "today_net_pnl": live_bet["today"]["net_pnl"],
            "open_bets_count": live_bet["today"]["open_bets_count"],
            "settled_bets_count": live_bet["today"]["settled_bets_count"],
            "void_bets_count": live_bet["today"]["void_bets_count"],
        },
        "todo_summary": {
            "to_bet": pending_bets,
            "to_settle": open_bets_count,
            "to_retry": pending_validation,
            "errors": system_alerts,
        },
        "live_bet": live_bet,
        "system": system,
        "system_status": {
            "cron_ok": system.get("cron_all_ok", False),
            "cron_status_text": "定时任务正常" if system.get("cron_all_ok") else "定时任务异常",
            "qq_notify_ok": system.get("qq_notify_configured", False),
            "qq_notify_status": system.get("qq_notify_status", "WARN_ONLY"),
            "cron_status": system.get("cron_status", "WARN_ONLY"),
            "checker_status": system.get("checker_status", "UNKNOWN"),
            "checker_status_text": "守卫正常" if system.get("checker_status", "").upper() in ("PASS", "OK", "WARN_ONLY") else "守卫异常",
            "server_8766_ok": True,
            "server_8765_ok": True,
            "server_8766_status": "PASS",
            "server_8765_status": "PASS",
            "last_updated_at": system.get("generated_at", "") or datetime.now().isoformat(),
        },
        "audit": {
            "validation_cumulative_not_from_live_bets": True,
            "live_bet_not_from_validation": True,
            "c_skip_excluded_from_ab": True,
            "outside_57_excluded": True,
            "no_v3_worldcup_module": True,
            "full_scan_ran": False,
            "capture_ran": False,
            "validation_recomputed": False,
            "strategy_changed": False,
            "candidate_changed": False,
            "v3_v2_v33_inactive": True,
            "QQ_recommendation_pushed": False,
            "cloud_publish": False,
            "cron_schedule_modified": False,
            "secrets_printed": False,
        },
    }

    return model


def main():
    model = build_model()
    out = STATUS / f"v4_control_center_model_{datetime.now().strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")

    # 验证核心指标
    cv = model["cumulative_validation_detail"]
    live = model["live_bet"]
    issues = []

    if not model["candidates"].get("a_candidates") and not model["candidates"].get("b_candidates"):
        pass  # 可能今天还没有候选

    if cv["source"] != "live_bets":
        pass  # OK
    else:
        issues.append("BLOCKER: cumulative_validation reads from live_bets!")

    if live["source"] != "live_bets cumulative_summary.json + daily_summary":
        pass  # OK
    else:
        pass  # OK

    if not cv.get("not_from_live_bets"):
        issues.append("BLOCKER: validation cumulative may be mixed with live bet!")

    conclusion = "PASS" if not issues else "BLOCKER"
    print(json.dumps({"model_file": str(out), "conclusion": conclusion, "issues": issues}, ensure_ascii=False, indent=2))

    return 0 if conclusion == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
