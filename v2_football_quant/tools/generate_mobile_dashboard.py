#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

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
OUT_DIR = BASE_DIR / "data" / "runtime" / "dashboard"
ASSET_DIR = OUT_DIR / "assets"
STATE_CURRENT = BASE_DIR.parent / "STATE_CURRENT.md"


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
    elif s in {"RUNNING", "PARTIAL_DONE", "REVIEW_PARTIAL", "DELIVERED_UNCONFIRMED", "SKIPPED_STARTED_OR_CLOSED"}:
        cls = "warn"
    elif s in {"FAIL", "FAILED", "TIMEOUT", "ABNORMAL", "BLOCKER", "CHAIN_INCOMPLETE", "MISSING"}:
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
    windows = [
        ("凌晨", "late"),
        ("早场", "early"),
        ("午间", "midday"),
        ("傍晚", "evening"),
        ("晚间", "night"),
    ]
    rows = []
    for label, key in windows:
        task_path = STATUS_DIR / f"task_status_v4_scan_{key}.json"
        task = _load_json(task_path, {})
        push_path = STATUS_DIR / f"v4_scan_push_{date_key}_{key}.json"
        push = _load_json(push_path, {})
        fallback_used = False
        if not push:
            if key == "midday":
                for cand in [
                    STATUS_DIR / f"v4_scan_push_{date_key}_midday_corrected_v2.json",
                    STATUS_DIR / f"v4_scan_push_{date_key}_midday_corrected.json",
                    STATUS_DIR / f"v4_scan_push_{date_key}_midday.json",
                ]:
                    if cand.exists():
                        push = _load_json(cand, {})
                        push_path = cand
                        fallback_used = True
                        break
            elif key == "early":
                cand = STATUS_DIR / f"v4_scan_push_{date_key}_latest.json"
                if cand.exists():
                    push = _load_json(cand, {})
                    push_path = cand
                    fallback_used = True

        a = int(push.get("a_count", 0) or 0)
        b = int(push.get("b_count", 0) or 0)
        c = int(push.get("c_count", 0) or 0)
        skip = int(push.get("skip_count", 0) or 0)
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

        scout_path = task.get("output_files", {}).get("scout")
        script_archive = False
        dist_archive = False
        if scout_path:
            # Phase 1: 只读存在性，若后续脚本归档文件出现再切换。
            script_archive = (DAILY_REPORT_DIR / f"v4_script_type_archive_{date_key}.json").exists()
            dist_archive = (DAILY_REPORT_DIR / f"v4_script_distribution_{date_key}.json").exists()

        rows.append(
            {
                "window": label,
                "task_key": key,
                "task_path": task_path,
                "task": task,
                "push_path": push_path,
                "push": push,
                "fallback_used": fallback_used,
                "grade": grade,
                "a": a,
                "b": b,
                "c": c,
                "skip": skip,
                "script_archive": script_archive,
                "distribution_archive": dist_archive,
            }
        )

    return {"windows": rows}


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

    def step(name: str, path: Path, extra_ok: bool = True) -> dict[str, Any]:
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
    push_allowed = bool(route.get("allowed_to_push")) and str(guard_qq.get("guard_status", "")).upper() == "PASS"
    pushed = str(sent.get("status", "")).upper() in {"SENT", "DELIVERED_UNCONFIRMED"}
    ab_hit = {
        "A": stats.get("A", {}),
        "B": stats.get("B", {}),
    } if isinstance(stats, dict) else {}

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


def _render_index(date_key: str, v2: dict[str, Any], scan: dict[str, Any], review: dict[str, Any], system: dict[str, Any]) -> str:
    v4_win = scan["windows"]
    scan_total_ab = sum(w["a"] + w["b"] for w in v4_win)
    running_windows = [w for w in v4_win if str(w["task"].get("status", "")).upper() == "RUNNING"]
    sys_chain = str(system.get("sys_summary", {}).get("chain_status", "MISSING"))
    issue_count = len(system.get("issues", {}).get("P0", [])) + len(system.get("issues", {}).get("P1", []))

    cards = []
    cards.append(
        _kv_card(
            "1) V2 今日状态",
            [
                ("状态", _status_tag(v2["final_status"])),
                ("正式锁定", f"<b>{v2['official_locked_count']}</b>"),
                ("错过锁定候选", f"<b>{v2['missed_count']}</b>"),
                ("每日建池", _status_tag(v2["daily_pool_task"].get("status", "MISSING"))),
                ("QQ推荐推送", f"<b>{v2['production_recommendation']}</b> · {_status_tag(v2['pushed_status'])}"),
                ("正式结算对象", f"<b>{v2['settlement_required']}</b>"),
            ],
        )
    )
    cards.append(
        _kv_card(
            "2) V4 扫描状态",
            [
                ("扫描窗口", f"{len(v4_win)} 个"),
                ("A+B 总数", f"<b>{scan_total_ab}</b>"),
                ("运行中窗口", f"<b>{len(running_windows)}</b>"),
                ("剧本归档", _status_tag("PASS" if any(w["script_archive"] for w in v4_win) else "MISSING")),
                ("时段分布归档", _status_tag("PASS" if any(w["distribution_archive"] for w in v4_win) else "MISSING")),
            ],
        )
    )
    cards.append(
        _kv_card(
            "3) V4 复盘状态",
            [
                ("9步硬链", _status_tag("PASS" if review["complete"] else "MISSING")),
                ("赛果刷新", _status_tag("PASS" if review["result_refresh_cache"] else "MISSING")),
                ("QQ守卫", _status_tag(review["guard_qq"].get("guard_status", "MISSING"))),
                ("路由标记", _status_tag("PASS" if review["route"] else "MISSING")),
                ("发送标记", _status_tag(review["sent"].get("status", "MISSING"))),
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
            ],
        )
    )
    cards.append(
        _kv_card(
            "5) 明日/下一轮验证",
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
        "</ul></section>"
    ]

    body = f"<div class='grid'>{''.join(cards)}</div>{''.join(details)}"
    body += (
        "<section class='card'><h2>数据来源说明</h2>"
        "<ul>"
        "<li>V2卡片：V2状态回执 / missed candidates审计 / 正式锁定marker</li>"
        "<li>V4扫描卡片：V4扫描结构化产物 / push marker / 日志</li>"
        "<li>V4复盘卡片：validation / attribution / renderer / guard / route/sent marker</li>"
        "<li>系统健康卡片：STATE_CURRENT / cron状态 / watchdog / audit</li>"
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
                    ("QQ推荐推送", f"<b>{v2['production_recommendation']}</b> · {_status_tag(v2['pushed_status'])}"),
                    ("结算", _status_tag(v2["settlement_status"])),
                    ("正式结算对象", f"<b>{v2['settlement_required']}</b>"),
                    ("状态回执", _status_tag("PASS" if v2["refs"]["daily_status_push"].exists else "MISSING")),
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
            "<section class='card'><h2>数据来源说明</h2><div class='muted'>数据来源：V2状态回执 / missed candidates审计 / 正式锁定marker</div></section>",
        ]
    )
    return _shell("V2 今日状态", body, date_key, "v2_today.html")


def _render_scan(date_key: str, scan: dict[str, Any]) -> str:
    items = []
    for w in scan["windows"]:
        task = w["task"] if isinstance(w["task"], dict) else {}
        push = w["push"] if isinstance(w["push"], dict) else {}
        cron_id = task.get("cron_id") or task.get("job_id") or "缺失"
        items.append(
            _kv_card(
                f"{w['window']} 扫描窗口",
                [
                    ("cron ID", escape(str(cron_id))),
                    ("扫描状态", _status_tag(task.get("status", "MISSING"))),
                    ("扫描时间", escape(_text_or_missing(task.get("started_at")))),
                    ("A/B/C/SKIP", f"{w['a']}/{w['b']}/{w['c']}/{w['skip']}"),
                    ("当前等级", _status_tag(w["grade"])),
                    ("QQ模板状态", _status_tag(push.get("status", "MISSING"))),
                    ("推送标记", _status_tag("PASS" if w["push_path"].exists() else "MISSING")),
                    ("日志路径", escape(_text_or_missing(task.get("output_files", {}).get("scan_log")))),
                    ("赛前剧本归档", _status_tag("PASS" if w["script_archive"] else "MISSING")),
                    ("时段分布归档", _status_tag("PASS" if w["distribution_archive"] else "MISSING")),
                    ("使用回退源", "是" if w["fallback_used"] else "否"),
                ],
            )
        )
    body = "<div class='grid'>" + "".join(items) + "</div>"
    body += "<section class='card'><h2>数据来源说明</h2><div class='muted'>数据来源：V4扫描结构化产物 / push marker / 日志</div></section>"
    return _shell("V4 扫描窗口", body, date_key, "v4_scan.html")


def _render_review(date_key: str, review: dict[str, Any]) -> str:
    step_cards = []
    for step in review["steps"]:
        step_cards.append(
            "<li>"
            f"<b>{escape(step['name'])}</b> { _status_tag(step['status']) }"
            f"<br><span class='muted'>{escape(str(step['path']))}</span>"
            "</li>"
        )
    ab_a = review.get("ab_hit", {}).get("A", {})
    ab_b = review.get("ab_hit", {}).get("B", {})
    body = "".join(
        [
            _kv_card(
                "V4 复盘 9步硬链",
                [
                    ("链路完成", _status_tag("PASS" if review["complete"] else "MISSING")),
                    ("允许推送", _status_tag("PASS" if review["push_allowed"] else "MISSING")),
                    ("路由标记", _status_tag("PASS" if review["route"] else "MISSING")),
                    ("发送标记", _status_tag(review["sent"].get("status", "MISSING"))),
                ],
            ),
            "<section class='card'><h2>步骤明细</h2><ol>" + "".join(step_cards) + "</ol></section>",
            _kv_card(
                "复盘附加状态",
                [
                    ("赛果刷新", _status_tag("PASS" if review["result_refresh_cache"] else "MISSING")),
                    ("剧本归档", _status_tag("PASS" if (DAILY_REPORT_DIR / f"v4_script_type_archive_{date_key}.json").exists() else "MISSING")),
                    ("A命中", escape(f"{ab_a.get('hit','-')}/{ab_a.get('total','-')}")),
                    ("B命中", escape(f"{ab_b.get('hit','-')}/{ab_b.get('total','-')}")),
                    ("数据缺失待核验", _status_tag("PASS" if not review["result_refresh_cache"] or int(review['result_refresh_cache'].get('still_missing', 0)) == 0 else "MISSING")),
                    ("生产验证标记", _status_tag("FORBIDDEN_THIS_PHASE")),
                ],
            ),
            "<section class='card'><h2>数据来源说明</h2><div class='muted'>数据来源：validation / attribution / renderer / guard / route/sent marker</div></section>",
        ]
    )
    return _shell("V4 复盘硬链", body, date_key, "v4_review.html")


def _render_system(date_key: str, system: dict[str, Any]) -> str:
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
.k{font-size:12px;color:#93a6cc}.v{font-size:13px;line-height:1.35;word-break:break-word}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700}
.tag.ok{background:#123524;color:#59d58f}.tag.warn{background:#3f300f;color:#f3c969}.tag.bad{background:#481b25;color:#ff93a6}.tag.neutral{background:#223657;color:#96b8ff}
.muted{font-size:12px;color:#93a6cc}
ul,ol{margin:0;padding-left:18px}li{margin:6px 0;line-height:1.35}
details{margin-top:8px}summary{cursor:pointer;color:#aac1f3}
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

    pages = {
        "index.html": _render_index(date_key, v2, scan, review, system),
        "v2_today.html": _render_v2(date_key, v2),
        "v4_scan.html": _render_scan(date_key, scan),
        "v4_review.html": _render_review(date_key, review),
        "system.html": _render_system(date_key, system),
    }
    for name, html in pages.items():
        (OUT_DIR / name).write_text(html, encoding="utf-8")

    outputs = {name: str((OUT_DIR / name).relative_to(BASE_DIR)) for name in pages}
    outputs["manifest.json"] = str((OUT_DIR / "manifest.json").relative_to(BASE_DIR))
    outputs["service-worker.js"] = str((OUT_DIR / "service-worker.js").relative_to(BASE_DIR))
    outputs["assets/style.css"] = str((ASSET_DIR / "style.css").relative_to(BASE_DIR))

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
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate read-only mobile dashboard (Phase 1)")
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    args = parser.parse_args()
    result = generate(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
