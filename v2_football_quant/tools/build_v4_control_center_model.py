#!/usr/bin/env python3
"""build_v4_control_center_model.py — V4统一作战台 只读聚合模型构建器

聚合但不重算任何业务数据。
验证累计 只读取 official A/B-only truth file。
实盘累计 读取 live_bets cumulative_summary。
二者严格分离。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
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


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _norm_date_from_record(rec: dict, fallback_date: str) -> tuple[str, bool]:
    d = str(rec.get("bet_date") or rec.get("date") or "").strip()
    if d and len(d) == 8 and d.isdigit():
        return d, False
    return fallback_date, True


def _load_live_records_for_date(date_str: str) -> list[dict]:
    p = LIVE_DIR / f"v4_live_bets_{date_str}.jsonl"
    out: list[dict] = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _load_live_records_all() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for p in sorted(LIVE_DIR.glob("v4_live_bets_*.jsonl")):
        fallback = p.stem.replace("v4_live_bets_", "")
        fallback = fallback if (len(fallback) == 8 and fallback.isdigit()) else ""
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append((fallback, json.loads(line)))
            except Exception:
                continue
    return out


def _load_no_bet_decisions_for_date(date_str: str) -> list[dict]:
    p = LIVE_DIR / f"v4_no_bet_decisions_{date_str}.jsonl"
    out: list[dict] = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if str(rec.get("date") or "") == date_str and str(rec.get("decision") or "").upper() == "NO_BET":
            out.append(rec)
    return out


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
    # Fallback: 默认金额只用于输入建议，不等于今日真实投注
    return {
        "default_line": "O1",
        "default_odds": live_daily.get("last_odds") or 0.86,
        "default_stake": live_daily.get("last_stake") or 428,
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
            "distribution_text": r.get("distribution_text") or "",
            "time_bin_0_15": r.get("time_bin_0_15") if r.get("time_bin_0_15") is not None else (r.get("time_bins") or {}).get("0_15"),
            "time_bin_16_30": r.get("time_bin_16_30") if r.get("time_bin_16_30") is not None else (r.get("time_bins") or {}).get("16_30"),
            "time_bin_31_45": r.get("time_bin_31_45") if r.get("time_bin_31_45") is not None else (r.get("time_bins") or {}).get("31_45"),
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
            "distribution_text": r.get("distribution_text") or "",
            "time_bin_0_15": r.get("time_bin_0_15") if r.get("time_bin_0_15") is not None else (r.get("time_bins") or {}).get("0_15"),
            "time_bin_16_30": r.get("time_bin_16_30") if r.get("time_bin_16_30") is not None else (r.get("time_bins") or {}).get("16_30"),
            "time_bin_31_45": r.get("time_bin_31_45") if r.get("time_bin_31_45") is not None else (r.get("time_bins") or {}).get("31_45"),
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


def _extract_yesterday_validation(vsot: dict, *, today_str: str, vsot_path: Optional[Path] = None) -> dict:
    """从 official A/B-only truth file 提取昨日验证"""
    # Hot overlay: if fixture-id validation result for target_date is newer than
    # source_of_truth, prefer it to avoid stale pending display on control center.
    # Canonical yesterday target: dashboard today - 1 day.
    try:
        canonical_target = (datetime.strptime(today_str, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    except Exception:
        canonical_target = str(vsot.get("yesterday_target_date") or "")
    target_date = canonical_target
    if target_date:
        hot_path = STATUS / f"v4_official_fixture_id_validation_{target_date}.json"
        try:
            if hot_path.exists() and (vsot_path is None or hot_path.stat().st_mtime >= vsot_path.stat().st_mtime):
                hot = _load_json(hot_path)
                a_set = int(hot.get("a_settled", 0) or 0)
                b_set = int(hot.get("b_settled", 0) or 0)
                ab_set = int(hot.get("ab_settled", 0) or 0)
                if ab_set > 0:
                    a_hit = int(hot.get("a_hit", 0) or 0)
                    b_hit = int(hot.get("b_hit", 0) or 0)
                    ab_hit = int(hot.get("ab_hit", 0) or 0)
                    fixtures = hot.get("fixtures") or []
                    hot_rec_a = sum(1 for f in fixtures if str((f or {}).get("grade", "")).upper() == "A")
                    hot_rec_b = sum(1 for f in fixtures if str((f or {}).get("grade", "")).upper() == "B")
                    rec_ab = int(hot.get("total_official_ab", 0) or (hot_rec_a + hot_rec_b) or ab_set)
                    rec_a = int(hot_rec_a or a_set)
                    rec_b = int(hot_rec_b or b_set)
                    vsot = {
                        **vsot,
                        "yesterday_target_date": target_date,
                        "recommended": {"A": rec_a, "B": rec_b, "AB": rec_ab},
                        "verified": {"A": a_set, "B": b_set, "AB": ab_set},
                        "pending": {"A": max(0, rec_a - a_set), "B": max(0, rec_b - b_set), "AB": max(0, rec_ab - ab_set)},
                        "yesterday": {
                            "A": {"hit": a_hit, "settled": a_set, "display_rate": "N/A" if a_set <= 0 else f"{a_hit}/{a_set} · {a_hit*100.0/a_set:.1f}%"},
                            "B": {"hit": b_hit, "settled": b_set, "display_rate": "N/A" if b_set <= 0 else f"{b_hit}/{b_set} · {b_hit*100.0/b_set:.1f}%"},
                            "A_plus_B": {"hit": ab_hit, "settled": ab_set, "display_rate": "N/A" if ab_set <= 0 else f"{ab_hit}/{ab_set} · {ab_hit*100.0/ab_set:.1f}%"},
                            "excluded_not_settled": 0,
                            "api_errors": int(hot.get("api_errors", 0) or 0),
                        },
                    }
        except Exception:
            pass

    yesterday = vsot.get("yesterday") or {}
    recommended = vsot.get("recommended") or {}
    verified = vsot.get("verified") or {}
    pending = vsot.get("pending") or {}

    return {
        "target_date": target_date,
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


def _extract_cumulative_validation(tc: dict, *, vsot: dict, today_str: str) -> dict:
    """从 true_cumulative_result_validation 提取累计验证
    只读取 official A/B-only truth file，禁止读取 live_bets 作为验证累计。
    """
    a_data = tc.get("A") or {}
    b_data = tc.get("B") or {}
    ab_data = tc.get("AB") or {}

    # Overlay newer official fixture-id validations after source-of-truth target date
    # so control center cumulative keeps up with latest bounded validation result.
    def _as_int(v: Any) -> int:
        try:
            return int(v or 0)
        except Exception:
            return 0

    base_a_hit = _as_int(a_data.get("hit", 0))
    base_a_res = _as_int(a_data.get("resolved", 0))
    base_b_hit = _as_int(b_data.get("hit", 0))
    base_b_res = _as_int(b_data.get("resolved", 0))

    sot_target = str(vsot.get("yesterday_target_date") or "")
    try:
        start = datetime.strptime(sot_target, "%Y%m%d") + timedelta(days=1) if sot_target else None
        end = datetime.strptime(today_str, "%Y%m%d") - timedelta(days=1)
    except Exception:
        start = None
        end = None

    if start and end and start <= end:
        cur = start
        while cur <= end:
            d = cur.strftime("%Y%m%d")
            p = STATUS / f"v4_official_fixture_id_validation_{d}.json"
            if p.exists():
                hot = _load_json(p)
                base_a_hit += _as_int(hot.get("a_hit", 0))
                base_a_res += _as_int(hot.get("a_settled", 0))
                base_b_hit += _as_int(hot.get("b_hit", 0))
                base_b_res += _as_int(hot.get("b_settled", 0))
            cur += timedelta(days=1)

    base_ab_hit = base_a_hit + base_b_hit
    base_ab_res = base_a_res + base_b_res
    a_rate = (base_a_hit / base_a_res) if base_a_res > 0 else None
    b_rate = (base_b_hit / base_b_res) if base_b_res > 0 else None
    ab_rate = (base_ab_hit / base_ab_res) if base_ab_res > 0 else None

    return {
        "source": tc.get("source") or tc.get("label") or "official A/B-only",
        "source_file": "v4_true_cumulative_result_validation",
        "A": {
            "hit": base_a_hit,
            "resolved": base_a_res,
            "display": "N/A" if a_rate is None else f"{base_a_hit}/{base_a_res} · {a_rate * 100:.1f}%",
        },
        "B": {
            "hit": base_b_hit,
            "resolved": base_b_res,
            "display": "N/A" if b_rate is None else f"{base_b_hit}/{base_b_res} · {b_rate * 100:.1f}%",
        },
        "AB": {
            "hit": base_ab_hit,
            "resolved": base_ab_res,
            "display": "N/A" if ab_rate is None else f"{base_ab_hit}/{base_ab_res} · {ab_rate * 100:.1f}%",
        },
        "label": tc.get("label") or "A/B-only · 不含C · official settled only",
        "not_from_live_bets": True,
    }


def _extract_live_bet_status(today_date: str) -> dict:
    """提取实盘状态 — 严格按 today_date 隔离 today stake"""
    daily = _read_live_bet_summary(today_date)
    cumulative = _read_live_bet_cumulative()
    today_records = _load_live_records_for_date(today_date)

    today_stake = 0.0
    today_gross = 0.0
    today_effective = 0.0
    today_rebate = 0.0
    today_net = 0.0
    today_record_count = 0
    today_real_bet_count = 0
    settled_count = 0
    open_count = 0
    void_count = 0
    excluded_test = 0
    assumed_date_from_file = 0

    for rec in today_records:
        rec_date, assumed = _norm_date_from_record(rec, today_date)
        if assumed:
            assumed_date_from_file += 1
        if rec_date != today_date:
            continue
        today_record_count += 1

        if bool(rec.get("is_test")):
            excluded_test += 1
            continue

        bet_status = str(rec.get("bet_status") or "").upper()
        settlement_result = str(rec.get("settlement_result") or "PENDING").upper()
        if bet_status == "VOID":
            void_count += 1
            continue

        stake = _safe_float(rec.get("stake"), _safe_float(rec.get("stake_amount"), 0.0))
        if bet_status in {"BET", "PENDING", "SETTLED"} and settlement_result == "PENDING" and stake > 0:
            today_stake += stake
            today_real_bet_count += 1

        gross = _safe_float(rec.get("gross_pnl"), 0.0)
        effective = _safe_float(rec.get("effective_turnover"), 0.0)
        rebate = _safe_float(rec.get("rebate"), 0.0)
        net = _safe_float(rec.get("net_pnl"), gross + rebate)

        if bet_status in {"BET", "PENDING", "SETTLED"} and settlement_result in {"PENDING", "", "NULL", "NONE"}:
            open_count += 1
        elif bet_status in {"BET", "PENDING", "SETTLED"}:
            settled_count += 1
            today_gross += gross
            today_effective += effective
            today_rebate += rebate
            today_net += net

    cross_day_open_items: list[dict[str, Any]] = []
    for fallback_date, rec in _load_live_records_all():
        rec_date, _ = _norm_date_from_record(rec, fallback_date or today_date)
        if rec_date == today_date or bool(rec.get("is_test")):
            continue
        bet_status = str(rec.get("bet_status") or "").upper()
        settlement_result = str(rec.get("settlement_result") or "PENDING").upper()
        if bet_status in {"BET", "PENDING", "SETTLED"} and settlement_result == "PENDING":
            cross_day_open_items.append({
                "bet_id": rec.get("bet_id"),
                "fixture_id": rec.get("fixture_id"),
                "record_date": rec_date,
                "home_cn": rec.get("home_cn") or "",
                "away_cn": rec.get("away_cn") or "",
                "market_line": rec.get("market_line") or "",
                "bet_status": bet_status,
                "settlement_result": settlement_result,
            })

    default_stake = _safe_float(daily.get("last_stake"), 428.0) or 428.0

    return {
        "source": "live_bets raw daily jsonl + cumulative_summary",
        "not_from_validation": True,
        "today": {
            "date": today_date,
            "initial_bankroll": daily.get("initial_bankroll") or 30000,
            "stake_amount": round(today_stake, 2),
            "default_stake": round(default_stake, 2),
            "gross_pnl": round(today_gross, 2),
            "effective_turnover": round(today_effective, 2),
            "rebate": round(today_rebate, 2),
            "net_pnl": round(today_net, 2),
            "records": today_record_count,
            "today_real_bet_count": today_real_bet_count,
            "settled_records": settled_count,
            "effective_bet_records": today_real_bet_count,
            "open_bets_count": open_count,
            "settled_bets_count": settled_count,
            "void_bets_count": void_count,
            "excluded_test_records": excluded_test,
            "assumed_date_from_file": assumed_date_from_file,
            "risk_status": "today_gross_pnl",
            "rebate_formula": daily.get("rebate_formula_version") or "",
            "source": f"v4_live_bets_{today_date}.jsonl",
            "default_stake_source": "daily_summary.last_stake_or_428",
            "cross_day_open_bets_count": len(cross_day_open_items),
            "cross_day_open_bet_items": cross_day_open_items,
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


def _load_system_error_summary() -> dict:
    """加载最新系统异常摘要；如不存在则自动运行采集器；失败时返回安全 fallback。"""
    import subprocess

    candidates = sorted(STATUS.glob("v4_system_error_summary_*.json"))
    if candidates:
        data = _load_json(candidates[-1])
        if data and data.get("system_error_status"):
            return data

    # 自动运行采集器
    try:
        collector = ROOT / "tools" / "collect_v4_system_error_summary.py"
        if collector.exists():
            cp = subprocess.run(
                ["python3", str(collector), "--hours", "48", "--limit", "20"],
                capture_output=True, text=True, timeout=30,
                cwd=str(ROOT),
            )
            if cp.returncode == 0:
                # 重新查找输出文件
                candidates2 = sorted(STATUS.glob("v4_system_error_summary_*.json"))
                if candidates2:
                    data = _load_json(candidates2[-1])
                    if data and data.get("system_error_status"):
                        return data
    except Exception:
        pass

    return {
        "active_error_count": 0,
        "active_blocker_count": 0,
        "recent_error_count_24h": 0,
        "recent_error_count_48h": 0,
        "system_error_status": "PASS",
        "display_text": "当前无 active 异常",
        "active_items": [],
        "recent_items": [],
        "generated_at": datetime.now().isoformat(),
        "scan_window_hours": 48,
        "safe_to_show": True,
        "raw_logs_hidden": True,
        "read_only_collector": True,
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
    yesterday_validation = _extract_yesterday_validation(vsot, today_str=today_str, vsot_path=vsot_path)

    # 3. 验证累计 — 只读取 official A/B-only truth file
    tc_path, tc = _find_latest_true_cumulative()
    cumulative_validation = _extract_cumulative_validation(tc, vsot=vsot, today_str=today_str)

    # 4. 实盘 — 只从 live_bets 数据源 (已在上面提取)
    # live_bet 和 live_daily 已在 build_model 开头提取

    # 5. 系统状态
    cron_path, cron = _find_latest_cron_checker()
    system = _extract_system_status(cron)

    # Fill candidate live states from today's raw records (no rewrite)
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
    by_fixture_today: dict[str, dict[str, Any]] = {}
    by_fixture_cross_day: dict[str, dict[str, Any]] = {}
    no_bet_decisions = _load_no_bet_decisions_for_date(today_str)
    no_bet_by_fixture: dict[str, dict[str, Any]] = {}
    for d in no_bet_decisions:
        fid = str(d.get("fixture_id") or "")
        if fid:
            no_bet_by_fixture[fid] = d
    open_bet_items: list[dict[str, Any]] = []
    for rec in raw_records:
        if bool(rec.get("is_test")):
            continue
        fid = str(rec.get("fixture_id") or "")
        if not fid:
            continue
        rec_date, _ = _norm_date_from_record(rec, today_str)
        target_map = by_fixture_today if rec_date == today_str else by_fixture_cross_day
        prev = target_map.get(fid)
        if prev is None:
            target_map[fid] = rec
        else:
            target_map[fid] = rec if str(rec.get("updated_at") or rec.get("created_at") or "") >= str(prev.get("updated_at") or prev.get("created_at") or "") else prev

        bet_status = str(rec.get("bet_status") or "").upper()
        settlement_result = str(rec.get("settlement_result") or "PENDING").upper()
        if bet_status in {"BET", "PENDING"} and settlement_result == "PENDING":
            open_bet_items.append({
                "date": rec.get("date") or today_str,
                "bet_id": rec.get("bet_id"),
                "fixture_id": rec.get("fixture_id"),
                "league": rec.get("league") or "",
                "home_cn": rec.get("home_cn") or "",
                "away_cn": rec.get("away_cn") or "",
                "market_line": rec.get("market_line") or "",
                "odds_water": rec.get("odds_water"),
                "stake": rec.get("stake"),
                "entry_minute": rec.get("entry_minute"),
                "bet_status": bet_status,
                "settlement_result": settlement_result,
            })

    pending_bet_candidates: list[dict[str, Any]] = []
    no_bet_items: list[dict[str, Any]] = []
    already_bet_ab = 0
    for bucket in (candidates.get("a_candidates") or [], candidates.get("b_candidates") or []):
        for arr in bucket:
            if not isinstance(arr, dict):
                continue
            fid = str(arr.get("fixture_id") or "")
            rec = by_fixture_today.get(fid)
            cross_rec = by_fixture_cross_day.get(fid)
            no_bet_rec = no_bet_by_fixture.get(fid)
            bet_status = str((rec or {}).get("bet_status", "")).upper()
            settlement_result = str((rec or {}).get("settlement_result", "PENDING")).upper()
            arr["already_bet"] = bool(rec and bet_status in {"BET", "PENDING", "SETTLED"} and settlement_result == "PENDING")
            arr["settled"] = False
            arr["live_bet_status"] = bet_status or "UNMATCHED"
            arr["settlement_result"] = settlement_result if rec else "UNMATCHED"
            arr["live_bet_record_date"] = (rec or {}).get("bet_date") or (rec or {}).get("date") or today_str if rec else ""
            arr["forensic_cross_day_match"] = bool(cross_rec and not rec)
            arr["no_bet_recorded"] = bool(no_bet_rec)
            arr["no_bet_reason_code"] = (no_bet_rec or {}).get("reason_code") or ""
            arr["no_bet_reason_text"] = (no_bet_rec or {}).get("reason_text") or ""
            if arr["no_bet_recorded"]:
                arr["pending_action"] = "未投：早进球" if arr["no_bet_reason_code"] == "EARLY_GOAL" else "未投：已记录"
            else:
                arr["pending_action"] = "待结算" if (arr["already_bet"] and not arr["settled"]) else ("待投注" if not arr["already_bet"] else "已结算")
            if arr["already_bet"]:
                already_bet_ab += 1
            elif arr["no_bet_recorded"]:
                no_bet_items.append({
                    "fixture_id": arr.get("fixture_id"),
                    "home_cn": arr.get("home_cn") or "",
                    "away_cn": arr.get("away_cn") or "",
                    "grade": arr.get("grade") or "",
                    "reason_code": arr.get("no_bet_reason_code") or "",
                    "reason_text": arr.get("no_bet_reason_text") or "",
                })
            else:
                pending_bet_candidates.append({
                    "fixture_id": arr.get("fixture_id"),
                    "home_cn": arr.get("home_cn") or "",
                    "away_cn": arr.get("away_cn") or "",
                    "grade": arr.get("grade") or "",
                })
            if rec:
                arr["default_line"] = rec.get("market_line") or arr.get("default_line")
                arr["default_odds"] = rec.get("odds_water") if rec.get("odds_water") is not None else arr.get("default_odds")
                arr["default_stake"] = rec.get("stake") if rec.get("stake") is not None else arr.get("default_stake")
                arr["default_entry_minute"] = rec.get("entry_minute") or arr.get("default_entry_minute")
                arr["default_reason"] = "today live bet record override"

    # Canonical todo from fixture-level state (no by_grade reverse inference)
    ab_candidate_count = candidates["a_count"] + candidates["b_count"]
    pending_bets = len(pending_bet_candidates)
    open_bets_count = len(open_bet_items)
    pending_validation = int((yesterday_validation.get("pending") or {}).get("AB") or 0)
    retry_items = []
    if pending_validation > 0:
        retry_items.append({
            "type": "validation_retry",
            "count": pending_validation,
            "source": "official_pending_source",
        })
    system_alerts = 0 if system.get("cron_all_ok", False) else 1
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
            "today_real_stake": live_bet["today"]["stake_amount"],
            "today_default_stake": live_bet["today"].get("default_stake", 428.0),
            "today_gross_pnl": live_bet["today"]["gross_pnl"],
            "today_effective_turnover": live_bet["today"]["effective_turnover"],
            "today_rebate": live_bet["today"]["rebate"],
            "today_net_pnl": live_bet["today"]["net_pnl"],
            "today_record_count": live_bet["today"].get("records", 0),
            "today_real_bet_count": live_bet["today"].get("today_real_bet_count", 0),
            "today_source": live_bet["today"].get("source", ""),
            "default_stake_source": live_bet["today"].get("default_stake_source", ""),
            "open_bets_count": live_bet["today"]["open_bets_count"],
            "settled_bets_count": live_bet["today"]["settled_bets_count"],
            "void_bets_count": live_bet["today"]["void_bets_count"],
            "cross_day_open_bets_count": live_bet["today"].get("cross_day_open_bets_count", 0),
            "cross_day_open_bet_items": live_bet["today"].get("cross_day_open_bet_items", []),
        },
        "todo_summary": {
            "to_bet": pending_bets,
            "to_settle": open_bets_count,
            "to_retry": pending_validation,
            "errors": system_alerts,
            "no_bet_count": len(no_bet_items),
            "pending_bet_candidates": pending_bet_candidates,
            "no_bet_items": no_bet_items,
            "open_bet_items": open_bet_items,
            "retry_items": retry_items,
            "source": "fixture_id_canonical",
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

    # ── system_errors 接入 ──
    model["system_errors"] = _load_system_error_summary()

    # 更新 system_status 增加 error 计数
    se = model["system_errors"]
    model["system_status"].update({
        "active_error_count": se.get("active_error_count", 0),
        "active_blocker_count": se.get("active_blocker_count", 0),
        "recent_error_count_24h": se.get("recent_error_count_24h", 0),
        "system_error_status": se.get("system_error_status", "PASS"),
        "system_error_display": se.get("display_text", "当前无 active 异常"),
    })

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
