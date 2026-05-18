#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any

try:
    from engine.v4_display_name_normalizer import display_name as _v4_display_name
except Exception:
    _v4_display_name = None

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
AUDIT_DIR = BASE_DIR / "data" / "runtime" / "audit"
CACHE_DIR = BASE_DIR / "data" / "runtime" / "cache"
DAILY_REPORT_DIR = BASE_DIR / "data" / "daily_reports"
V4_ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
STATE_DIR = BASE_DIR / "data" / "state"
OPS_SUMMARY_DIR = BASE_DIR / "data" / "ops" / "daily_ops_summary"
CAPTURE_AUDIT_DIR = BASE_DIR / "data" / "capture_audit"
LOG_DIR = BASE_DIR / "data" / "runtime" / "logs"
LEDGER_DIR = BASE_DIR / "data" / "runtime" / "ledger"
OUT_DIR = BASE_DIR / "data" / "runtime" / "dashboard"
ASSET_DIR = OUT_DIR / "assets"
STATE_CURRENT = BASE_DIR.parent / "STATE_CURRENT.md"

V4_SCRIPT_ARCHIVE_FIX_DATE = "20260518"

# 阅读层补充中文别名（仅展示，不改策略/评级）
READING_ALIAS = {
    "New York Red Bulls": "纽约红牛",
    "New York City FC": "纽约城",
    "Bodo/Glimt": "博德闪耀",
    "Tromso": "特罗姆瑟",
    "Valerenga": "瓦勒伦加",
    "Sarpsborg 08 FF": "萨普斯堡",
    "Sligo Rovers": "斯莱戈流浪者",
    "Galway United": "戈尔韦联",
    "Penarol": "佩纳罗尔",
    "Liverpool Montevideo": "蒙得维的亚利物浦",
    "Internacional": "巴西国际",
    "Vasco DA Gama": "达伽马",
    "Philadelphia Union": "费城联合",
    "Columbus Crew": "哥伦布机员",
    "Cherno More Varna": "查洛摩利",
    "Gnistan": "格尼斯坦",
    "FF Jaro": "雅罗",
    "Atromitos": "阿特罗米托斯",
    "Al Okhdood": "欧鲁巴赫多德",
    "Austin": "奥斯汀FC",
    "Minnesota United FC": "明尼苏达联",
    "Real Salt Lake": "皇家盐湖城",
    "Colorado Rapids": "科罗拉多急流",
}

V4_SCAN_WINDOWS = [
    {
        "label": "凌晨",
        "key": "late",
        "aliases": ["late"],
        "cron_id": "4450d249",
        "plan_time": "01:20",
        "log_candidates": ["v4_scan_late_{date}.log"],
    },
    {
        "label": "早场",
        "key": "early",
        "aliases": ["early"],
        "cron_id": "e1863187",
        "plan_time": "07:20",
        "log_candidates": ["v4_scan_early_{date}.log"],
    },
    {
        "label": "午间",
        "key": "midday",
        "aliases": ["midday", "noon"],
        "cron_id": "708f26f9",
        "plan_time": "14:05",
        "log_candidates": ["v4_scan_midday_{date}.log", "v4_scan_noon_{date}.log"],
    },
    {
        "label": "傍晚",
        "key": "evening",
        "aliases": ["evening"],
        "cron_id": "0443f80e",
        "plan_time": "16:20",
        "log_candidates": ["v4_scan_evening_{date}.log"],
    },
    {
        "label": "晚间",
        "key": "night",
        "aliases": ["night"],
        "cron_id": "b022bce3",
        "plan_time": "22:20",
        "log_candidates": ["v4_scan_night_{date}.log"],
    },
]


@dataclass
class FileRef:
    label: str
    path: Path

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def rel(self) -> str:
        try:
            return str(self.path.relative_to(BASE_DIR))
        except Exception:
            return str(self.path)


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return default


def _latest(pattern: str) -> Path | None:
    files = sorted(BASE_DIR.glob(pattern))
    return files[-1] if files else None


STATUS_ZH = {
    "BET_LOCKED_DAY": "有正式锁定",
    "ABNORMAL": "异常日",
    "NO_BET_NORMAL": "正常无单",
    "NORMAL": "正常",
    "MISSING": "缺失",
    "DONE": "已完成",
    "PASS": "通过",
    "FAIL": "失败",
    "FAILED": "失败",
    "PARTIAL_DONE": "部分完成",
    "SUCCESS": "成功",
    "RUNNING": "运行中",
    "SENT": "已发送",
    "DELIVERED_UNCONFIRMED": "已发送待确认",
    "SKIPPED_STARTED_OR_CLOSED": "已跳过（已开赛/已关闭）",
    "REVIEW_PARTIAL": "复盘部分完成",
    "TIMEOUT": "超时",
    "CHAIN_INCOMPLETE": "链路不完整",
    "BLOCKER": "阻断",
    "NEXT_RUN_AT_ANOMALY": "nextRunAt文件态异常",
    "P2_DASHBOARD_LOCAL_ONLY_NOT_VERSIONED": "仪表盘代码仅本地存在，尚未同步main",
    "FORBIDDEN_THIS_PHASE": "本阶段禁止写入",
    "PIPELINE_READY": "流程就绪",
    "CODE_READY": "代码就绪",
    "DELAYED": "延迟",
    "NO_PUSH": "未推送",
    "NO_SETTLEMENT_OBJECT": "无结算对象",
    "PARSE_FAILED": "解析失败",
    "NOT_DUE": "未到时间",
    "UNVERIFIED": "未验证",
    "HISTORICAL_NOT_ARCHIVED": "历史未归档",
    "WAITING_TRIGGER": "待自然触发",
    "PENDING": "待执行",
    "UNFINISHED": "未完成",
    "WARN": "警告",
    "NO": "否",
    "YES": "是",
}

ODDS_STATUS_ZH = {
    "LOCKED_IN_BAND": "锁定区间内",
    "IN_BAND": "区间内",
    "ABOVE_BAND": "高于区间",
    "BELOW_BAND": "低于区间",
    "NO_MARKET": "无盘口",
    "MOVED_OUT_BEFORE_LOCK": "锁定前漂出",
    "MOVED_OUT_AFTER_LOCK": "锁定后漂出",
}


def _status_zh(status: str | None) -> str:
    s = str(status or "MISSING").upper()
    return STATUS_ZH.get(s, s)


def _odds_status_zh(status: str | None) -> str:
    s = str(status or "").upper()
    if not s:
        return "缺失"
    return ODDS_STATUS_ZH.get(s, s)


def _status_tag(status: str | None) -> str:
    s = str(status or "MISSING").upper()
    if s in {"PASS", "DONE", "SENT", "SUCCESS", "NORMAL", "BET_LOCKED_DAY"}:
        cls = "ok"
    elif s in {"RUNNING", "PARTIAL_DONE", "REVIEW_PARTIAL", "DELIVERED_UNCONFIRMED", "SKIPPED_STARTED_OR_CLOSED", "DELAYED", "UNVERIFIED", "NOT_DUE", "HISTORICAL_NOT_ARCHIVED", "WAITING_TRIGGER", "PENDING"}:
        cls = "warn"
    elif s in {"FAIL", "FAILED", "TIMEOUT", "ABNORMAL", "BLOCKER", "CHAIN_INCOMPLETE", "MISSING", "PARSE_FAILED", "UNFINISHED"}:
        cls = "bad"
    else:
        cls = "neutral"
    return f'<span class="tag {cls}">{escape(_status_zh(s))}</span>'


def _priority_tag(p: str) -> str:
    p = p.upper()
    cls = {"P0": "bad", "P1": "warn", "P2": "neutral"}.get(p, "neutral")
    return f'<span class="tag {cls}">{p}</span>'


def _read_selected_fixtures(date_key: str) -> dict[str, Any]:
    path = STATE_DIR / f"selected_fixtures_{date_key}.json"
    return _load_json(path, {})


def _to_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _text_or_missing(x: Any) -> str:
    if x is None:
        return "缺失"
    s = str(x).strip()
    return s if s else "缺失"


def _parse_dt(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        return None


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _extract_abcs_from_text(text: str) -> dict[str, int] | None:
    clean = _strip_ansi(text)
    pats = [
        r"A\s*[:：]?\s*(\d+)\s*/\s*B\s*[:：]?\s*(\d+)\s*/\s*C\s*[:：]?\s*(\d+)\s*/\s*SKIP\s*[:：]?\s*(\d+)",
        r"A(\d+)\s*/\s*B(\d+)\s*/\s*C(\d+)\s*/\s*SKIP(\d+)",
    ]
    for pat in pats:
        m = re.search(pat, clean, flags=re.IGNORECASE)
        if m:
            a, b, c, skip = [int(x) for x in m.groups()]
            return {"a": a, "b": b, "c": c, "skip": skip}
    return None


def _extract_scan_log_meta(log_path: Path) -> dict[str, Any]:
    if not log_path.exists():
        return {"exists": False, "complete": False, "counts": None, "scan_total": None, "last_line_time": None}
    text = _load_text(log_path, "")
    clean = _strip_ansi(text)
    complete = ("球探扫描完成" in clean) or ("V4 球探扫描完成" in clean)
    counts = _extract_abcs_from_text(clean)
    scan_total = None
    pre_funnel_total = None
    h2h_insufficient = None
    below_threshold = None
    api_errors = None
    no_market = None
    m_total = re.search(r"球探报告[:：]\s*(\d+)", clean)
    if m_total:
        scan_total = int(m_total.group(1))
    m_prefunnel = re.search(r"前置漏斗[:：]\s*(\d+)\s*场", clean)
    if m_prefunnel:
        pre_funnel_total = int(m_prefunnel.group(1))
    m_summary = re.search(
        r"总数[:：]\s*(\d+)\s*→\s*H2H不足[:：]\s*(\d+)\s*→\s*未达标[:：]\s*(\d+)\s*→\s*API错误[:：]\s*(\d+)\s*→\s*无盘口[:：]\s*(\d+)\s*→\s*🔭球探报告[:：]\s*(\d+)",
        clean,
    )
    if m_summary:
        pre_funnel_total = int(m_summary.group(1))
        h2h_insufficient = int(m_summary.group(2))
        below_threshold = int(m_summary.group(3))
        api_errors = int(m_summary.group(4))
        no_market = int(m_summary.group(5))
        scan_total = int(m_summary.group(6))
    ts_matches = re.findall(r"(\d{2}:\d{2}:\d{2})", clean)
    last_line_time = ts_matches[-1] if ts_matches else None
    return {
        "exists": True,
        "complete": complete,
        "counts": counts,
        "scan_total": scan_total,
        "pre_funnel_total": pre_funnel_total,
        "h2h_insufficient": h2h_insufficient,
        "below_threshold": below_threshold,
        "api_errors": api_errors,
        "no_market": no_market,
        "last_line_time": last_line_time,
    }


def _extract_counts_from_json_obj(obj: Any) -> dict[str, int] | None:
    if not isinstance(obj, dict):
        return None
    keys = ("a_count", "b_count", "c_count", "skip_count")
    if all(k in obj for k in keys):
        return {
            "a": _to_int(obj.get("a_count")),
            "b": _to_int(obj.get("b_count")),
            "c": _to_int(obj.get("c_count")),
            "skip": _to_int(obj.get("skip_count")),
        }
    return None


def _parse_v4_qq_brief(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "parse_ok": False}
    text = _load_text(path, "")
    if not text:
        return {"exists": True, "parse_ok": False, "raw_text": ""}

    lines = [ln.rstrip() for ln in text.splitlines()]
    counts = _extract_abcs_from_text(text)

    scan_total = None
    intel_total = None
    cover_ab = None
    m_head = re.search(r"扫描(\d+)场｜情报(\d+)场.*A\+B覆盖([0-9.]+%)", text)
    if m_head:
        scan_total = _to_int(m_head.group(1), 0)
        intel_total = _to_int(m_head.group(2), 0)
        cover_ab = m_head.group(3)

    a_items: list[str] = []
    b_items: list[str] = []
    c_summary = ""
    skip_summary = ""
    generated_time = ""
    source_window = ""
    parsed_matches: list[dict[str, Any]] = []

    def _has_cjk(s: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", s or ""))

    def _norm_name(name: str, is_league: bool = False) -> tuple[str, bool]:
        raw = (name or "").strip()
        if not raw:
            return raw, False
        mapped = raw
        if _v4_display_name is not None:
            mapped = _v4_display_name(raw, is_league=is_league)
        # 阅读层兜底别名：仅用于展示，不影响任何评级或证据判定
        if mapped == raw and not is_league:
            mapped = READING_ALIAS.get(raw, mapped)
        unmapped = (mapped == raw) and (not _has_cjk(raw))
        return mapped, unmapped

    def _time_bucket(hhmm: str) -> str:
        try:
            hh = int(hhmm.split(":")[0])
        except Exception:
            return "跨日/其他"
        if 0 <= hh < 6:
            return "00:00-06:00"
        if 6 <= hh < 12:
            return "06:00-12:00"
        if 12 <= hh < 18:
            return "12:00-18:00"
        if 18 <= hh < 24:
            return "18:00-24:00"
        return "跨日/其他"

    def _parse_match_block(lines_local: list[str], idx: int) -> dict[str, Any] | None:
        line = lines_local[idx].strip()
        m = re.match(r"^\d+\.\s*(.*?)\s+vs\s+(.*?)｜([^｜]+)｜(\d{2}-\d{2}\s+\d{2}:\d{2})\s*$", line)
        if not m:
            return None
        home_raw, away_raw, league_raw, kickoff = m.groups()
        home_cn, home_unmapped = _norm_name(home_raw, is_league=False)
        away_cn, away_unmapped = _norm_name(away_raw, is_league=False)
        league_cn, league_unmapped = _norm_name(league_raw, is_league=True)
        ht_score = "未提供"
        ht_rate = "未提供"
        avg_goals = "未提供"
        script_type = "未提供"
        time_bins = "未提供"

        if idx + 1 < len(lines_local):
            l2 = lines_local[idx + 1].strip()
            m2 = re.search(r"HT\s*([0-9]+)\s*｜\s*([0-9]+%)\s*｜\s*([0-9.]+球)\s*｜\s*剧本[:：]\s*(.+)$", l2)
            if m2:
                ht_score, ht_rate, avg_goals, script_type = [x.strip() for x in m2.groups()]
        if idx + 2 < len(lines_local):
            l3 = lines_local[idx + 2].strip()
            m3 = re.search(r"时段[:：]\s*(.+)$", l3)
            if m3:
                time_bins = m3.group(1).strip()

        kickoff_hhmm = kickoff.split()[-1] if " " in kickoff else kickoff
        return {
            "home_raw": home_raw,
            "away_raw": away_raw,
            "league_raw": league_raw,
            "home": home_cn,
            "away": away_cn,
            "league": league_cn,
            "home_unmapped": home_unmapped,
            "away_unmapped": away_unmapped,
            "league_unmapped": league_unmapped,
            "kickoff": kickoff,
            "kickoff_hhmm": kickoff_hhmm,
            "time_group": _time_bucket(kickoff_hhmm),
            "ht_score": ht_score,
            "ht_rate": ht_rate,
            "avg_goals": avg_goals,
            "script_type": script_type,
            "time_bins": time_bins,
            "source": "qq_brief",
            "production_evidence": False,
        }
    in_a = False
    in_b = False
    for i, ln in enumerate(lines):
        if ln.startswith("生成时间："):
            generated_time = ln.replace("生成时间：", "").strip()
        if ln.startswith("窗口："):
            source_window = ln.replace("窗口：", "").strip()
        if "【A级" in ln:
            in_a = True
            in_b = False
            continue
        if "【B级" in ln:
            in_b = True
            in_a = False
            continue
        if ln.startswith("【C级"):
            c_summary = ln.strip()
            in_a = False
            in_b = False
            continue
        if ln.startswith("【跳过原因】"):
            skip_summary = ln.replace("【跳过原因】", "").strip()
            in_a = False
            in_b = False
            continue
        if in_a and re.match(r"^\d+\.\s*", ln.strip()):
            a_items.append(ln.strip())
            rec = _parse_match_block(lines, i)
            if rec is not None:
                rec["grade"] = "A"
                parsed_matches.append(rec)
        if in_b and re.match(r"^\d+\.\s*", ln.strip()):
            b_items.append(ln.strip())
            rec = _parse_match_block(lines, i)
            if rec is not None:
                rec["grade"] = "B"
                parsed_matches.append(rec)

    skip_reason_items = []
    for mm in re.finditer(r"([^|｜]+?)\s*(\d+)场", skip_summary):
        reason = mm.group(1).strip()
        cnt = _to_int(mm.group(2), 0)
        if reason:
            skip_reason_items.append({"reason": reason, "count": cnt})

    c_rep = []
    m_c_rep = re.search(r"代表[:：](.+?)(?:等\d+场|$)", c_summary)
    if m_c_rep:
        c_rep = [x.strip() for x in m_c_rep.group(1).split("|") if x.strip()]

    parse_ok = bool(counts or a_items or b_items or c_summary or skip_summary or parsed_matches)
    return {
        "exists": True,
        "parse_ok": parse_ok,
        "source_path": str(path),
        "counts": counts,
        "scan_total": scan_total,
        "intel_total": intel_total,
        "ab_cover": cover_ab,
        "a_items": a_items,
        "b_items": b_items,
        "ab_matches": parsed_matches,
        "c_summary": c_summary,
        "c_representatives": c_rep,
        "skip_summary": skip_summary,
        "skip_reason_items": skip_reason_items,
        "generated_time": generated_time,
        "source_window": source_window,
        "raw_excerpt": "\n".join(lines[:30]),
        "raw_text": text,
    }


def _window_planned_dt(date_key: str, hhmm: str) -> datetime | None:
    try:
        return datetime.strptime(f"{date_key} {hhmm}", "%Y%m%d %H:%M")
    except Exception:
        return None


def _review_due_dt(date_key: str) -> datetime | None:
    try:
        base = datetime.strptime(date_key, "%Y%m%d")
        return base + timedelta(days=1, hours=12, minutes=35)
    except Exception:
        return None


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "缺失"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_missed_audit(obj: Any) -> list[dict[str, Any]]:
    if not obj:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("missed_candidates", "rows", "candidates", "items", "fixtures"):
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _compute_v2(date_key: str) -> dict[str, Any]:
    refs = {
        "daily_status_push": FileRef("v2_daily_status_push", STATUS_DIR / f"v2_daily_status_push_{date_key}.json"),
        "missed_candidates_audit": FileRef("v2_missed_lock_candidates", AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json"),
        "window_latest": FileRef("v2_window_latest", STATUS_DIR / "v2_window_latest.json"),
        "window_notify": FileRef("v2_window_notify", STATUS_DIR / f"v2_window_notify_{date_key}.json"),
        "daily_pool_task": FileRef("task_status_v2_daily_pool", STATUS_DIR / "task_status_v2_daily_pool.json"),
        "window_hourly_task": FileRef("task_status_v2_window_hourly", STATUS_DIR / "task_status_v2_window_hourly.json"),
        "daily_pool_summary": FileRef("v2_daily_pool_summary", STATUS_DIR / f"v2_daily_pool_summary_{date_key}.json"),
        "daily_pool_push": FileRef("v2_daily_pool_push", STATUS_DIR / f"v2_daily_pool_push_{date_key}.json"),
        "daily_settle_task": FileRef("task_status_v2_daily_settle", STATUS_DIR / "task_status_v2_daily_settle.json"),
        "daily_settle_push": FileRef("v2_settle_push", STATUS_DIR / f"v2_settle_push_{date_key}.json"),
        "selected_state": FileRef("selected_fixtures", STATE_DIR / f"selected_fixtures_{date_key}.json"),
    }

    daily_status_push = _load_json(refs["daily_status_push"].path, {})
    missed_audit = _load_json(refs["missed_candidates_audit"].path, {})
    wl = _load_json(refs["window_latest"].path, {})
    notify = _load_json(refs["window_notify"].path, {})
    pool_task = _load_json(refs["daily_pool_task"].path, {})
    hourly_task = _load_json(refs["window_hourly_task"].path, {})
    pool_summary = _load_json(refs["daily_pool_summary"].path, {})
    pool_push = _load_json(refs["daily_pool_push"].path, {})
    settle_task = _load_json(refs["daily_settle_task"].path, {})
    settle_push = _load_json(refs["daily_settle_push"].path, {})
    selected = _read_selected_fixtures(date_key)

    fixtures = selected.get("fixtures", {}) if isinstance(selected, dict) else {}
    locked: list[dict[str, Any]] = []
    settlement_targets: list[dict[str, Any]] = []
    missed_fallback: list[dict[str, Any]] = []

    # 优先级3：严格正式锁定义，不再从候选池推断。
    for fid, st in fixtures.items():
        if not isinstance(st, dict):
            continue
        status = str(st.get("status") or "").upper()
        lock_owner = str(st.get("lock_owner") or "")
        official_bet_locked = bool(st.get("official_bet_locked") is True)
        is_official = (
            official_bet_locked
            and lock_owner == "window_checker"
            and status == "BET_LOCKED"
        )
        row = {
            "fixture_id": str(fid),
            "locked_stage": st.get("locked_stage"),
            "locked_odds_D": st.get("locked_odds_D"),
            "final_odds_status": st.get("final_odds_status"),
            "last_seen_stage": st.get("last_seen_stage"),
            "last_seen_odds_D": st.get("last_seen_odds_D"),
            "status": st.get("status"),
            "lock_owner": st.get("lock_owner"),
            "official_bet_locked": st.get("official_bet_locked"),
        }
        if is_official:
            locked.append(row)
            if bool(st.get("settlement_required") is True):
                settlement_targets.append(row)
        # fallback: 用于 audit 缺失时的错过候选估算（不计入正式锁）
        if bool(st.get("lock_owner_conflict_detected")) and str(st.get("conflict_reason", "")).startswith("prelocked_by_"):
            missed_fallback.append(
                {
                    "fixture_id": str(fid),
                    "reason": st.get("conflict_reason"),
                    "last_seen_stage": st.get("last_seen_stage"),
                    "last_seen_odds_D": st.get("last_seen_odds_D"),
                    "final_odds_status": st.get("final_odds_status"),
                }
            )

    locked = sorted(locked, key=lambda x: str(x.get("locked_stage") or ""))
    settlement_targets = sorted(settlement_targets, key=lambda x: str(x.get("fixture_id") or ""))

    missed_rows = _parse_missed_audit(missed_audit)
    if missed_rows:
        missed = []
        for r in missed_rows:
            missed.append(
                {
                    "fixture_id": str(r.get("fixture_id") or r.get("id") or r.get("match_id") or "-"),
                    "reason": str(r.get("reason") or r.get("status") or "AUDIT"),
                    "last_seen_stage": r.get("last_seen_stage"),
                    "last_seen_odds_D": r.get("last_seen_odds_D"),
                    "final_odds_status": r.get("final_odds_status"),
                }
            )
    else:
        missed = missed_fallback
    missed = sorted(missed, key=lambda x: str(x.get("fixture_id") or ""))

    # 优先级1：状态回执
    if isinstance(daily_status_push, dict) and daily_status_push:
        final_status = str(daily_status_push.get("status") or "MISSING").upper()
        official_locked_count = _to_int(daily_status_push.get("official_bet_locked"), default=len(locked))
        missed_count = _to_int(daily_status_push.get("missed_candidates"), default=len(missed))
        production_recommendation = _to_int(
            daily_status_push.get("production_recommendation"),
            default=official_locked_count,
        )
        settlement_required = _to_int(
            daily_status_push.get("settlement_required"),
            default=len(settlement_targets),
        )
        pushed_flag = daily_status_push.get("pushed")
        pushed_status = "SENT" if pushed_flag is True else ("MISSING" if pushed_flag is None else "NO_PUSH")
    else:
        official_locked_count = len(locked)
        missed_count = len(missed)
        production_recommendation = official_locked_count
        settlement_required = len(settlement_targets)
        pushed_bool = bool(notify.get("pushed") is True and _to_int(notify.get("new_bet_locked")) > 0)
        pushed_status = "SENT" if pushed_bool else "NO_PUSH"
        if official_locked_count > 0:
            final_status = "BET_LOCKED_DAY"
        elif missed_count > 0:
            final_status = "ABNORMAL"
        else:
            final_status = "NO_BET_NORMAL"

    settlement_status = str(settle_task.get("status") or "MISSING").upper()
    if settlement_required == 0 and settlement_status in {"DONE", "PARTIAL_DONE"}:
        settlement_status = "NO_SETTLEMENT_OBJECT"

    return {
        "refs": refs,
        "daily_status_push": daily_status_push,
        "missed_audit": missed_audit,
        "window_latest": wl,
        "window_notify": notify,
        "daily_pool_task": pool_task,
        "window_hourly_task": hourly_task,
        "daily_pool_summary": pool_summary,
        "daily_pool_push": pool_push,
        "daily_settle_task": settle_task,
        "daily_settle_push": settle_push,
        "locked": locked,
        "settlement_targets": settlement_targets,
        "missed": missed,
        "final_status": final_status,
        "official_locked_count": official_locked_count,
        "missed_count": missed_count,
        "production_recommendation": production_recommendation,
        "settlement_required": settlement_required,
        "pushed_status": pushed_status,
        "settlement_status": settlement_status,
    }


def _compute_v4_scan(date_key: str) -> dict[str, Any]:
    now = datetime.now()
    script_archive_file = DAILY_REPORT_DIR / f"v4_script_type_archive_{date_key}.json"
    dist_archive_file = DAILY_REPORT_DIR / f"v4_script_distribution_{date_key}.json"
    is_historical_pre_archive = date_key < V4_SCRIPT_ARCHIVE_FIX_DATE

    rows: list[dict[str, Any]] = []
    guard_fail_items: list[str] = []
    guard_warn_items: list[str] = []

    for spec in V4_SCAN_WINDOWS:
        label = spec["label"]
        key = spec["key"]
        task_path = STATUS_DIR / f"task_status_v4_scan_{key}.json"
        task = _load_json(task_path, {})
        task_date = str(task.get("date") or "")
        task_date_mismatch = bool(task_date and task_date != date_key)
        if task_date_mismatch:
            task = {}
        task_status = str(task.get("status", "MISSING")).upper()
        planned_dt = _window_planned_dt(date_key, spec["plan_time"])

        log_candidates = [LOG_DIR / pat.format(date=date_key) for pat in spec.get("log_candidates", [])]
        task_log = task.get("output_files", {}).get("scan_log")
        if task_log:
            log_candidates.append(Path(str(task_log)))
        log_path = next((p for p in log_candidates if p.exists()), None)
        log_meta = _extract_scan_log_meta(log_path) if log_path else {"exists": False, "complete": False, "counts": None, "scan_total": None, "last_line_time": None}

        push_marker_candidates: list[Path] = []
        status_structured_candidates: list[Path] = []
        archive_structured_candidates: list[Path] = []
        for alias in spec.get("aliases", [key]):
            push_marker_candidates.append(STATUS_DIR / f"v4_scan_push_{date_key}_{alias}.json")
            status_structured_candidates.append(STATUS_DIR / f"v4_scan_{date_key}_{alias}.json")
            archive_structured_candidates.append(V4_ARCHIVE_DIR / f"v4_scan_structured_{date_key}_{alias}.json")

        source_type = "missing"
        source_path: Path | None = None
        source_obj: dict[str, Any] = {}
        counts: dict[str, int] | None = None
        fallback_used = False
        fallback_reason = ""
        parse_failed = False

        # 优先级1：窗口专属 status/structured/push marker
        p1_sources: list[tuple[str, Path]] = []
        p1_sources.extend([("window_status_marker", p) for p in status_structured_candidates])
        p1_sources.extend([("window_structured", p) for p in archive_structured_candidates])
        p1_sources.extend([("window_push_marker", p) for p in push_marker_candidates])

        for stype, spath in p1_sources:
            if not spath.exists():
                continue
            obj = _load_json(spath, {})
            c = _extract_counts_from_json_obj(obj)
            if c is not None:
                source_type = stype
                source_path = spath
                source_obj = obj if isinstance(obj, dict) else {}
                counts = c
                break

        # 优先级2：窗口专属日志解析
        if counts is None and log_path and log_path.exists():
            c = log_meta.get("counts")
            if c is not None:
                source_type = "window_log"
                source_path = log_path
                counts = c

        # 优先级3：明确 fallback（并显示路径与原因）
        if counts is None:
            fallback_candidates: list[tuple[str, Path, str]] = []
            if key == "midday":
                fallback_candidates.extend(
                    [
                        ("fallback_midday_corrected_v2", STATUS_DIR / f"v4_scan_push_{date_key}_midday_corrected_v2.json", "午间窗口使用 corrected_v2 回退"),
                        ("fallback_midday_corrected", STATUS_DIR / f"v4_scan_push_{date_key}_midday_corrected.json", "午间窗口使用 corrected 回退"),
                        ("fallback_midday_raw", STATUS_DIR / f"v4_scan_push_{date_key}_midday.json", "午间窗口使用原始 mid-day push 回退"),
                    ]
                )
            if key == "early":
                fallback_candidates.append(
                    ("fallback_latest_push", STATUS_DIR / f"v4_scan_push_{date_key}_latest.json", "早场窗口无专属push，使用latest回退")
                )
            fallback_candidates.append(
                ("fallback_qq_brief", DAILY_REPORT_DIR / f"v4_openclaw_brief_qq_{date_key}.txt", f"{label}窗口尝试从QQ简报回退")
            )

            for stype, spath, reason in fallback_candidates:
                if not spath.exists():
                    continue
                if stype == "fallback_qq_brief":
                    txt = _load_text(spath, "")
                    if f"窗口：{label}" not in txt:
                        continue
                    c = _extract_abcs_from_text(txt)
                else:
                    obj = _load_json(spath, {})
                    if stype == "fallback_latest_push":
                        note = str(obj.get("note", ""))
                        if "早场" not in note:
                            continue
                    c = _extract_counts_from_json_obj(obj)
                if c is not None:
                    source_type = stype
                    source_path = spath
                    counts = c
                    fallback_used = True
                    fallback_reason = reason
                    break

        if counts is None and (source_path is not None or log_meta.get("exists")):
            parse_failed = True

        if counts is None:
            a = b = c = skip = None
            grade = "MISSING"
        else:
            a, b, c, skip = counts["a"], counts["b"], counts["c"], counts["skip"]
            if a > 0:
                grade = "A"
            elif b > 0:
                grade = "B"
            elif c > 0:
                grade = "C"
            elif skip > 0:
                grade = "SKIP"
            else:
                grade = "MISSING"

        # 状态判定：不使用 latest 猜测，不让次日长期显示运行中
        status_code = "MISSING"
        status_reason = ""
        if planned_dt and now < planned_dt and not task and not log_meta.get("exists"):
            status_code = "NOT_DUE"
            status_reason = "尚未到计划时间"
        elif task_status in {"DONE", "SUCCESS"}:
            status_code = "DONE"
            status_reason = "task_status 已完成"
        elif bool(log_meta.get("complete")):
            status_code = "DONE"
            status_reason = "日志含扫描完成标记"
        elif task_status in {"FAIL", "FAILED", "TIMEOUT", "BLOCKER"}:
            status_code = "FAILED"
            status_reason = "任务状态失败"
        elif task_status == "RUNNING":
            hb = _parse_dt(task.get("last_heartbeat_at"))
            same_day = date_key == now.strftime("%Y%m%d")
            recent_hb = hb is not None and (now - hb) <= timedelta(minutes=20)
            near_window = planned_dt is not None and abs((now - planned_dt).total_seconds()) <= 3 * 3600
            if same_day and recent_hb and near_window:
                status_code = "UNVERIFIED"
                status_reason = "运行中，等待结束标记"
            else:
                status_code = "DELAYED"
                status_reason = "运行状态滞留且无新心跳证据"
        elif task_status == "DELAYED":
            status_code = "DELAYED"
            status_reason = "任务状态为延迟"
        elif task:
            status_code = "UNVERIFIED"
            status_reason = "有任务记录但缺少完成标记"
        elif log_meta.get("exists"):
            status_code = "UNVERIFIED"
            status_reason = "有日志但未识别完成标记"
        else:
            if planned_dt and now >= planned_dt:
                status_code = "MISSING"
                status_reason = "已过计划时间但无窗口产物"
            else:
                status_code = "NOT_DUE"
                status_reason = "尚未到计划时间"

        if status_code == "DONE" and counts is None:
            status_code = "PARSE_FAILED"
            status_reason = "扫描完成但A/B/C/SKIP未找到可解析来源"

        read_only_parse = {
            "available": bool(log_meta.get("exists")),
            "scan_total": log_meta.get("pre_funnel_total"),
            "scout_total": log_meta.get("scan_total"),
            "h2h_insufficient": log_meta.get("h2h_insufficient"),
            "below_threshold": log_meta.get("below_threshold"),
            "api_errors": log_meta.get("api_errors"),
            "no_market": log_meta.get("no_market"),
            "complete": bool(log_meta.get("complete")),
            "exit_code": 0 if task_status in {"DONE", "SUCCESS"} else (None if task_status in {"RUNNING", "UNVERIFIED"} else None),
            "parse_note": "仅从日志与状态文件只读补解析，不代表窗口专属计数",
        }

        if script_archive_file.exists():
            script_archive_status = "DONE"
        elif is_historical_pre_archive:
            script_archive_status = "HISTORICAL_NOT_ARCHIVED"
        else:
            script_archive_status = "MISSING"

        if dist_archive_file.exists():
            dist_archive_status = "DONE"
        elif is_historical_pre_archive:
            dist_archive_status = "HISTORICAL_NOT_ARCHIVED"
        else:
            dist_archive_status = "MISSING"

        push_marker_exists = any(p.exists() for p in push_marker_candidates)
        source_path_present = source_path is not None and source_path.exists()
        log_path_present = log_path is not None and log_path.exists()
        counts_present = counts is not None
        marker_source_exists = any(p.exists() for p in push_marker_candidates)
        window_specific_source = source_type in {"window_status_marker", "window_structured", "window_push_marker"}
        counts_parse_status = "ok"
        if counts is None:
            counts_parse_status = "failed" if parse_failed else "missing"
        elif source_type == "fallback_qq_brief":
            counts_parse_status = "failed"
        elif source_type.startswith("fallback_"):
            counts_parse_status = "fallback"

        checklist = {
            "cron_id_present": bool(spec.get("cron_id")),
            "log_path_present": log_path_present,
            "source_path_present": source_path_present,
            "window_specific_source": window_specific_source,
            "counts_present": counts_present,
            "counts_parse_status": counts_parse_status,
            "push_marker_checked": True,
            "marker_source_exists": marker_source_exists,
            "script_archive_status_checked": script_archive_status in {"DONE", "MISSING", "HISTORICAL_NOT_ARCHIVED"},
            "fallback_reason_present_if_used": (not fallback_used) or bool(fallback_reason),
            "task_date_matched": not task_date_mismatch,
            "status_not_parse_failed": status_code != "PARSE_FAILED",
            "status_not_running_stale": not (task_status == "RUNNING" and status_code == "DELAYED"),
        }

        reasons: list[str] = []
        warn_reasons: list[str] = []
        fail_reasons: list[str] = []

        if not checklist["cron_id_present"]:
            fail_reasons.append("cron_id_missing")
        if task_date_mismatch and not window_specific_source:
            warn_reasons.append("task_date_mismatch")
        if status_code == "PARSE_FAILED":
            fail_reasons.append("status_parse_failed")
        if not source_path_present:
            fail_reasons.append("source_path_missing")
        if status_code == "DONE" and not source_path_present:
            fail_reasons.append("done_without_source_path")
        if not counts_present:
            fail_reasons.append("counts_missing")
        if counts_parse_status == "failed":
            fail_reasons.append("counts_parse_failed")
        if fallback_used and not checklist["fallback_reason_present_if_used"]:
            fail_reasons.append("fallback_reason_missing")

        if fallback_used and counts_parse_status != "failed":
            if source_type == "fallback_latest_push":
                warn_reasons.append("uses_fallback_latest")
            else:
                warn_reasons.append("uses_fallback_source")
        if not window_specific_source and counts_present and counts_parse_status in {"ok", "fallback"}:
            warn_reasons.append("non_window_specific_counts_source")
        if not marker_source_exists and log_path_present:
            warn_reasons.append("marker_missing_but_log_present")
        if not checklist["status_not_running_stale"]:
            warn_reasons.append("running_stale_without_heartbeat")

        # 业务硬规则：晚间 qq 简报回退不能作为窗口完整证据，直接 FAIL
        if source_type == "fallback_qq_brief":
            fail_reasons.append("fallback_scope_unverified")

        checklist_status = "PASS"
        if fail_reasons:
            checklist_status = "FAIL"
        elif warn_reasons:
            checklist_status = "WARN"

        reasons.extend(fail_reasons if checklist_status == "FAIL" else [])
        if checklist_status == "WARN":
            reasons.extend(warn_reasons)
        if checklist_status == "PASS":
            reasons = []

        data_completeness = "完整" if checklist_status == "PASS" else ("回退展示" if checklist_status == "WARN" else "不完整")
        production_evidence = checklist_status == "PASS" and source_type in {"window_status_marker", "window_structured", "window_push_marker"}

        if checklist_status == "FAIL":
            guard_fail_items.extend([f"{key}_{r}" for r in fail_reasons])
        elif checklist_status == "WARN":
            guard_warn_items.extend([f"{key}_{r}" for r in warn_reasons])

        rows.append(
            {
                "window": label,
                "task_key": key,
                "cron_id": spec["cron_id"],
                "planned_time": spec["plan_time"],
                "task_path": task_path,
                "task": task,
                "window_status": status_code,
                "window_status_reason": status_reason,
                "task_date_mismatch": task_date_mismatch,
                "source_type": source_type,
                "source_path": str(source_path) if source_path else None,
                "counts_source": str(source_path) if (counts is not None and source_path) else None,
                "marker_source": str(next((p for p in push_marker_candidates if p.exists()), push_marker_candidates[0])),
                "log_source": str(log_path) if log_path else None,
                "log_complete": bool(log_meta.get("complete")),
                "scan_total": log_meta.get("scan_total"),
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "grade": grade,
                "a": a,
                "b": b,
                "c": c,
                "skip": skip,
                "parse_failed": parse_failed,
                "read_only_parse": read_only_parse,
                "script_archive_status": script_archive_status,
                "distribution_archive_status": dist_archive_status,
                "checklist": checklist,
                "checklist_status": checklist_status,
                "checklist_reasons": reasons,
                "data_completeness": data_completeness,
                "production_evidence": production_evidence,
            }
        )

    render_status = "PASS"
    if guard_fail_items:
        data_guard_status = "FAIL"
    elif guard_warn_items:
        data_guard_status = "WARN"
    else:
        data_guard_status = "PASS"

    window_results: dict[str, Any] = {}
    for r in rows:
        window_results[r["task_key"]] = {
            "checklist_status": r["checklist_status"],
            "production_evidence": r["production_evidence"],
            "reasons": r["checklist_reasons"],
            "source_type": r["source_type"],
            "source_path": r["source_path"],
        }

    guard = {
        "render_status": render_status,
        "data_guard_status": data_guard_status,
        "production_verified": False,
        "guard_status": data_guard_status,
        "checked_windows": [r["task_key"] for r in rows],
        "window_results": window_results,
        "fail_items": sorted(set(guard_fail_items)),
        "warn_items": sorted(set(guard_warn_items)),
        "generated_at": datetime.now().isoformat(),
    }
    guard_path = STATUS_DIR / f"dashboard_v4_scan_guard_{date_key}.json"
    guard_path.write_text(json.dumps(guard, ensure_ascii=False, indent=2), encoding="utf-8")

    # 阅读模式：优先读取可读简报（仅阅读，不作为生产证据）
    readable_sources: list[dict[str, Any]] = []
    qq_brief_path = DAILY_REPORT_DIR / f"v4_openclaw_brief_qq_{date_key}.txt"
    qq_brief = _parse_v4_qq_brief(qq_brief_path)
    if qq_brief.get("exists"):
        readable_sources.append(
            {
                "type": "qq_brief",
                "path": str(qq_brief_path),
                "parse_ok": bool(qq_brief.get("parse_ok")),
                "production_evidence": False,
            }
        )

    latest_push_path = STATUS_DIR / f"v4_scan_push_{date_key}_latest.json"
    if latest_push_path.exists():
        readable_sources.append(
            {
                "type": "latest_push",
                "path": str(latest_push_path),
                "parse_ok": True,
                "production_evidence": False,
            }
        )

    for r in rows:
        if r.get("production_evidence"):
            readable_sources.append(
                {
                    "type": "window_push_marker",
                    "path": r.get("source_path"),
                    "window": r.get("task_key"),
                    "parse_ok": True,
                    "production_evidence": True,
                }
            )

    dedup = {}
    for s in readable_sources:
        dedup[(s.get("type"), s.get("path"), s.get("window"))] = s
    readable_sources = list(dedup.values())

    if qq_brief.get("parse_ok") or any(s.get("production_evidence") for s in readable_sources):
        reading_status = "PASS"
    elif qq_brief.get("exists") or readable_sources:
        reading_status = "WARN"
    else:
        reading_status = "FAIL"

    return {
        "windows": rows,
        "guard": guard,
        "guard_path": guard_path,
        "reading_mode": {
            "enabled": True,
            "reading_status": reading_status,
            "qq_brief": qq_brief,
            "readable_sources": readable_sources,
        },
    }


def _find_latest_completed_review(exclude_date_key: str) -> dict[str, Any] | None:
    candidates: list[str] = []
    for p in STATUS_DIR.glob("v4_review_push_*.json"):
        m = re.search(r"v4_review_push_(\d{8})\.json$", p.name)
        if m:
            candidates.append(m.group(1))
    candidates = sorted(set(candidates), reverse=True)
    for d in candidates:
        if d == exclude_date_key:
            continue
        sent = _load_json(STATUS_DIR / f"v4_review_push_{d}.json", {})
        route = _load_json(STATUS_DIR / f"v4_review_route_{d}.json", {})
        guard = _load_json(STATUS_DIR / f"v4_review_guard_{d}.json", {})
        sent_ok = str(sent.get("status", "")).upper() in {"SENT", "DELIVERED_UNCONFIRMED"}
        route_ok = bool(route.get("allowed_to_push"))
        guard_ok = str(guard.get("guard_status", "")).upper() == "PASS"
        if sent_ok or (route_ok and guard_ok):
            return {
                "date": d,
                "sent_status": str(sent.get("status", "MISSING") or "MISSING").upper(),
                "allowed_to_push": route_ok,
                "guard_status": str(guard.get("guard_status", "MISSING") or "MISSING").upper(),
                "route_path": str((STATUS_DIR / f"v4_review_route_{d}.json")),
                "sent_path": str((STATUS_DIR / f"v4_review_push_{d}.json")),
                "guard_path": str((STATUS_DIR / f"v4_review_guard_{d}.json")),
            }
    return None


def _compute_v4_review(date_key: str) -> dict[str, Any]:
    step_files = {
        "validation": DAILY_REPORT_DIR / f"v4_ht_recommend_validation_{date_key}.json",
        "attribution": V4_ARCHIVE_DIR / f"v4_result_attribution_{date_key}.jsonl",
        "gen_structured": DAILY_REPORT_DIR / f"v4_review_structured_{date_key}.json",
        "renderer_full": DAILY_REPORT_DIR / f"v4_review_full_{date_key}.txt",
        "renderer_qq": DAILY_REPORT_DIR / f"v4_review_qq_{date_key}.txt",
        "guard_full": STATUS_DIR / f"v4_review_guard_{date_key}_full.json",
        "guard_qq": STATUS_DIR / f"v4_review_guard_{date_key}.json",
        "route_marker": STATUS_DIR / f"v4_review_route_{date_key}.json",
        "sent_marker": STATUS_DIR / f"v4_review_push_{date_key}.json",
    }
    route = _load_json(step_files["route_marker"], {})
    sent = _load_json(step_files["sent_marker"], {})
    guard_full = _load_json(step_files["guard_full"], {})
    guard_qq = _load_json(step_files["guard_qq"], {})
    review_task = _load_json(STATUS_DIR / "task_status_v4_daily_review.json", {})
    result_refresh_cache = _load_json(CACHE_DIR / f"v4_result_refresh_{date_key}.json", {})
    result_refresh_audit = _load_json(AUDIT_DIR / f"v4_review_result_refresh_{date_key}.json", {})
    stats = _load_json(DAILY_REPORT_DIR / f"v4_ht_recommend_validation_{date_key}.json", {})

    now = datetime.now()
    due_dt = _review_due_dt(date_key)
    due_reached = bool(due_dt and now >= due_dt)

    def step(name: str, path: Path, extra_ok: bool = True) -> dict[str, Any]:
        if not due_reached:
            return {"name": name, "path": path, "status": "WAITING_TRIGGER"}
        ok = path.exists() and extra_ok
        return {"name": name, "path": path, "status": "PASS" if ok else "MISSING"}

    steps = [
        step("1.赛后验证", step_files["validation"]),
        step("2.赛后归因", step_files["attribution"]),
        step("3.结构化产物", step_files["gen_structured"]),
        step("4.渲染全文", step_files["renderer_full"]),
        step("5.渲染QQ版", step_files["renderer_qq"]),
        step("6.全文守卫", step_files["guard_full"], extra_ok=str(guard_full.get("guard_status", "")).upper() == "PASS"),
        step("7.QQ守卫", step_files["guard_qq"], extra_ok=str(guard_qq.get("guard_status", "")).upper() == "PASS"),
        step("8.ReportAgent", step_files["route_marker"], extra_ok=bool(route.get("reportagent_called")) and str(route.get("reportagent_status", "")).upper() == "PASS"),
        step("9.路由与发送标记", step_files["sent_marker"], extra_ok=bool(route.get("allowed_to_push"))),
    ]

    complete = all(s["status"] == "PASS" for s in steps)
    push_allowed_raw = bool(route.get("allowed_to_push")) and str(guard_qq.get("guard_status", "")).upper() == "PASS"
    push_allowed = bool(due_reached and push_allowed_raw)
    pushed = bool(due_reached and str(sent.get("status", "")).upper() in {"SENT", "DELIVERED_UNCONFIRMED"})
    ab_hit = {
        "A": stats.get("A", {}),
        "B": stats.get("B", {}),
    } if isinstance(stats, dict) else {}

    if not due_reached:
        overall_status = "PENDING"
        overall_reason = "未到复盘时间"
    elif complete:
        overall_status = "DONE"
        overall_reason = "复盘链路已完成"
    else:
        passed = sum(1 for s in steps if s["status"] == "PASS")
        overall_status = "UNFINISHED" if passed > 0 else "MISSING"
        overall_reason = "复盘时间已过但产物缺失或未完成"

    latest_completed = _find_latest_completed_review(date_key)

    fail_items: list[str] = []
    if not due_reached:
        if any(s["status"] == "MISSING" for s in steps):
            fail_items.append("before_due_steps_mislabeled_missing")
        if push_allowed:
            fail_items.append("before_due_push_allowed_should_be_false")
        if overall_status != "PENDING":
            fail_items.append("before_due_overall_status_should_be_pending")
    else:
        if any(s["status"] == "WAITING_TRIGGER" for s in steps):
            fail_items.append("after_due_steps_should_not_waiting")
    if latest_completed and latest_completed.get("date") == date_key:
        fail_items.append("latest_completed_overrides_current_date")

    review_guard = {
        "guard_status": "FAIL" if fail_items else "PASS",
        "review_date": date_key,
        "review_due_time": _fmt_dt(due_dt),
        "current_time": _fmt_dt(now),
        "overall_status": overall_status,
        "fail_items": fail_items,
        "production_verified": False,
    }
    review_guard_path = STATUS_DIR / f"dashboard_v4_review_guard_{date_key}.json"
    review_guard_path.write_text(json.dumps(review_guard, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "steps": steps,
        "complete": complete,
        "push_allowed": push_allowed,
        "pushed": pushed,
        "route": route,
        "sent": sent,
        "guard_qq": guard_qq,
        "guard_full": guard_full,
        "task": review_task,
        "result_refresh_cache": result_refresh_cache,
        "result_refresh_audit": result_refresh_audit,
        "ab_hit": ab_hit,
        "review_date": date_key,
        "review_due_time": _fmt_dt(due_dt),
        "current_time": _fmt_dt(now),
        "due_reached": due_reached,
        "overall_status": overall_status,
        "overall_reason": overall_reason,
        "latest_completed": latest_completed,
        "review_guard": review_guard,
        "review_guard_path": review_guard_path,
        "production_verified": False,
    }


def _compute_system(date_key: str, step1_local_only: bool) -> dict[str, Any]:
    sys_summary = _load_json(STATUS_DIR / f"sys_daily_summary_{date_key}.json", {})
    ops_daily = _load_json(OPS_SUMMARY_DIR / f"v4_daily_ops_summary_{date_key}.json", {})
    budget = _load_json(CAPTURE_AUDIT_DIR / f"v4_api_budget_audit_{date_key}.json", {})
    capture = _load_json(CAPTURE_AUDIT_DIR / f"v4_live_capture_audit_{date_key}.json", {})
    invalid_sources = _load_json(STATUS_DIR / "invalid_sources_index.json", {})
    state_md = _load_text(STATE_CURRENT, "")

    task_files = sorted(STATUS_DIR.glob("task_status_*.json"))
    cron_rows = []
    for f in task_files:
        obj = _load_json(f, {})
        cron_rows.append(
            {
                "task": obj.get("task_name", f.stem),
                "status": obj.get("status", "MISSING"),
                "finished_at": obj.get("finished_at"),
                "path": f,
            }
        )
    cron_rows = sorted(cron_rows, key=lambda x: str(x["task"]))

    issue_codes = sorted(set(re.findall(r"\bP[0-2]_[A-Z0-9_]+\b", state_md)))
    issues = {"P0": [], "P1": [], "P2": []}
    for code in issue_codes:
        if code.startswith("P0_"):
            issues["P0"].append(code)
        elif code.startswith("P1_"):
            issues["P1"].append(code)
        elif code.startswith("P2_"):
            issues["P2"].append(code)

    fixed = []
    for line in state_md.splitlines():
        if "✅" in line:
            fixed.append(line.strip("- ").strip())
    fixed = fixed[:10]

    tomorrow = []
    collecting = False
    for line in state_md.splitlines():
        if "明日" in line and "验收清单" in line:
            collecting = True
            continue
        if collecting:
            s = line.strip()
            if not s:
                break
            tomorrow.append(s)
    tomorrow = tomorrow[:10]

    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:12]

    jobs_anomaly = "MISSING"
    if "nextRunAt=None" in state_md or "nextRunAt=None" in json.dumps(sys_summary, ensure_ascii=False):
        jobs_anomaly = "NEXT_RUN_AT_ANOMALY"

    return {
        "sys_summary": sys_summary,
        "ops_daily": ops_daily,
        "budget": budget,
        "capture": capture,
        "invalid_sources": invalid_sources,
        "cron_rows": cron_rows,
        "issues": issues,
        "fixed": fixed,
        "tomorrow": tomorrow,
        "logs": logs,
        "jobs_anomaly": jobs_anomaly,
        "state_current_exists": STATE_CURRENT.exists(),
        "step1_local_only": step1_local_only,
    }


def _compute_api_cache(date_key: str) -> dict[str, Any]:
    dryrun_path = STATUS_DIR / f"api_snapshot_cache_dryrun_{date_key}.json"
    bundle_path = CACHE_DIR / "api_snapshot" / date_key / "bundle.json"
    check_path = STATUS_DIR / f"api_snapshot_cache_check_{date_key}.json"
    dryrun = _load_json(dryrun_path, {})
    bundle = _load_json(bundle_path, {})
    check = _load_json(check_path, {})
    safety_dry = dryrun if isinstance(dryrun, dict) else {}
    boundaries = bundle.get("boundaries", {}) if isinstance(bundle.get("boundaries", {}), dict) else {}
    safety_bundle = bundle.get("safety", {}) if isinstance(bundle.get("safety", {}), dict) else {}
    boundary_src = boundaries if boundaries else safety_bundle

    no_api = bool(safety_dry.get("no_api", boundary_src.get("no_api", False)))
    no_push = bool(safety_dry.get("no_push", boundary_src.get("no_push", False)))
    no_strategy_recompute = bool(
        safety_dry.get("no_strategy_recompute", boundary_src.get("no_strategy_recompute", False))
    )
    no_cron = bool(safety_dry.get("no_cron", boundary_src.get("no_cron", False)))
    production_verified = bool(
        safety_dry.get("production_verified", boundary_src.get("production_verified", False))
    )
    runtime_root = (
        safety_dry.get("runtime_root")
        or bundle.get("runtime_root")
        or (bundle.get("runtime_root_policy", {}) if isinstance(bundle.get("runtime_root_policy", {}), dict) else {}).get(
            "canonical_runtime_root"
        )
        or str(STATUS_DIR.parent)
    )
    module_list = safety_dry.get("modules", [])
    if not isinstance(module_list, list):
        module_list = []

    warnings: list[str] = []
    if not dryrun_path.exists():
        warnings.append("dry-run 状态文件缺失")
    if not bundle_path.exists():
        warnings.append("bundle 文件缺失")
    if not no_api:
        warnings.append("no_api 标记异常")
    if not no_push:
        warnings.append("no_push 标记异常")
    if not no_strategy_recompute:
        warnings.append("no_strategy_recompute 标记异常")
    if not no_cron:
        warnings.append("no_cron 标记异常")
    if production_verified:
        warnings.append("production_verified 不应为 true")

    if dryrun_path.exists() and bundle_path.exists() and not warnings:
        status = "PASS"
        status_label = "dry-run 已完成"
    elif dryrun_path.exists() or bundle_path.exists():
        status = "WARN"
        status_label = "部分存在"
    else:
        status = "MISSING"
        status_label = "缺失"

    return {
        "status": status,
        "status_label": status_label,
        "phase": safety_dry.get("phase", "Phase_C_Framework_DryRun"),
        "module": safety_dry.get("module", "all"),
        "modules": module_list,
        "generated_at": safety_dry.get("generated_at") or bundle.get("generated_at"),
        "bundle_date": bundle.get("date"),
        "dryrun_path": dryrun_path,
        "bundle_path": bundle_path,
        "check_path": check_path,
        "dryrun_found": dryrun_path.exists(),
        "bundle_found": bundle_path.exists(),
        "check_found": check_path.exists(),
        "no_api": no_api,
        "no_push": no_push,
        "no_strategy_recompute": no_strategy_recompute,
        "no_cron": no_cron,
        "production_dependency": False,
        "production_verified": production_verified,
        "runtime_root": runtime_root,
        "warnings": warnings,
        "check_status": str((check.get("status", "MISSING") if isinstance(check, dict) else "MISSING")).upper(),
        "check_schema_valid": bool(check.get("schema_valid", False)) if isinstance(check, dict) else False,
        "check_integrity_valid": bool(check.get("integrity_valid", False)) if isinstance(check, dict) else False,
        "check_secret_safe": bool(check.get("secret_safe", False)) if isinstance(check, dict) else False,
        "check_warnings": check.get("warnings", []) if isinstance(check.get("warnings", []), list) else [],
        "check_errors": check.get("errors", []) if isinstance(check.get("errors", []), list) else [],
        "bundle_preview": {
            "module_keys": sorted(
                list((bundle.get("modules", {}) if isinstance(bundle.get("modules", {}), dict) else {}).keys())
            ),
            "path_mismatch_warning_count": len(bundle.get("path_mismatch_warnings", []) or []),
        },
    }


def _nav(date_key: str, active: str) -> str:
    tabs = [
        ("index.html", "总控台"),
        ("v2_today.html", "V2今日"),
        ("v4_scan.html", "V4扫描"),
        ("v4_review.html", "V4复盘"),
        ("system.html", "系统健康"),
    ]
    html_tabs = []
    for href, label in tabs:
        cls = "tab active" if href == active else "tab"
        html_tabs.append(f'<a class="{cls}" href="{href}">{label}</a>')
    return (
        "<header><div class='top'>"
        "<h1>足球量化总控台｜只读版</h1>"
        f"<div class='meta'>日期：{escape(date_key)} · 生成时间：{escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</div>"
        "</div>"
        f"<nav class='tabs'>{''.join(html_tabs)}</nav>"
        "</header>"
    )


def _shell(title: str, body: str, date_key: str, active_page: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="V2V4控制台">
  <meta name="theme-color" content="#0c1220">
  <title>{escape(title)}</title>
  <link rel="manifest" href="manifest.json">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  {_nav(date_key, active_page)}
  <main>{body}</main>
  <script>
    if ('serviceWorker' in navigator) {{
      navigator.serviceWorker.register('./service-worker.js').catch(() => {{}});
    }}
  </script>
</body>
</html>"""


def _kv_card(title: str, rows: list[tuple[str, str]]) -> str:
    out = [f"<section class='card'><h2>{escape(title)}</h2><div class='kv'>"]
    for k, v in rows:
        out.append(f"<div class='k'>{escape(k)}</div><div class='v'>{v}</div>")
    out.append("</div></section>")
    return "".join(out)


def _ul(items: list[str]) -> str:
    if not items:
        return "<div class='muted'>缺失</div>"
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def _render_index(
    date_key: str,
    v2: dict[str, Any],
    scan: dict[str, Any],
    review: dict[str, Any],
    system: dict[str, Any],
    api_cache: dict[str, Any],
    ledger: dict[str, Any] | None = None,
) -> str:
    ledger = ledger or {}
    ledger_present = bool(ledger)
    lv2 = ledger.get("v2", {}) if isinstance(ledger.get("v2", {}), dict) else {}
    lscan = ledger.get("v4_scan", {}) if isinstance(ledger.get("v4_scan", {}), dict) else {}
    lreview = ledger.get("v4_review", {}) if isinstance(ledger.get("v4_review", {}), dict) else {}
    lissues = ledger.get("issues", {}) if isinstance(ledger.get("issues", {}), dict) else {}
    lfinal = ledger.get("final_status", {}) if isinstance(ledger.get("final_status", {}), dict) else {}

    v4_win = scan["windows"]
    scan_total_ab = sum((w["a"] or 0) + (w["b"] or 0) for w in v4_win)
    running_windows = [w for w in v4_win if str(w.get("window_status", "")).upper() == "UNVERIFIED"]
    sys_chain = str(system.get("sys_summary", {}).get("chain_status", "MISSING"))
    issue_count = len(system.get("issues", {}).get("P0", [])) + len(system.get("issues", {}).get("P1", []))

    v2_status_val = _status_tag(lv2.get("status", v2["final_status"])) if ledger_present else _status_tag(v2["final_status"])
    v2_official_locked_val = int(lv2.get("official_bet_locked", v2["official_locked_count"])) if ledger_present else int(v2["official_locked_count"])
    v2_missed_val = int(lv2.get("missed_candidates", v2["missed_count"])) if ledger_present else int(v2["missed_count"])
    v2_settle_obj_val = int(lv2.get("settlement_objects", v2["settlement_required"])) if ledger_present else int(v2["settlement_required"])
    v2_push_val = "<b>1</b>" if bool(lv2.get("qq_recommendation_pushed")) else "<b>0</b>" if ledger_present else f"<b>{v2['production_recommendation']}</b>"

    scan_reading_val = _status_tag(lscan.get("reading_status", "MISSING")) if ledger_present else _status_tag(scan.get("reading_mode", {}).get("reading_status", "MISSING"))
    scan_guard_val = _status_tag(lscan.get("data_guard_status", "MISSING")) if ledger_present else _status_tag(scan.get("guard", {}).get("data_guard_status", "MISSING"))
    prod_windows = lscan.get("production_evidence_windows", []) if ledger_present else [w.get("task_key") for w in v4_win if w.get("production_evidence")]
    prod_windows_text = "、".join(prod_windows) if prod_windows else "无"
    scan_total_ab_val = scan_total_ab
    if ledger_present and isinstance(lscan.get("readable_summary", {}), dict):
        rs = lscan.get("readable_summary", {})
        scan_total_ab_val = int(rs.get("A", 0) or 0) + int(rs.get("B", 0) or 0)

    review_status_val = _status_tag(lreview.get("status", review.get("overall_status", "MISSING"))) if ledger_present else _status_tag(review.get("overall_status", "MISSING"))
    review_due_val = str(lreview.get("due_time", review.get("review_due_time", "缺失"))) if ledger_present else str(review.get("review_due_time", "缺失"))
    review_nine_step = str(lreview.get("nine_step", "缺失")) if ledger_present else str(review.get("nine_step_display", "缺失"))

    if ledger_present:
        issue_count = len(lissues.get("p0", [])) + len(lissues.get("p1", []))
        sys_chain = str(lfinal.get("status", "CODE_READY"))

    api_runtime_root = str(api_cache.get("runtime_root", "缺失"))
    api_runtime_root_view = "项目内 data/runtime" if api_runtime_root.startswith(str(BASE_DIR / "data" / "runtime")) else api_runtime_root
    api_cache_status_view = f"{escape(str(api_cache.get('status_label', '缺失')))} · {_status_tag(api_cache.get('status'))}"

    cards = []
    cards.append(
        _kv_card(
            "1) V2 今日状态",
            [
                ("状态", v2_status_val),
                ("正式锁定", f"<b>{v2_official_locked_val}</b>"),
                ("错过锁定候选", f"<b>{v2_missed_val}</b>"),
                ("每日建池", _status_tag(v2["daily_pool_task"].get("status", "MISSING"))),
                ("QQ推荐推送", v2_push_val),
                ("状态回执", _status_tag(v2["pushed_status"])),
                ("正式结算对象", f"<b>{v2_settle_obj_val}</b>"),
            ],
        )
    )
    cards.append(
        _kv_card(
            "2) V4 扫描状态",
            [
                ("扫描窗口", f"{len(v4_win)} 个"),
                ("A+B 总数", f"<b>{scan_total_ab_val}</b>"),
                ("运行中窗口", f"<b>{len(running_windows)}</b>"),
                ("阅读状态", scan_reading_val),
                ("数据守卫", scan_guard_val),
                ("生产证据窗口", escape(prod_windows_text)),
                ("赛前剧本归档", _status_tag("PASS" if any(str(w["script_archive_status"]).upper() == "DONE" for w in v4_win) else ("HISTORICAL_NOT_ARCHIVED" if date_key == "20260517" else "MISSING"))),
                ("时段分布归档", _status_tag("PASS" if any(str(w["distribution_archive_status"]).upper() == "DONE" for w in v4_win) else ("HISTORICAL_NOT_ARCHIVED" if date_key == "20260517" else "MISSING"))),
            ],
        )
    )
    cards.append(
        _kv_card(
            "3) V4 复盘状态",
            [
                ("总体状态", review_status_val),
                ("计划触发", escape(review_due_val)),
                ("九步链状态", _status_tag(review_nine_step)),
                ("赛果刷新", _status_tag("PASS" if review["result_refresh_cache"] else ("WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
                ("QQ守卫", _status_tag(review["guard_qq"].get("guard_status", "WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
                ("路由标记", _status_tag("PASS" if review["route"] else ("WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
                ("发送标记", _status_tag(review["sent"].get("status", "WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
            ],
        )
    )
    cards.append(
        _kv_card(
            "4) 系统健康",
            [
                ("链路状态", _status_tag(sys_chain)),
                ("P0/P1 问题数", f"<b>{issue_count}</b>"),
                ("定时器文件态", _status_tag(system["jobs_anomaly"])),
                ("状态文件", _status_tag("PASS" if system["state_current_exists"] else "MISSING")),
                ("本地与main同步", _status_tag("P2_DASHBOARD_LOCAL_ONLY_NOT_VERSIONED" if system["step1_local_only"] else "PASS")),
                ("Ledger源", _status_tag("PASS" if ledger_present else "MISSING")),
            ],
        )
    )
    cards.append(
        _kv_card(
            "5) API Snapshot / Cache",
            [
                ("状态", api_cache_status_view),
                ("模式", "只读 dry-run"),
                ("是否调用API", _status_tag("NO" if api_cache.get("no_api") else "FAIL")),
                ("是否接入生产链路", _status_tag("NO")),
                ("是否推QQ", _status_tag("NO" if api_cache.get("no_push") else "FAIL")),
                ("是否接入cron", _status_tag("NO" if api_cache.get("no_cron") else "FAIL")),
                ("是否PRODUCTION_VERIFIED", _status_tag("NO" if not api_cache.get("production_verified") else "FAIL")),
                ("bundle", _status_tag("PASS" if api_cache.get("bundle_found") else "MISSING")),
                ("schema校验", _status_tag("PASS" if api_cache.get("check_schema_valid") else ("MISSING" if not api_cache.get("check_found") else "FAIL"))),
                ("integrity校验", _status_tag("PASS" if api_cache.get("check_integrity_valid") else ("MISSING" if not api_cache.get("check_found") else "FAIL"))),
                ("secret检查", _status_tag("PASS" if api_cache.get("check_secret_safe") else ("MISSING" if not api_cache.get("check_found") else "FAIL"))),
                ("runtime root", escape(api_runtime_root_view)),
                ("下一步", "待 BOSS 确认后进入 Phase C.2"),
            ],
        )
    )
    cards.append(
        _kv_card(
            "6) 明日/下一轮验证",
            [
                ("V2", "13:15 / 13:18 / 05/35"),
                ("V4 扫描", "凌晨 / 早场 / 午间 / 傍晚 / 晚间"),
                ("V4 复盘", "12:35"),
                ("下一步", "仅建议，未接入 cron"),
            ],
        )
    )

    details = [
        "<section class='card'><h2>运行提示</h2>"
        "<ul>"
        "<li>本页面只读，不触发任务，不调用外部 API，不推送 QQ。</li>"
        "<li>当状态文件缺失时，统一显示“缺失”，不做假通过。</li>"
        "<li>详细数据请进入各子页查看。</li>"
        f"<li>Ledger源：{'present' if ledger_present else 'missing'}（首页优先读取 ledger）。</li>"
        "</ul></section>"
        "<section class='card'><h2>API Cache 证据（折叠）</h2>"
        "<details><summary>查看证据</summary>"
        "<div class='kv'>"
        f"<div class='k'>status marker</div><div class='v'><span class='mono'>{escape(str(api_cache.get('dryrun_path')))}</span></div>"
        f"<div class='k'>bundle</div><div class='v'><span class='mono'>{escape(str(api_cache.get('bundle_path')))}</span></div>"
        f"<div class='k'>checker marker</div><div class='v'><span class='mono'>{escape(str(api_cache.get('check_path')))}</span></div>"
        f"<div class='k'>checker状态</div><div class='v'>{_status_tag(api_cache.get('check_status'))}</div>"
        f"<div class='k'>module</div><div class='v'>{escape(str(api_cache.get('module', 'all')))}</div>"
        f"<div class='k'>modules</div><div class='v'>{escape(', '.join(api_cache.get('modules', [])) or '缺失')}</div>"
        f"<div class='k'>生成时间</div><div class='v'>{escape(str(api_cache.get('generated_at') or '缺失'))}</div>"
        f"<div class='k'>warnings</div><div class='v'>{escape('；'.join(api_cache.get('warnings', [])) if api_cache.get('warnings') else '无')}</div>"
        f"<div class='k'>checker warnings</div><div class='v'>{escape('；'.join(api_cache.get('check_warnings', [])) if api_cache.get('check_warnings') else '无')}</div>"
        f"<div class='k'>checker errors</div><div class='v'>{escape('；'.join(api_cache.get('check_errors', [])) if api_cache.get('check_errors') else '无')}</div>"
        "</div></details></section>"
    ]

    body = f"<div class='grid'>{''.join(cards)}</div>{''.join(details)}"
    body += (
        "<section class='card'><h2>数据来源说明</h2>"
        "<ul>"
        "<li>V2卡片：V2状态回执 / 错过候选审计 / 正式锁定marker（首页优先ledger）</li>"
        "<li>V4扫描卡片：V4扫描结构化产物 / push marker / 日志</li>"
        "<li>V4复盘卡片：validation / attribution / renderer / guard / route/sent marker</li>"
        "<li>系统健康卡片：STATE_CURRENT / cron状态 / watchdog / audit / ledger</li>"
        "</ul></section>"
    )
    return _shell("足球量化总控台", body, date_key, "index.html")


def _render_v2(date_key: str, v2: dict[str, Any]) -> str:
    locked_items = [
        f"#{x['fixture_id']} | {x.get('locked_stage') or '-'} | @{x.get('locked_odds_D') or '-'} | {_odds_status_zh(x.get('final_odds_status'))}"
        for x in v2["locked"][:40]
    ]
    missed_items = [
        f"#{x['fixture_id']} | {x.get('last_seen_stage') or '-'} | @{x.get('last_seen_odds_D') or '-'} | {_odds_status_zh(x.get('final_odds_status'))}"
        for x in v2["missed"][:60]
    ]
    body = "".join(
        [
            _kv_card(
                "V2 今日总览",
                [
                    ("状态", _status_tag(v2["final_status"])),
                    ("正式锁定", f"<b>{v2['official_locked_count']}</b>"),
                    ("错过候选", f"<b>{v2['missed_count']}</b>"),
                    ("每日建池", _status_tag(v2["daily_pool_task"].get("status", "MISSING"))),
                    ("QQ推荐推送", f"<b>{v2['production_recommendation']}</b>"),
                    ("状态回执", _status_tag(v2["pushed_status"])),
                    ("结算", _status_tag(v2["settlement_status"])),
                    ("正式结算对象", f"<b>{v2['settlement_required']}</b>"),
                    ("状态文件", _status_tag("PASS" if v2["refs"]["daily_status_push"].exists else "MISSING")),
                ],
            ),
            "<section class='card'><h2>正式锁定清单</h2>"
            + (_ul(locked_items) if locked_items else "<div class='muted'>缺失 / 今日无正式锁定</div>")
            + "</section>",
            "<section class='card'><h2>错过锁定候选清单</h2>"
            + (_ul(missed_items) if missed_items else "<div class='muted'>缺失 / 今日无错过候选</div>")
            + "</section>",
            "<section class='card'><h2>数据来源</h2><ul>"
            + "".join(
                f"<li>{escape(ref.label)}: { _status_tag('PASS' if ref.exists else 'MISSING')}<br><span class='muted'>{escape(ref.rel)}</span></li>"
                for ref in v2["refs"].values()
            )
            + "</ul></section>",
            "<section class='card'><h2>数据来源说明</h2><div class='muted'>数据来源：V2状态回执 / 错过候选审计 / 正式锁定marker</div></section>",
        ]
    )
    return _shell("V2 今日状态", body, date_key, "v2_today.html")


def _render_scan(date_key: str, scan: dict[str, Any]) -> str:
    def reason_zh(code: str) -> str:
        mapping = {
            "evening_counts_missing": "A/B/C/SKIP计数缺失",
            "night_counts_missing": "A/B/C/SKIP计数缺失",
            "evening_counts_parse_failed": "A/B/C/SKIP解析失败",
            "night_counts_parse_failed": "A/B/C/SKIP解析失败",
            "late_counts_parse_failed": "凌晨计数来源不可靠",
            "evening_source_path_missing": "缺少可用数据源",
            "night_source_path_missing": "缺少可用数据源",
            "evening_status_parse_failed": "扫描状态解析失败",
            "night_status_parse_failed": "扫描状态解析失败",
            "late_fallback_scope_unverified": "回退源窗口专属性未验证",
            "early_uses_fallback_latest": "使用latest回退源",
            "early_non_window_specific_counts_source": "计数不是窗口专属来源",
            "early_marker_missing_but_log_present": "专属marker不完整，但日志存在",
            "counts_parse_failed": "A/B/C/SKIP解析失败",
            "status_parse_failed": "扫描状态解析失败",
            "source_path_missing": "缺少可用数据源",
            "counts_missing": "A/B/C/SKIP计数缺失",
            "fallback_scope_unverified": "回退源窗口专属性未验证",
            "uses_fallback_latest": "使用latest回退源",
            "non_window_specific_counts_source": "计数不是窗口专属来源",
            "marker_missing_but_log_present": "专属marker不完整，但日志存在",
            "task_date_mismatch": "任务日期不匹配（仅供参考）",
        }
        return mapping.get(code, code)

    def uniq_zh(codes: list[str], limit: int = 4) -> list[str]:
        out: list[str] = []
        for c in codes:
            z = reason_zh(c)
            if z not in out:
                out.append(z)
            if len(out) >= limit:
                break
        return out

    def summary_status_text(w: dict[str, Any]) -> tuple[str, str]:
        st = str(w.get("checklist_status", "FAIL")).upper()
        if st == "PASS":
            return "完整", "完整"
        if st == "WARN":
            return "回退展示", "回退展示"
        if str(w.get("window_status", "")).upper() in {"UNVERIFIED", "NOT_DUE"}:
            return "待验证", "待验证"
        return "失败", "失败"

    def window_one_liner(w: dict[str, Any]) -> str:
        name = str(w.get("task_key", ""))
        if name == "midday":
            return "窗口专属 push marker 完整。"
        if name == "early":
            return "使用latest回退，不是窗口专属证据。"
        if name == "late":
            return "QQ简报回退，窗口专属性未验证。"
        if name in {"evening", "night"}:
            return "扫描完成，但未找到可解析的A/B/C/SKIP来源。"
        zh = uniq_zh(w.get("checklist_reasons", []), limit=1)
        return zh[0] if zh else "状态待核验。"

    guard = scan.get("guard", {})
    guard_path = scan.get("guard_path")
    reading_mode = scan.get("reading_mode", {}) if isinstance(scan.get("reading_mode"), dict) else {}
    qq_brief = reading_mode.get("qq_brief", {}) if isinstance(reading_mode.get("qq_brief"), dict) else {}
    readable_sources = reading_mode.get("readable_sources", []) if isinstance(reading_mode.get("readable_sources"), list) else []
    reading_status = str(reading_mode.get("reading_status", "FAIL")).upper()
    window_results = guard.get("window_results", {}) if isinstance(guard, dict) else {}

    summary_cards: list[str] = []
    prod_windows: list[str] = []
    fallback_windows: list[str] = []
    fail_windows: list[str] = []
    for w in scan["windows"]:
        task = w["task"] if isinstance(w["task"], dict) else {}
        key = str(w.get("task_key"))
        r = window_results.get(key, {}) if isinstance(window_results, dict) else {}
        checklist_status = str(r.get("checklist_status") or w.get("checklist_status") or "FAIL").upper()
        prod_evidence = bool(r.get("production_evidence", w.get("production_evidence")))
        reasons_raw = r.get("reasons") or w.get("checklist_reasons") or []
        reasons_zh = uniq_zh([str(x) for x in reasons_raw], limit=3)

        status_text, status_badge = summary_status_text({"checklist_status": checklist_status, "window_status": w.get("window_status")})
        if status_text == "回退展示":
            fallback_windows.append(w["window"])
        if status_text == "失败":
            fail_windows.append(w["window"])
        if prod_evidence:
            prod_windows.append(w["window"])

        counts_text = "无法解析"
        counts_label = "A/B/C/SKIP"
        counts_extra = ""
        reading_state = "无可读内容"
        if all(v is not None for v in (w.get("a"), w.get("b"), w.get("c"), w.get("skip"))):
            counts_text = f"{w['a']}/{w['b']}/{w['c']}/{w['skip']}"
            reading_state = "有内容"
        if str(w.get("window_status", "")).upper() == "PARSE_FAILED":
            counts_text = "无法解析"

        # 展示语义修正：fallback来源计数只能作为参考，不作为正式窗口计数
        if str(w.get("source_type", "")).lower() in {"fallback_qq_brief", "fallback_latest_push"}:
            counts_label = "正式窗口计数"
            counts_text = "不可确认"
            reading_state = "回退参考"
            if all(v is not None for v in (w.get("a"), w.get("b"), w.get("c"), w.get("skip"))):
                counts_extra = f"回退参考计数：{w['a']}/{w['b']}/{w['c']}/{w['skip']}"

        fallback_path = w.get("source_path") if w.get("fallback_used") else None
        reason_line = window_one_liner(w)
        if reasons_zh and reason_line.endswith("。") and reason_line not in reasons_zh:
            # keep one-line concise; extra reasons in evidence
            pass

        pill_cls = "ok" if status_badge == "完整" else ("warn" if status_badge == "回退展示" else ("pending" if status_badge == "待验证" else "fail"))
        card_parts = [
            "<section class='card scan-summary-card'>",
            f"<h2>{escape(str(w['window']))}</h2>",
            f"<div class='scan-badges'><span class='scan-pill scan-{pill_cls}'>{escape(status_badge)}</span></div>",
            "<div class='kv'>",
            f"<div class='k'>{escape(counts_label)}</div>",
            f"<div class='v'><b>{escape(counts_text)}</b></div>",
        ]
        if counts_extra:
            card_parts.append(f"<div class='k'>回退参考</div><div class='v'>{escape(counts_extra)}</div>")
        card_parts.extend(
            [
                "<div class='k'>生产证据</div>",
                f"<div class='v'>{'是' if prod_evidence else '否'}</div>",
                "<div class='k'>原因</div>",
                f"<div class='v'>{escape(reason_line)}</div>",
            ]
        )
        if counts_extra:
            if str(w.get("source_type", "")).lower() == "fallback_qq_brief":
                card_parts.append("<div class='k'>说明</div><div class='v'>该计数来自QQ简报回退，不可作为窗口生产证据。</div>")
            elif str(w.get("source_type", "")).lower() == "fallback_latest_push":
                card_parts.append("<div class='k'>说明</div><div class='v'>该计数来自latest回退，不可作为窗口生产证据。</div>")
        ro = w.get("read_only_parse") if isinstance(w.get("read_only_parse"), dict) else {}
        show_ro = str(w.get("task_key")) in {"evening", "night"} and bool(ro.get("available"))
        if show_ro:
            ro_scan = ro.get("scan_total")
            ro_scout = ro.get("scout_total")
            ro_complete = "是" if ro.get("complete") else "否"
            ro_exit = "0" if ro.get("exit_code") == 0 else "未知"
            ro_parts = []
            if ro_scan is not None:
                ro_parts.append(f"总扫描：{ro_scan}")
            if ro_scout is not None:
                ro_parts.append(f"球探报告：{ro_scout}")
            ro_parts.append(f"完成状态：{ro_complete}")
            ro_parts.append(f"exit_code：{ro_exit}")
            card_parts.append("<div class='k'>只读补解析</div><div class='v'>" + "｜".join(ro_parts) + "</div>")
            card_parts.append("<div class='k'>补解析说明</div><div class='v'>仅从日志与状态文件补解析，不代表窗口专属A/B/C/SKIP。</div>")
            reading_state = "有内容（补解析）"
        card_parts.extend(
            [
                "<div class='k'>阅读状态</div>",
                f"<div class='v'>{escape(reading_state)}</div>",
                "</div>",
                "<details class='reading-evidence'>",
                "<summary>查看情报内容</summary>",
                "<div class='evidence-block'>",
                "<div class='kv'>",
                "<div class='k'>阅读层来源</div>",
                f"<div class='v'>{escape(_text_or_missing(w.get('source_type')))}</div>",
                "<div class='k'>阅读层说明</div>",
                f"<div class='v'>{escape(reason_line)}</div>",
                "<div class='k'>内容口径</div>",
                "<div class='v'>仅供阅读，不作生产证据</div>",
                "</div>",
                "</div>",
                "</details>",
                "<details class='evidence'>",
                "<summary>查看证据</summary>",
                "<div class='evidence-block'>",
                "<div class='kv'>",
                "<div class='k'>窗口清单检查</div>",
                f"<div class='v'>{_status_tag(checklist_status)}</div>",
                "<div class='k'>扫描状态</div>",
                f"<div class='v'>{_status_tag(w.get('window_status', 'MISSING'))}</div>",
                "<div class='k'>一句话说明</div>",
                f"<div class='v'>{escape(_text_or_missing(w.get('window_status_reason')))}</div>",
                "<div class='k'>cron ID</div>",
                f"<div class='v'>{escape(str(w.get('cron_id') or '缺失'))}</div>",
                "<div class='k'>计划时间</div>",
                f"<div class='v'>{escape(str(w.get('planned_time') or '缺失'))}</div>",
                "<div class='k'>扫描时间</div>",
                f"<div class='v'>{escape(_text_or_missing(task.get('started_at')))}</div>",
                "<div class='k'>数据源类型</div>",
                f"<div class='v'>{escape(_text_or_missing(w.get('source_type')))}</div>",
                "<div class='k'>marker状态</div>",
                f"<div class='v'>{_status_tag('PASS' if str(w.get('marker_source') or '').strip() and str(w.get('marker_source')).strip() != '缺失' else 'MISSING')}</div>",
                "<div class='k'>日志状态</div>",
                f"<div class='v'>{_status_tag('PASS' if w.get('log_complete') else ('MISSING' if not w.get('log_source') else 'UNVERIFIED'))}</div>",
                "<div class='k'>Guard状态</div>",
                f"<div class='v'>{_status_tag(checklist_status)}</div>",
                "<div class='k'>聚合原因</div>",
                f"<div class='v'>{escape('、'.join(reasons_zh) if reasons_zh else '无')}</div>",
                "</div>",
                "<details class='raw-evidence'>",
                "<summary>查看原始证据</summary>",
                "<div class='mono'>",
                f"source_path: {escape(_text_or_missing(w.get('source_path')))}<br>",
                f"counts_source: {escape(_text_or_missing(w.get('counts_source')))}<br>",
                f"marker_source: {escape(_text_or_missing(w.get('marker_source')))}<br>",
                f"log_path: {escape(_text_or_missing(w.get('log_source')))}<br>",
                f"fallback_source_path: {escape(_text_or_missing(fallback_path))}<br>",
                f"fallback_reason: {escape(_text_or_missing(w.get('fallback_reason')))}<br>",
                f"raw_fail_items: {escape('、'.join([str(x) for x in reasons_raw]) if reasons_raw else '无')}",
                "</div>",
                "</details>",
                "</div>",
                "</details>",
                "</section>",
            ]
        )
        summary_cards.append("".join(card_parts))

    fail_items_zh = uniq_zh([str(x) for x in guard.get("fail_items", [])], limit=8)
    warn_items_zh = uniq_zh([str(x) for x in guard.get("warn_items", [])], limit=8)
    prod_windows_txt = "、".join(prod_windows) if prod_windows else "无"
    fallback_windows_txt = "、".join(fallback_windows) if fallback_windows else "无"
    fail_windows_txt = "、".join(fail_windows) if fail_windows else "无"

    summary_card = _kv_card(
        "V4扫描证据模式总览",
        [
            ("页面渲染", _status_tag(guard.get("render_status", "MISSING"))),
            ("数据完整性", _status_tag(guard.get("data_guard_status", "MISSING"))),
            ("可作生产证据窗口", f"{len(prod_windows)}/{len(scan['windows'])}"),
            ("生产证据窗口", escape(prod_windows_txt)),
            ("回退展示窗口", escape(fallback_windows_txt)),
            ("失败窗口", escape(fail_windows_txt)),
            ("结论", "本页可用于查看问题，但不能作为V4扫描生产通过依据。"),
        ],
    )

    source_name_map = {
        "window_push_marker": "窗口专属marker",
        "qq_brief": "QQ简报",
        "latest_push": "latest回退",
        "window_log": "日志补解析",
        "missing": "缺失",
    }
    readable_source_lines = []
    readable_source_paths = []
    for s in readable_sources:
        st = str(s.get("type", "unknown"))
        st_zh = source_name_map.get(st, st)
        p = str(s.get("path") or "缺失")
        pe = "是" if bool(s.get("production_evidence")) else "否"
        readable_source_lines.append(f"{st_zh}（生产证据：{pe}）")
        readable_source_paths.append(f"{st_zh}: {p}")

    brief_counts = qq_brief.get("counts", {}) if isinstance(qq_brief.get("counts"), dict) else {}
    brief_counts_text = "不可解析"
    if all(k in brief_counts for k in ("a", "b", "c", "skip")):
        brief_counts_text = f"{brief_counts['a']}/{brief_counts['b']}/{brief_counts['c']}/{brief_counts['skip']}"
    a_items = qq_brief.get("a_items", []) if isinstance(qq_brief.get("a_items"), list) else []
    b_items = qq_brief.get("b_items", []) if isinstance(qq_brief.get("b_items"), list) else []
    ab_matches = qq_brief.get("ab_matches", []) if isinstance(qq_brief.get("ab_matches"), list) else []
    c_summary = str(qq_brief.get("c_summary") or "缺失")
    skip_summary = str(qq_brief.get("skip_summary") or "缺失")
    c_representatives = qq_brief.get("c_representatives", []) if isinstance(qq_brief.get("c_representatives"), list) else []
    skip_reason_items = qq_brief.get("skip_reason_items", []) if isinstance(qq_brief.get("skip_reason_items"), list) else []

    def _kickoff_sort_key(m: dict[str, Any]) -> tuple:
        kf = str(m.get("kickoff", ""))
        mmdd, hhmm = ("99-99", "99:99")
        if " " in kf:
            mmdd, hhmm = kf.split(" ", 1)
        return (mmdd, hhmm, str(m.get("home", "")))

    def _render_match_li(m: dict[str, Any]) -> str:
        unmapped_tags = []
        if m.get("home_unmapped"):
            unmapped_tags.append("主队未映射")
        if m.get("away_unmapped"):
            unmapped_tags.append("客队未映射")
        if m.get("league_unmapped"):
            unmapped_tags.append("联赛未映射")
        unmapped_note = f"（{'/'.join(unmapped_tags)}）" if unmapped_tags else ""
        line1 = f"{m.get('home','未提供')} vs {m.get('away','未提供')}{unmapped_note}"
        line2 = f"{m.get('league','未提供')}｜{m.get('kickoff','未提供')}"
        line3 = f"HT评分 {m.get('ht_score','未提供')}｜HT率 {m.get('ht_rate','未提供')}｜场均球 {m.get('avg_goals','未提供')}"
        line4 = f"剧本：{m.get('script_type','未提供')}"
        line5 = f"时段：{m.get('time_bins','未提供')}"
        line6 = "来源：阅读简报｜生产证据：否"
        return "<li><div>" + escape(line1) + "</div><div class='muted'>" + escape(line2) + "</div><div class='muted'>" + escape(line3) + "</div><div class='muted'>" + escape(line4) + "</div><div class='muted'>" + escape(line5) + "</div><div class='muted'>" + escape(line6) + "</div></li>"

    def _render_grouped_matches(matches: list[dict[str, Any]]) -> str:
        if not matches:
            return "<div class='muted'>缺失</div>"
        order = ["00:00-06:00", "06:00-12:00", "12:00-18:00", "18:00-24:00", "跨日/其他"]
        group_map: dict[str, list[dict[str, Any]]] = {k: [] for k in order}
        for m in sorted(matches, key=_kickoff_sort_key):
            g = str(m.get("time_group") or "跨日/其他")
            if g not in group_map:
                group_map[g] = []
            group_map[g].append(m)
        parts = []
        for g in order:
            rows = group_map.get(g, [])
            if not rows:
                continue
            parts.append(f"<div class='muted'>{escape(g)}（{len(rows)}场）</div>")
            parts.append("<ul>" + "".join(_render_match_li(x) for x in rows) + "</ul>")
        return "".join(parts) if parts else "<div class='muted'>缺失</div>"

    a_matches = [m for m in ab_matches if str(m.get("grade")) == "A"]
    b_matches = [m for m in ab_matches if str(m.get("grade")) == "B"]
    a_top_matches = sorted(a_matches, key=_kickoff_sort_key)[:10]
    b_top_matches = sorted(b_matches, key=_kickoff_sort_key)[:10]
    a_more = max(0, len(a_matches) - len(a_top_matches))
    b_more = max(0, len(b_matches) - len(b_top_matches))
    unmapped_names = []
    for m in ab_matches:
        if m.get("home_unmapped"):
            unmapped_names.append(str(m.get("home_raw") or m.get("home") or ""))
        if m.get("away_unmapped"):
            unmapped_names.append(str(m.get("away_raw") or m.get("away") or ""))
        if m.get("league_unmapped"):
            unmapped_names.append(str(m.get("league_raw") or m.get("league") or ""))
    unmapped_names = sorted({x for x in unmapped_names if x})

    def _norm_reading_name(raw: str, is_league: bool = False) -> str:
        name = (raw or "").strip()
        if not name:
            return name
        mapped = name
        if _v4_display_name is not None:
            mapped = _v4_display_name(name, is_league=is_league)
        if mapped == name and not is_league:
            mapped = READING_ALIAS.get(name, mapped)
        return mapped

    def _normalize_repr_item(s: str) -> str:
        txt = (s or "").strip()
        if not txt or " vs " not in txt:
            return txt
        left, right = txt.split(" vs ", 1)
        left_cn = _norm_reading_name(left, is_league=False)
        right_cn = _norm_reading_name(right, is_league=False)
        return f"{left_cn} vs {right_cn}"

    c_rep_norm = [_normalize_repr_item(x) for x in c_representatives]

    readable_brief_card = [
        "<section class='card'>",
        "<h2>V4扫描阅读模式</h2>",
        "<div class='muted'>本区用于阅读已有情报内容。若来自回退源，会标注“仅供阅读，不作生产证据”。</div>",
        "<div class='kv'>",
        "<div class='k'>阅读状态</div>",
        f"<div class='v'>{_status_tag(reading_status)}</div>",
        "<div class='k'>状态</div><div class='v'>可读</div>",
        "<div class='k'>来源</div>",
        f"<div class='v'>{escape(' / '.join(readable_source_lines) if readable_source_lines else '缺失')}</div>",
        "<div class='k'>生产证据</div><div class='v'>否（阅读层）</div>",
        "<div class='k'>数据完整性（证据层）</div>",
        f"<div class='v'>{_status_tag(guard.get('data_guard_status', 'MISSING'))}</div>",
        "<div class='k'>说明</div><div class='v'>本区用于阅读，不代表生产验证通过。</div>",
        "</div>",
        "<details class='raw-evidence'><summary>查看来源路径</summary><pre class='mono'>" + escape("\n".join(readable_source_paths) if readable_source_paths else "缺失") + "</pre></details>",
        "</section>",
        "<section class='card'>",
        "<h2>今日可读简报</h2>",
    ]
    if qq_brief.get("exists") and qq_brief.get("parse_ok"):
        readable_brief_card.extend(
            [
                "<div class='kv'>",
                "<div class='k'>来源类型</div><div class='v'>qq_brief（仅供阅读）</div>",
                "<div class='k'>扫描总数</div><div class='v'>" + escape(str(qq_brief.get("scan_total") or "缺失")) + "</div>",
                "<div class='k'>情报总数</div><div class='v'>" + escape(str(qq_brief.get("intel_total") or "缺失")) + "</div>",
                "<div class='k'>A/B/C/SKIP</div><div class='v'><b>" + escape(brief_counts_text) + "</b></div>",
                "<div class='k'>A+B覆盖</div><div class='v'>" + escape(str(qq_brief.get("ab_cover") or "缺失")) + "</div>",
                "<div class='k'>生成时间</div><div class='v'>" + escape(str(qq_brief.get("generated_time") or "未提供")) + "</div>",
                "<div class='k'>来源范围</div><div class='v'>全日回退简报</div>",
                "<div class='k'>生产证据</div><div class='v'>否</div>",
                "<div class='k'>数据完整性</div><div class='v'>失败（证据层）</div>",
                "<div class='k'>来源说明</div><div class='v'>该简报用于阅读，不代表凌晨窗口生产证据，也不代表生产验证通过。</div>",
                "</div>",
                "<h3>A/B重点（默认前10，按时间展示）</h3>",
                "<div class='muted'>A级前10</div>" + _render_grouped_matches(a_top_matches) + (f"<div class='muted'>其余 {a_more} 条已折叠</div>" if a_more > 0 else ""),
                ("<details><summary>展开全部A级" + str(len(a_matches)) + "场</summary>" + _render_grouped_matches(a_matches) + "</details>") if a_matches else "<div class='muted'>A级缺失</div>",
                "<div class='muted'>B级前10</div>" + _render_grouped_matches(b_top_matches) + (f"<div class='muted'>其余 {b_more} 条已折叠</div>" if b_more > 0 else ""),
                ("<details><summary>展开全部B级" + str(len(b_matches)) + "场</summary>" + _render_grouped_matches(b_matches) + "</details>") if b_matches else "<div class='muted'>B级缺失</div>",
                "<h3>C/SKIP摘要</h3>",
                f"<div class='muted'>C级总数：{escape(str(brief_counts.get('c') if isinstance(brief_counts, dict) and 'c' in brief_counts else '未提供'))}</div>",
                ("<div class='muted'>C级代表前5：" + escape(" | ".join(c_rep_norm[:5]) if c_rep_norm else "未提供") + "</div>"),
                f"<div class='muted'>SKIP总数：{escape(str(brief_counts.get('skip') if isinstance(brief_counts, dict) and 'skip' in brief_counts else '未提供'))}</div>",
                ("<ul>" + "".join(f"<li>{escape(str(x.get('reason','未提供')))}：{escape(str(x.get('count','未提供')))}场</li>" for x in skip_reason_items[:5]) + "</ul>" if skip_reason_items else "<div class='muted'>跳过原因Top5：未提供</div>"),
                "<details><summary>查看原文摘要</summary>"
                + f"<div class='muted'>{escape(c_summary)}</div>"
                + f"<div class='muted'>{escape(skip_summary)}</div>"
                + "</details>",
                ("<div class='muted'>未映射名称：" + escape("、".join(unmapped_names[:20])) + (" …" if len(unmapped_names) > 20 else "") + "</div>" if unmapped_names else "<div class='muted'>未映射名称：无</div>"),
                "<details class='raw-evidence'><summary>查看原文（折叠）</summary><pre class='mono'>"
                + escape(str(qq_brief.get("raw_excerpt") or "缺失"))
                + "</pre></details>",
                "<div class='muted'>来源声明：本卡片来自可读简报，仅用于阅读，不作为生产证据。</div>",
            ]
        )
    else:
        readable_brief_card.extend(
            [
                "<div class='kv'>",
                "<div class='k'>今日可读简报</div><div class='v'>无法解析</div>",
                "<div class='k'>原因</div><div class='v'>简报文件缺失或结构不完整</div>",
                "</div>",
                "<details class='raw-evidence'><summary>查看原文（折叠）</summary><pre class='mono'>"
                + escape(str(qq_brief.get("raw_excerpt") or "缺失"))
                + "</pre></details>",
            ]
        )
    readable_brief_card.append("</section>")

    guard_card = (
        "<section class='card'>"
        "<h2>V4扫描证据模式 Guard</h2>"
        "<div class='kv'>"
        f"<div class='k'>Guard状态</div><div class='v'>{_status_tag(guard.get('guard_status', 'MISSING'))}</div>"
        f"<div class='k'>渲染状态</div><div class='v'>{_status_tag(guard.get('render_status', 'MISSING'))}</div>"
        f"<div class='k'>数据守卫状态</div><div class='v'>{_status_tag(guard.get('data_guard_status', 'MISSING'))}</div>"
        f"<div class='k'>检查窗口</div><div class='v'>{escape(','.join(guard.get('checked_windows', [])) or '缺失')}</div>"
        f"<div class='k'>失败原因（聚合）</div><div class='v'>{escape('、'.join(fail_items_zh) if fail_items_zh else '无')}</div>"
        f"<div class='k'>警告原因（聚合）</div><div class='v'>{escape('、'.join(warn_items_zh) if warn_items_zh else '无')}</div>"
        f"<div class='k'>生产验证标记</div><div class='v'>{_status_tag('FORBIDDEN_THIS_PHASE')}</div>"
        "</div>"
        "<details class='raw-evidence'>"
        "<summary>查看原始证据</summary>"
        "<div class='mono'>"
        f"guard_file: {escape(str(guard_path) if guard_path else '缺失')}<br>"
        f"fail_items_raw: {escape('、'.join([str(x) for x in guard.get('fail_items', [])]) or '无')}<br>"
        f"warn_items_raw: {escape('、'.join([str(x) for x in guard.get('warn_items', [])]) or '无')}"
        "</div>"
        "</details>"
        "</section>"
    )

    body = "".join(readable_brief_card)
    body += summary_card
    body += "<div class='grid scan-grid'>" + "".join(summary_cards) + "</div>"
    body += guard_card
    body += "<section class='card'><h2>数据来源说明</h2><div class='muted'>阅读模式：window_push_marker / qq_brief / latest_push / log_parse。证据模式：V4扫描结构化产物 / push marker / 日志（技术证据折叠）。</div></section>"
    return _shell("V4 扫描窗口", body, date_key, "v4_scan.html")


def _render_review(date_key: str, review: dict[str, Any]) -> str:
    step_cards = []
    for step in review["steps"]:
        step_cards.append(
            "<li>"
            f"<b>{escape(step['name'])}</b> { _status_tag(step['status']) }"
            f"<details><summary>查看目标文件路径</summary><span class='muted'>{escape(str(step['path']))}</span></details>"
            "</li>"
        )
    ab_a = review.get("ab_hit", {}).get("A", {})
    ab_b = review.get("ab_hit", {}).get("B", {})
    latest = review.get("latest_completed")
    latest_card = ""
    if latest:
        latest_card = _kv_card(
            "最近已完成复盘（参考）",
            [
                ("最近日期", escape(str(latest.get("date") or "缺失"))),
                ("QQ守卫", _status_tag(latest.get("guard_status", "MISSING"))),
                ("路由允许推送", _status_tag("PASS" if latest.get("allowed_to_push") else "MISSING")),
                ("发送状态", _status_tag(latest.get("sent_status", "MISSING"))),
                ("说明", "仅参考，不替代当前复盘日期"),
            ],
        )
    body = "".join(
        [
            _kv_card(
                "V4复盘状态",
                [
                    ("状态", _status_tag(review.get("overall_status", "MISSING"))),
                    ("复盘日期", escape(str(review.get("review_date", date_key)))),
                    ("计划触发", escape(str(review.get("review_due_time", "缺失")))),
                    ("当前时间", escape(str(review.get("current_time", "缺失")))),
                    ("当前阶段", escape(str(review.get("overall_reason", "缺失")))),
                    ("允许推送", _status_tag("PASS" if review["push_allowed"] else "NO")),
                    ("路由标记", _status_tag("PASS" if review["route"] else ("WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
                    ("发送标记", _status_tag(review["sent"].get("status", "WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
                    ("PRODUCTION_VERIFIED", _status_tag("FORBIDDEN_THIS_PHASE")),
                ],
            ),
            "<section class='card'><h2>步骤明细</h2><ol>" + "".join(step_cards) + "</ol></section>",
            latest_card,
            _kv_card(
                "复盘附加状态",
                [
                    ("赛果刷新", _status_tag("PASS" if review["result_refresh_cache"] else ("WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
                    ("剧本归档", _status_tag("PASS" if (DAILY_REPORT_DIR / f"v4_script_type_archive_{date_key}.json").exists() else ("HISTORICAL_NOT_ARCHIVED" if date_key == "20260517" else "MISSING"))),
                    ("A命中", escape(f"{ab_a.get('hit','-')}/{ab_a.get('total','-')}")),
                    ("B命中", escape(f"{ab_b.get('hit','-')}/{ab_b.get('total','-')}")),
                    ("数据缺失待核验", _status_tag("PASS" if (review["result_refresh_cache"] and int(review['result_refresh_cache'].get('still_missing', 0)) == 0) else ("WAITING_TRIGGER" if not review.get("due_reached") else "MISSING"))),
                    ("复盘Guard", _status_tag(review.get("review_guard", {}).get("guard_status", "MISSING"))),
                    ("Guard文件", escape(str(review.get("review_guard_path") or "缺失"))),
                ],
            ),
            "<section class='card'><h2>数据来源说明</h2><div class='muted'>数据来源：validation / attribution / renderer / guard / route/sent marker</div></section>",
        ]
    )
    return _shell("V4 复盘硬链", body, date_key, "v4_review.html")


def _render_system(date_key: str, system: dict[str, Any], api_cache: dict[str, Any]) -> str:
    cron_items = []
    for row in system["cron_rows"][:30]:
        cron_items.append(f"{row['task']} | {_status_zh(row['status'])} | {row['finished_at'] or '缺失'}")
    issue_sections = []
    for p in ("P0", "P1", "P2"):
        vals = system["issues"].get(p, [])
        fallback = '<div class="muted">缺失 / 无记录</div>'
        issue_sections.append(
            f"<section class='card'><h2>{_priority_tag(p)} 问题</h2>{_ul(vals) if vals else fallback}</section>"
        )
    body = "".join(
        [
            _kv_card(
                "系统健康总览",
                [
                    ("定时任务状态", _status_tag("PASS" if system["cron_rows"] else "MISSING")),
                    ("守护状态", _status_tag(system["sys_summary"].get("chain_status", "MISSING"))),
                    ("定时器文件态", _status_tag(system["jobs_anomaly"])),
                    ("状态文件", _status_tag("PASS" if system["state_current_exists"] else "MISSING")),
                    ("GitHub main 同步风险", _status_tag("P2_DASHBOARD_LOCAL_ONLY_NOT_VERSIONED" if system["step1_local_only"] else "PASS")),
                ],
            ),
            "<section class='card'><h2>Cron / Task 状态</h2>" + _status_tag("PASS" if system["cron_rows"] else "MISSING") + "<details><summary>展开任务列表</summary>" + _ul(cron_items) + "</details></section>",
            "".join(issue_sections),
            "<section class='card'><h2>今日已修复</h2>" + _ul(system["fixed"]) + "</section>",
            "<section class='card'><h2>明日待验证</h2>" + _ul(system["tomorrow"]) + "</section>",
            _kv_card(
                "API Snapshot / Cache",
                [
                    ("dry-run 状态", _status_tag(api_cache.get("status"))),
                    ("bundle 状态", _status_tag("PASS" if api_cache.get("bundle_found") else "MISSING")),
                    ("是否调用API", _status_tag("NO" if api_cache.get("no_api") else "FAIL")),
                    ("是否推QQ", _status_tag("NO" if api_cache.get("no_push") else "FAIL")),
                    ("是否重算策略", _status_tag("NO" if api_cache.get("no_strategy_recompute") else "FAIL")),
                    ("是否接入cron", _status_tag("NO" if api_cache.get("no_cron") else "FAIL")),
                    ("production_dependency", _status_tag("NO")),
                    ("是否PRODUCTION_VERIFIED", _status_tag("NO" if not api_cache.get("production_verified") else "FAIL")),
                    ("schema校验", _status_tag("PASS" if api_cache.get("check_schema_valid") else ("MISSING" if not api_cache.get("check_found") else "FAIL"))),
                    ("integrity校验", _status_tag("PASS" if api_cache.get("check_integrity_valid") else ("MISSING" if not api_cache.get("check_found") else "FAIL"))),
                    ("secret检查", _status_tag("PASS" if api_cache.get("check_secret_safe") else ("MISSING" if not api_cache.get("check_found") else "FAIL"))),
                ],
            ),
            "<section class='card'><h2>API Cache 证据（折叠）</h2>"
            "<details><summary>查看证据</summary>"
            "<div class='kv'>"
            f"<div class='k'>status marker</div><div class='v'><span class='mono'>{escape(str(api_cache.get('dryrun_path')))}</span></div>"
            f"<div class='k'>bundle</div><div class='v'><span class='mono'>{escape(str(api_cache.get('bundle_path')))}</span></div>"
            f"<div class='k'>runtime root</div><div class='v'><span class='mono'>{escape(str(api_cache.get('runtime_root', '缺失')))}</span></div>"
            f"<div class='k'>generated_at</div><div class='v'>{escape(str(api_cache.get('generated_at') or '缺失'))}</div>"
            f"<div class='k'>warnings</div><div class='v'>{escape('；'.join(api_cache.get('warnings', [])) if api_cache.get('warnings') else '无')}</div>"
            "</div></details></section>",
            "<section class='card'><h2>最近日志入口</h2><ul>"
            + "".join(f"<li>{escape(p.name)}<br><span class='muted'>{escape(str(p.relative_to(BASE_DIR)))}</span></li>" for p in system["logs"])
            + "</ul></section>",
            "<section class='card'><h2>数据来源说明</h2><div class='muted'>数据来源：STATE_CURRENT / cron状态 / watchdog / audit</div></section>",
        ]
    )
    return _shell("系统健康", body, date_key, "system.html")


def _write_assets() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    css = """*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC','Microsoft YaHei',sans-serif;background:#0c1220;color:#e8eefc}
header{position:sticky;top:0;z-index:10;padding:14px 14px 10px;background:rgba(12,18,32,.92);backdrop-filter:blur(8px);border-bottom:1px solid #1f2b45}
h1{font-size:18px;line-height:1.3;margin:0 0 6px}.meta{font-size:12px;color:#9eb0d8}
.tabs{display:flex;gap:8px;overflow:auto;padding-bottom:2px}.tab{display:inline-block;padding:8px 10px;border-radius:10px;background:#172239;color:#c6d4f2;text-decoration:none;white-space:nowrap;font-size:13px}
.tab.active{background:#285cff;color:#fff;font-weight:700}
main{padding:14px;display:grid;gap:12px}.grid{display:grid;gap:12px}
@media(min-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.card{background:#121c30;border:1px solid #1f2b45;border-radius:14px;padding:12px 12px 10px}
.card h2{margin:0 0 10px;font-size:15px;color:#f3f7ff}.kv{display:grid;grid-template-columns:120px 1fr;gap:8px 10px}
.card h3{margin:10px 0 6px;font-size:13px;color:#dbe6ff}
.k{font-size:12px;color:#93a6cc}.v{font-size:13px;line-height:1.35;word-break:break-word}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700}
.tag.ok{background:#123524;color:#59d58f}.tag.warn{background:#3f300f;color:#f3c969}.tag.bad{background:#481b25;color:#ff93a6}.tag.neutral{background:#223657;color:#96b8ff}
.muted{font-size:12px;color:#93a6cc}
ul,ol{margin:0;padding-left:18px}li{margin:6px 0;line-height:1.35}
details{margin-top:8px}summary{cursor:pointer;color:#aac1f3}
.scan-grid{grid-template-columns:1fr}
@media(min-width:900px){.scan-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.scan-summary-card h2{display:flex;align-items:center;justify-content:space-between}
.scan-badges{margin-bottom:8px}
.scan-pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}
.scan-pill.scan-ok{background:#123524;color:#59d58f}
.scan-pill.scan-warn{background:#3f300f;color:#f3c969}
.scan-pill.scan-fail{background:#481b25;color:#ff93a6}
.scan-pill.scan-pending{background:#223657;color:#96b8ff}
.evidence{margin-top:10px;border-top:1px dashed #2a395d;padding-top:8px}
.reading-evidence{margin-top:10px;border-top:1px dashed #2a395d;padding-top:8px}
.evidence-block{padding-top:6px}
.raw-evidence{margin-top:8px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,'Courier New',monospace;font-size:11px;line-height:1.45;word-break:break-all;color:#a9bddf}
pre.mono{white-space:pre-wrap;word-break:break-word;max-height:260px;overflow:auto;background:#0f1728;border:1px solid #1f2b45;border-radius:8px;padding:8px}
"""
    (ASSET_DIR / "style.css").write_text(css, encoding="utf-8")

    manifest = {
        "name": "V2/V4 Dashboard Phase 1",
        "short_name": "V2V4",
        "start_url": "./index.html",
        "display": "standalone",
        "background_color": "#0c1220",
        "theme_color": "#0c1220",
        "icons": [],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    sw = """const CACHE='v2v4-dashboard-phase1-v1';
const ASSETS=['./','./index.html','./v2_today.html','./v4_scan.html','./v4_review.html','./system.html','./assets/style.css','./manifest.json'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{const cp=res.clone();caches.open(CACHE).then(c=>c.put(e.request,cp)).catch(()=>{});return res;}).catch(()=>caches.match('./index.html'))));});
"""
    (OUT_DIR / "service-worker.js").write_text(sw, encoding="utf-8")


def generate(date_str: str) -> dict[str, Any]:
    date_key = _date_key(date_str)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_assets()

    step1_local_only = True
    for f in ("engine/v3_dashboard.py", "engine/v4_dashboard.py", "engine/v4_ops_dashboard.py"):
        if not Path(BASE_DIR / f).exists():
            step1_local_only = True
            break

    v2 = _compute_v2(date_key)
    scan = _compute_v4_scan(date_key)
    review = _compute_v4_review(date_key)
    system = _compute_system(date_key, step1_local_only=step1_local_only)
    api_cache = _compute_api_cache(date_key)
    ledger = _load_json(LEDGER_DIR / f"{date_key}.json", {})

    pages = {
        "index.html": _render_index(date_key, v2, scan, review, system, api_cache, ledger=ledger),
        "v2_today.html": _render_v2(date_key, v2),
        "v4_scan.html": _render_scan(date_key, scan),
        "v4_review.html": _render_review(date_key, review),
        "system.html": _render_system(date_key, system, api_cache),
    }
    for name, html in pages.items():
        (OUT_DIR / name).write_text(html, encoding="utf-8")

    outputs = {name: str((OUT_DIR / name).relative_to(BASE_DIR)) for name in pages}
    outputs["manifest.json"] = str((OUT_DIR / "manifest.json").relative_to(BASE_DIR))
    outputs["service-worker.js"] = str((OUT_DIR / "service-worker.js").relative_to(BASE_DIR))
    outputs["assets/style.css"] = str((ASSET_DIR / "style.css").relative_to(BASE_DIR))
    if scan.get("guard_path"):
        try:
            outputs["dashboard_v4_scan_guard.json"] = str(Path(scan["guard_path"]).relative_to(BASE_DIR))
        except Exception:
            outputs["dashboard_v4_scan_guard.json"] = str(scan["guard_path"])
    if review.get("review_guard_path"):
        try:
            outputs["dashboard_v4_review_guard.json"] = str(Path(review["review_guard_path"]).relative_to(BASE_DIR))
        except Exception:
            outputs["dashboard_v4_review_guard.json"] = str(review["review_guard_path"])

    # Phase C.1 dashboard status marker (runtime artifact, not for git commit)
    dashboard_api_cache_marker = {
        "status": "CODE_READY",
        "phase": "Phase_C_1_Dashboard_Status_Card",
        "api_cache_framework_visible": True,
        "dryrun_status_marker_found": bool(api_cache.get("dryrun_found")),
        "bundle_found": bool(api_cache.get("bundle_found")),
        "no_api": bool(api_cache.get("no_api")),
        "no_push": bool(api_cache.get("no_push")),
        "no_strategy_recompute": bool(api_cache.get("no_strategy_recompute")),
        "no_cron": bool(api_cache.get("no_cron")),
        "production_dependency": False,
        "production_verified": False,
        "dashboard_updated": True,
        "strategy_changed": False,
        "qq_pushed": False,
        "cron_enabled": False,
    }
    marker_path = STATUS_DIR / f"dashboard_api_cache_status_card_{date_key}.json"
    marker_path.write_text(json.dumps(dashboard_api_cache_marker, ensure_ascii=False, indent=2), encoding="utf-8")

    missing_flags = {
        "v2_daily_pool_summary_exists": v2["refs"]["daily_pool_summary"].exists,
        "v4_review_validation_exists": (DAILY_REPORT_DIR / f"v4_ht_recommend_validation_{date_key}.json").exists(),
        "v4_review_attribution_exists": (V4_ARCHIVE_DIR / f"v4_result_attribution_{date_key}.jsonl").exists(),
        "capture_audit_exists": (CAPTURE_AUDIT_DIR / f"v4_live_capture_audit_{date_key}.json").exists(),
    }

    return {
        "date": date_key,
        "generated_at": datetime.now().isoformat(),
        "outputs": outputs,
        "missing_flags": missing_flags,
        "safety": {
            "external_api_called": False,
            "qq_push_triggered": False,
            "task_triggered": False,
            "strategy_changed": False,
            "production_marker_written": False,
        },
        "v4_scan_guard": scan.get("guard", {}),
        "v4_review_guard": review.get("review_guard", {}),
        "api_cache": {
            "status": api_cache.get("status"),
            "dryrun_path": str(api_cache.get("dryrun_path")),
            "bundle_path": str(api_cache.get("bundle_path")),
            "marker_path": str(marker_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate read-only mobile dashboard (Phase 1)")
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    args = parser.parse_args()
    result = generate(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
