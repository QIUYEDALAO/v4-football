#!/usr/bin/env python3
"""
collect_v4_system_error_summary.py — 只读系统异常摘要采集器
============================================================
扫描 data/runtime/status/*.json 和 logs/*.log，提取异常摘要。
严格只读，不修改任何源文件，不执行任何修复/重试/kill。
输出脱敏后的安全摘要 JSON。

用法:
  python3 tools/collect_v4_system_error_summary.py
  python3 tools/collect_v4_system_error_summary.py --hours 48 --limit 20
  python3 tools/collect_v4_system_error_summary.py --output data/runtime/status/v4_system_error_summary_20260526.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
LOGS_DIR = BASE_DIR / "logs"

SCRUB_PATTERNS = [
    (re.compile(r'(?:api[_-]?key|apikey|RAPIDAPI[_-]?KEY|x[-]?rapidapi[-]?key)\s*[:=]\s*[\S]+', re.IGNORECASE), '[REDACTED:api_key]'),
    (re.compile(r'(?:Authorization|Bearer)\s+[\S]+', re.IGNORECASE), '[REDACTED:auth_header]'),
    (re.compile(r'(?:token|secret|password|passwd)\s*[:=]\s*[\S]+', re.IGNORECASE), '[REDACTED:credential]'),
    (re.compile(r'(?:Cookie)\s*[:=]\s*[\S]+', re.IGNORECASE), '[REDACTED:cookie]'),
    (re.compile(r'-----BEGIN[^-]*PRIVATE KEY-----[\s\S]*?-----END[^-]*PRIVATE KEY-----'), '[REDACTED:private_key]'),
    (re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'), '[REDACTED:long_token]'),
    (re.compile(r'sk-[A-Za-z0-9]{20,}'), '[REDACTED:sk_key]'),
]

SEVERITY_ORDER = {"BLOCKER": 0, "FAIL": 1, "WARN": 2, "INFO": 3}

ERROR_KEYWORDS = [
    "FAIL", "BLOCKER", "BLOCKED", "ERROR", "WARN", "traceback",
    "cron", "checker", "validation", "dashboard", "scan", "api", "retry",
    "timeout", "crash", "exception", "failed", "missing", "broken",
    "incomplete", "stale", "hung",
]

SELF_FEEDBACK_EXCLUDES = [
    re.compile(r"^v4_system_error_summary_\d{8}\.json$"),
    re.compile(r"^v4_control_center_system_error_center_.*\.json$"),
    re.compile(r"^v4_system_error_center_checker_.*\.json$"),
    re.compile(r"^v4_system_error_center_http_verify_.*\.json$"),
    re.compile(r"^v4_system_error_center_git_manifest_.*\.json$"),
]

PROCESS_ARTIFACT_PATTERNS = [
    re.compile(r".*_freeze_.*\.json$", re.IGNORECASE),
    re.compile(r".*_audit_.*\.json$", re.IGNORECASE),
    re.compile(r".*_verify_.*\.json$", re.IGNORECASE),
    re.compile(r".*_http_verify_.*\.json$", re.IGNORECASE),
    re.compile(r".*_content_verify_.*\.json$", re.IGNORECASE),
    re.compile(r".*_git_manifest_.*\.json$", re.IGNORECASE),
    re.compile(r".*_manifest_.*\.json$", re.IGNORECASE),
    re.compile(r".*_report_.*\.json$", re.IGNORECASE),
    re.compile(r".*_source_trace_.*\.json$", re.IGNORECASE),
    re.compile(r".*_classification_.*\.json$", re.IGNORECASE),
    re.compile(r".*_safety_impact_.*\.json$", re.IGNORECASE),
    re.compile(r".*_recommendation_.*\.json$", re.IGNORECASE),
    re.compile(r".*_fix_.*\.json$", re.IGNORECASE),
]

ACTIVE_TYPE_PATTERNS = [
    re.compile(r".*final.*", re.IGNORECASE),
    re.compile(r".*task_result.*", re.IGNORECASE),
    re.compile(r".*cron_task_result.*", re.IGNORECASE),
    re.compile(r".*watchdog.*", re.IGNORECASE),
    re.compile(r".*runner_result.*", re.IGNORECASE),
    re.compile(r".*pipeline_result.*", re.IGNORECASE),
    re.compile(r".*validation_result.*", re.IGNORECASE),
    re.compile(r".*scan_result.*", re.IGNORECASE),
]

COMPONENT_MAP = {
    "cron": "cron",
    "checker": "checker",
    "validation": "validation",
    "dashboard": "dashboard",
    "scan": "scan",
    "api": "api",
    "retry": "retry",
    "h2h": "h2h_engine",
    "model": "model_builder",
    "candidate": "candidate",
    "live_bet": "live_bet",
    "control_center": "control_center",
    "v4_control": "control_center",
}


def scrub_text(text: str) -> tuple[str, bool]:
    """对文本做脱敏，返回 (scrubbed_text, was_redacted)."""
    redacted = False
    for pattern, replacement in SCRUB_PATTERNS:
        if pattern.search(text):
            text = pattern.sub(replacement, text)
            redacted = True
    if len(text) > 500:
        text = text[:500] + "...[TRUNCATED]"
    return text, redacted


def parse_args():
    p = argparse.ArgumentParser(description="只读收集系统异常摘要")
    p.add_argument("--hours", type=int, default=48, help="扫描时间范围（小时）")
    p.add_argument("--limit", type=int, default=20, help="最大输出条数")
    p.add_argument("--output", default=None, help="输出文件路径")
    return p.parse_args()


def _detect_component(filepath: Path) -> str:
    name = filepath.stem.lower()
    for kw, comp in COMPONENT_MAP.items():
        if kw in name:
            return comp
    return "unknown"


def _resolve_severity(filepath: Path, content_preview: str) -> str:
    """从文件名和内容推断严重级别。"""
    combined = (filepath.stem + " " + content_preview[:200]).upper()
    if any(w in combined for w in ["BLOCKER", "BLOCKED"]):
        return "BLOCKER"
    if any(w in combined for w in ["FAIL", "ERROR", "CRASH", "EXCEPTION", "BROKEN"]):
        return "FAIL"
    if any(w in combined for w in ["WARN", "WARNING", "TIMEOUT", "STALE", "MISSING"]):
        return "WARN"
    return "INFO"


def _is_self_feedback_file(fp: Path) -> bool:
    name = fp.name
    return any(rx.match(name) for rx in SELF_FEEDBACK_EXCLUDES)


def _truthy(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "ok", "pass"}
    return False


def _status_from_json_obj(obj: dict) -> tuple[str, bool, str]:
    """
    基于 JSON 结构做状态判定（优先级高于文件名关键词）:
    返回: (severity, resolved_hint, reason)
    """
    if not isinstance(obj, dict):
        return "INFO", False, "non-dict json"

    def up(x):
        return str(x or "").strip().upper()

    final_status = up(obj.get("final_status"))
    # 兼容 phase 最终状态枚举：*_PASS / *_WARN_ONLY / *_BLOCKED
    if final_status.endswith("_PASS"):
        return "INFO", True, "phase final PASS enum"
    if final_status.endswith("_WARN_ONLY"):
        return "WARN", True, "phase final WARN enum"
    if final_status.endswith("_BLOCKED") or final_status.endswith("_BLOCKER"):
        return "BLOCKER", False, "phase final BLOCKED enum"
    conclusion = up(obj.get("conclusion"))
    status = up(obj.get("status"))
    checker_pass = _truthy(obj.get("checker_pass"))
    all_pass = obj.get("all_pass")
    ok = obj.get("ok")
    blocker_count = int(obj.get("blocker_count") or 0)
    fail_count = int(obj.get("fail_count") or 0)
    active_blocker_count = int(obj.get("active_blocker_count") or 0)
    active_error_count = int(obj.get("active_error_count") or 0)
    exit_code = obj.get("exit_code")
    traceback = obj.get("traceback")
    exception = obj.get("exception")
    blockers = obj.get("blockers")
    errors = obj.get("errors")
    failed = obj.get("failed")

    # PASS 信号（命中任一条则不可进入 ACTIVE）
    pass_signal = (
        final_status == "PASS"
        or conclusion == "PASS"
        or status == "PASS"
        or checker_pass
        or (_truthy(all_pass) if all_pass is not None else False)
        or ((_truthy(ok) if ok is not None else False) and (isinstance(blockers, list) and len(blockers) == 0))
        or (blocker_count == 0 and fail_count == 0 and blocker_count + fail_count > -1)
        or (active_blocker_count == 0 and active_error_count == 0 and (("active_blocker_count" in obj) or ("active_error_count" in obj)))
        or (isinstance(blockers, list) and len(blockers) == 0 and "blockers" in obj)
        or (isinstance(errors, list) and len(errors) == 0 and "errors" in obj)
        or (isinstance(failed, bool) and failed is False)
    )

    # 真实异常信号
    hard_blocker = final_status in {"BLOCKER", "BLOCKED"} or conclusion in {"BLOCKER", "BLOCKED"} or status in {"BLOCKER", "BLOCKED"}
    hard_fail = final_status == "FAIL" or conclusion == "FAIL" or status == "FAIL"
    has_runtime_err = bool(traceback) or bool(exception) or (isinstance(exit_code, int) and exit_code != 0)
    has_counts = (blocker_count > 0) or (fail_count > 0) or (active_blocker_count > 0) or (active_error_count > 0)
    has_lists = (isinstance(blockers, list) and len(blockers) > 0) or (isinstance(errors, list) and len(errors) > 0)
    all_pass_false = (all_pass is not None and not _truthy(all_pass)) or (ok is not None and not _truthy(ok))

    if pass_signal and not (hard_blocker or hard_fail or has_runtime_err or has_counts or has_lists or all_pass_false):
        return "INFO", True, "json PASS signal"

    if hard_blocker or active_blocker_count > 0 or blocker_count > 0:
        return "BLOCKER", False, "json blocker signal"
    if hard_fail or fail_count > 0 or has_runtime_err or all_pass_false:
        return "FAIL", False, "json fail signal"
    if has_lists or active_error_count > 0:
        return "WARN", False, "json warn signal"

    return "INFO", False, "json neutral"


def _is_process_artifact_file(fp: Path, obj: dict | None) -> bool:
    name = fp.name
    for rx in PROCESS_ARTIFACT_PATTERNS:
        if rx.match(name):
            return True
    # checker 文件默认作为过程产物，除非明确 final fail/blocker（在 active 白名单函数中再兜底）
    if re.match(r".*_checker_.*\.json$", name, re.IGNORECASE):
        return True
    step = str((obj or {}).get("step") or "").lower()
    if any(k in step for k in ("freeze", "audit", "verify", "checker", "manifest", "report", "fix")):
        return True
    return False


def _is_active_eligible_status_file(fp: Path, obj: dict | None, severity: str) -> tuple[bool, str]:
    obj = obj or {}
    name = fp.name
    stem = fp.stem

    # 先挡住 process artifact
    process_artifact = _is_process_artifact_file(fp, obj)
    if process_artifact:
        # 例外：checker 文件如果明确 FAIL/BLOCKER 且 all_pass=false，允许进入 ACTIVE
        if re.match(r".*_checker_.*\.json$", name, re.IGNORECASE):
            all_pass = obj.get("all_pass")
            conclusion = str(obj.get("conclusion") or "").upper()
            status = str(obj.get("status") or "").upper()
            final_status = str(obj.get("final_status") or "").upper()
            if (conclusion in {"FAIL", "BLOCKER", "BLOCKED"} or status in {"FAIL", "BLOCKER", "BLOCKED"} or final_status in {"FAIL", "BLOCKER", "BLOCKED"}) and (all_pass is False):
                return True, "checker_explicit_fail"
        return False, "process_artifact_excluded"

    # A. 最终任务结果文件：文件名包含 final/result/watchdog 等
    type_hit = any(rx.match(stem) for rx in ACTIVE_TYPE_PATTERNS)
    has_final_key = any(k in obj for k in ("final_status", "final_result", "task_result", "runner_result", "pipeline_result"))

    # B. 真实运行错误信号
    blockers = obj.get("blockers")
    errors = obj.get("errors")
    runtime_error = (
        bool(obj.get("traceback"))
        or bool(obj.get("exception"))
        or bool(obj.get("error_message"))
        or bool(obj.get("stderr"))
        or isinstance(obj.get("exit_code"), int) and obj.get("exit_code") != 0
        or int(obj.get("active_blocker_count") or 0) > 0
        or int(obj.get("blocker_count") or 0) > 0
        or int(obj.get("fail_count") or 0) > 0
        or (isinstance(blockers, list) and len(blockers) > 0)
        or (isinstance(errors, list) and len(errors) > 0)
    )

    # C. unresolved marker
    unresolved_signal = (
        obj.get("active") is True
        or str(obj.get("resolved")).lower() == "false"
        or str(obj.get("status") or "").upper() in {"FAIL", "BLOCKER", "BLOCKED"}
        or str(obj.get("conclusion") or "").upper() in {"FAIL", "BLOCKER", "BLOCKED"}
        or str(obj.get("final_status") or "").upper() in {"FAIL", "BLOCKER", "BLOCKED"}
    )

    if severity not in {"FAIL", "BLOCKER"}:
        return False, "severity_not_active"

    if (type_hit or has_final_key or runtime_error or unresolved_signal):
        return True, "eligible_signal"
    return False, "no_active_signal"


def _extract_title(filepath: Path, content_preview: str) -> str:
    """从文件名和内容提取标题。"""
    stem = filepath.stem
    # 截短文件名中的日期后缀
    stem = re.sub(r'_\d{8}$', '', stem)
    stem = stem.replace("_", " ").strip()
    if len(stem) > 80:
        stem = stem[:80] + "..."
    return stem or "unknown error"


def _extract_summary(content_preview: str) -> str:
    """提取safe摘要，最多200字符。"""
    lines = [l.strip() for l in content_preview.split("\n") if l.strip() and not l.strip().startswith("{")]
    summary = " ".join(lines[:3])
    if len(summary) > 200:
        summary = summary[:200] + "..."
    return summary or "no summary available"


def collect_status_errors(hours: int) -> list[dict]:
    """扫描 data/runtime/status/*.json 中的异常标记。"""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)

    if not STATUS_DIR.exists():
        return items

    for fp in sorted(STATUS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        if _is_self_feedback_file(fp):
            continue
        mtime = datetime.fromtimestamp(os.path.getmtime(fp), tz=timezone.utc)
        if mtime < cutoff:
            continue

        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        component = _detect_component(fp)
        severity = _resolve_severity(fp, content)
        title = _extract_title(fp, content)
        resolved_hint = False
        parse_reason = "keyword_fallback"

        obj: dict | None = None
        # 结构化 JSON 优先判定
        try:
            obj = json.loads(content)
            if isinstance(obj, dict):
                s2, resolved_hint, parse_reason = _status_from_json_obj(obj)
                severity = s2
        except Exception:
            pass

        # 只收集 WARN 及以上
        if severity not in ("BLOCKER", "FAIL", "WARN"):
            continue

        obj_dict = obj if isinstance(obj, dict) else {}
        process_artifact = _is_process_artifact_file(fp, obj_dict)
        active_eligible, active_reason = _is_active_eligible_status_file(
            fp,
            obj_dict,
            severity,
        )

        # 检查是否已被后续 PASS 覆盖（phase 优先）
        resolved = process_artifact or resolved_hint or _check_resolved(
            fp, component, title, obj_dict
        )
        active = (not resolved) and active_eligible and severity in ("BLOCKER", "FAIL")

        scrubbed_summary, was_redacted = scrub_text(content[:500])
        items.append({
            "detected_at": mtime.isoformat(),
            "source_file": fp.name,
            "source_path": str(fp),
            "source_type": "status_json",
            "component": component,
            "severity": severity,
            "title": title,
            "summary": _extract_summary(scrubbed_summary),
            "parse_reason": parse_reason,
            "impact": _infer_impact(component, severity),
            "suggested_action": _suggested_action(component, severity),
            "active": active,
            "resolved": resolved,
            "resolution_marker": "subsequent_PASS_found_or_process_artifact" if resolved else None,
            "process_artifact": process_artifact,
            "active_eligible": active_eligible,
            "active_eligible_reason": active_reason,
            "safe_to_show": True,
            "redacted": was_redacted,
            "raw_log_hidden": True,
        })
    return items


def collect_log_errors(hours: int) -> list[dict]:
    """扫描 logs/*.log 中的异常。"""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    if not LOGS_DIR.exists():
        return items

    log_files = list(LOGS_DIR.rglob("*.log"))
    for fp in sorted(log_files, key=os.path.getmtime, reverse=True)[:10]:
        mtime = datetime.fromtimestamp(os.path.getmtime(fp), tz=timezone.utc)
        if mtime < cutoff:
            continue

        try:
            lines = fp.read_text(encoding="utf-8", errors="ignore").split("\n")
        except Exception:
            continue

        # 查找 ERROR / Traceback 行
        error_blocks = []
        in_traceback = False
        current_block = []
        for line in lines[-500:]:  # 只看最后 500 行
            if "Traceback" in line or "ERROR" in line or "Exception" in line:
                in_traceback = True
                current_block = [line]
            elif in_traceback:
                current_block.append(line)
                if line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                    error_blocks.append("\n".join(current_block[-10:]))
                    in_traceback = False
                    current_block = []

        for block in error_blocks[-5:]:  # 最多取最后 5 个错误块
            severity = "FAIL" if "ERROR" in block else "WARN"
            scrubbed, was_redacted = scrub_text(block)
            items.append({
                "detected_at": mtime.isoformat(),
                "source_file": fp.name,
                "source_path": str(fp),
                "source_type": "log_file",
                "component": "log_monitor",
                "severity": severity,
                "title": "日志异常",
                "summary": _extract_summary(scrubbed),
                "impact": "日志中发现异常，需人工查看",
                "suggested_action": "检查对应组件状态",
                "active": True,
                "resolved": False,
                "resolution_marker": None,
                "safe_to_show": True,
                "redacted": was_redacted,
                "raw_log_hidden": True,
            })

    return items


def _is_pass_json(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    return (
        str(obj.get("final_status") or "").upper() == "PASS"
        or str(obj.get("conclusion") or "").upper() == "PASS"
        or str(obj.get("status") or "").upper() == "PASS"
        or _truthy(obj.get("all_pass"))
        or _truthy(obj.get("pass"))
    )


def _check_resolved(fp: Path, component: str, title: str, obj: dict | None = None) -> bool:
    """检查同一个 phase/task 是否有后续 PASS（phase 优先）。"""
    obj = obj or {}
    current_mtime = os.path.getmtime(fp)
    current_phase = str(obj.get("phase") or "").strip()

    # 1) phase 优先：同 phase 只要后续 PASS，即认为当前过程项已恢复
    if current_phase:
        for nf in sorted(STATUS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
            if nf == fp:
                continue
            if os.path.getmtime(nf) <= current_mtime:
                continue
            try:
                nobj = json.loads(nf.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            if str(nobj.get("phase") or "").strip() != current_phase:
                continue
            if _is_pass_json(nobj):
                return True
            # 同 phase 出现最终 BLOCKED，说明以最终状态替代中间过程项
            if str(nobj.get("final_status") or "").upper() in {"BLOCKER", "BLOCKED"} or str(nobj.get("conclusion") or "").upper() in {"BLOCKER", "BLOCKED"}:
                return True

    # 2) 退化到 stem 匹配
    stem_base = re.sub(r'_\d{8}$', '', fp.stem)
    newer_files = sorted(STATUS_DIR.glob(f"{stem_base}*.json"), key=os.path.getmtime, reverse=True)
    for nf in newer_files:
        if nf == fp:
            continue
        if os.path.getmtime(nf) <= current_mtime:
            continue
        try:
            nobj = json.loads(nf.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if _is_pass_json(nobj):
            return True
    return False


def _infer_impact(component: str, severity: str) -> str:
    impacts = {
        "cron": "定时任务可能中断",
        "checker": "系统检查未通过",
        "validation": "验证流程异常",
        "dashboard": "仪表盘数据可能不准确",
        "scan": "球探扫描可能中断",
        "api": "API 调用异常",
        "h2h_engine": "H2H 计算可能异常",
        "model_builder": "作战台数据模型构建异常",
        "candidate": "候选生成可能异常",
        "live_bet": "实盘记录可能异常",
        "control_center": "作战台主系统异常",
    }
    base = impacts.get(component, "系统组件异常")
    if severity == "BLOCKER":
        base += "（阻塞级别，需立即处理）"
    return base


def _suggested_action(component: str, severity: str) -> str:
    if severity == "BLOCKER":
        return f"建议人工检查 {component} 组件状态，确认是否需要手动介入"
    return f"监控 {component} 组件，等待自动恢复或人工确认"


def classify_and_rank(items: list[dict], hours: int) -> dict:
    """对错误分类并排名。"""
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=24)
    window_cutoff = now - timedelta(hours=hours)

    active_items = [i for i in items if i["active"] and i["severity"] in ("BLOCKER", "FAIL")]
    recent_items = [i for i in items if not i["active"] or i["severity"] == "WARN"]
    archive_items = []  # 超过窗口的不收集

    # 按严重程度排序
    active_items.sort(key=lambda x: SEVERITY_ORDER.get(x["severity"], 99))
    recent_items.sort(key=lambda x: SEVERITY_ORDER.get(x["severity"], 99))

    active_blocker_count = sum(1 for i in active_items if i["severity"] == "BLOCKER")
    active_error_count = len(active_items)
    recent_24h = [i for i in recent_items if datetime.fromisoformat(i["detected_at"]) >= recent_cutoff]
    recent_48h = [i for i in recent_items if datetime.fromisoformat(i["detected_at"]) >= window_cutoff]

    # 系统状态判定
    if active_blocker_count > 0:
        system_error_status = "BLOCKER"
    elif active_error_count > 0:
        system_error_status = "FAIL"
    elif len(recent_24h) > 0:
        system_error_status = "WARN_ONLY"
    else:
        system_error_status = "PASS"

    display_texts = {
        "BLOCKER": f"阻塞：{active_blocker_count} 项阻塞",
        "FAIL": f"异常：{active_error_count} 项 active",
        "WARN_ONLY": f"最近24h {len(recent_24h)} 条已恢复",
        "PASS": "当前无 active 异常",
    }

    return {
        "active_error_count": active_error_count,
        "active_blocker_count": active_blocker_count,
        "recent_error_count_24h": len(recent_24h),
        "recent_error_count_48h": len(recent_48h),
        "archive_count": len(archive_items),
        "latest_error_at": active_items[0]["detected_at"] if active_items else None,
        "latest_error_title": active_items[0]["title"] if active_items else None,
        "system_error_status": system_error_status,
        "display_text": display_texts.get(system_error_status, ""),
        "active_items": active_items,
        "recent_items": recent_items[:10],
        "archive_items": archive_items,
        "generated_at": now.isoformat(),
        "scan_window_hours": hours,
        "safe_to_show": True,
        "raw_logs_hidden": True,
        "read_only_collector": True,
    }


def main():
    args = parse_args()

    print(f"[collect] scanning status dir: {STATUS_DIR}")
    print(f"[collect] scanning logs dir: {LOGS_DIR}")
    print(f"[collect] window: {args.hours}h, limit: {args.limit}")

    status_items = collect_status_errors(args.hours)
    log_items = collect_log_errors(args.hours)
    all_items = status_items + log_items

    result = classify_and_rank(all_items, args.hours)

    # 限制总输出条数
    result["active_items"] = result["active_items"][:args.limit]
    result["recent_items"] = result["recent_items"][:args.limit]

    output_path = args.output
    if not output_path:
        today = datetime.now().strftime("%Y%m%d")
        output_path = str(STATUS_DIR / f"v4_system_error_summary_{today}.json")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[collect] {len(result['active_items'])} active, "
          f"{len(result['recent_items'])} recent, "
          f"status={result['system_error_status']}")
    print(f"[collect] written to {output_path}")


if __name__ == "__main__":
    main()
