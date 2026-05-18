#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


TERMINAL_STATES = {
    "DONE",
    "FAILED",
    "MISSING",
    "STALE",
    "SKIPPED",
    "ABNORMAL",
    "BLOCKED",
}

FAILURE_STATES = {"FAILED", "MISSING", "STALE", "ABNORMAL", "BLOCKED"}
WAITING_STATES = {"PENDING", "WAITING_DUE_TIME", "RUNNING", "UNKNOWN"}

ALLOWED_RUNTIME_STATES = {
    "PENDING",
    "WAITING_DUE_TIME",
    "RUNNING",
    "DONE",
    "FAILED",
    "MISSING",
    "STALE",
    "SKIPPED",
    "ABNORMAL",
    "BLOCKED",
    "UNKNOWN",
}

ALLOWED_RENDER_STATES = {"PASS", "WARN", "FAIL", "MISSING"}
ALLOWED_PRODUCTION_STATES = {
    "CODE_READY",
    "PIPELINE_READY",
    "PRODUCTION_VERIFIED",
    "ABNORMAL",
    "WAITING_DUE_TIME",
}

STATUS_CN = {
    "PENDING": "待处理",
    "WAITING_DUE_TIME": "待到时触发",
    "RUNNING": "运行中",
    "DONE": "已完成",
    "FAILED": "失败",
    "MISSING": "缺失",
    "STALE": "陈旧",
    "SKIPPED": "已跳过",
    "ABNORMAL": "异常",
    "BLOCKED": "阻断",
    "UNKNOWN": "未知",
    "PASS": "通过",
    "WARN": "警告",
    "FAIL": "失败",
    "CODE_READY": "代码就绪",
    "PIPELINE_READY": "流水线就绪",
    "PRODUCTION_VERIFIED": "生产验证通过",
}


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_status(value: Any, kind: str = "runtime") -> str:
    raw = _to_str(value).upper()
    if not raw:
        return "MISSING" if kind in {"runtime", "render"} else "CODE_READY"

    if kind == "render":
        if raw in ALLOWED_RENDER_STATES:
            return raw
        if raw in {"DONE", "SUCCESS"}:
            return "PASS"
        if raw in {"ERROR", "FAILED"}:
            return "FAIL"
        return "MISSING"

    if kind == "production":
        if raw in ALLOWED_PRODUCTION_STATES:
            return raw
        if raw in {"PASS", "DONE"}:
            return "PIPELINE_READY"
        if raw in {"FAIL", "FAILED", "ABNORMAL"}:
            return "ABNORMAL"
        return "CODE_READY"

    if raw in ALLOWED_RUNTIME_STATES:
        return raw
    if raw in {"SUCCESS", "COMPLETED"}:
        return "DONE"
    if raw in {"FAIL", "ERROR"}:
        return "FAILED"
    if raw in {"WAITING", "NOT_DUE"}:
        return "WAITING_DUE_TIME"
    return "UNKNOWN"


def is_terminal(status: Any) -> bool:
    return normalize_status(status) in TERMINAL_STATES


def is_failure(status: Any) -> bool:
    return normalize_status(status) in FAILURE_STATES


def is_waiting(status: Any) -> bool:
    return normalize_status(status) in WAITING_STATES


def production_verified_allowed(evidence: dict[str, Any]) -> bool:
    """
    PRODUCTION_VERIFIED only when guard/route/sent all satisfy strict evidence.

    Required:
    - guard_pass = True
    - route_allowed = True
    - sent_ok = True
    - fallback_used = False
    """
    if not isinstance(evidence, dict):
        return False
    guard_pass = bool(evidence.get("guard_pass"))
    route_allowed = bool(evidence.get("route_allowed"))
    sent_ok = bool(evidence.get("sent_ok"))
    fallback_used = bool(evidence.get("fallback_used"))
    return guard_pass and route_allowed and sent_ok and (not fallback_used)


def status_to_cn(status: Any) -> str:
    s = normalize_status(status)
    return STATUS_CN.get(s, s)


__all__ = [
    "normalize_status",
    "is_terminal",
    "is_failure",
    "is_waiting",
    "production_verified_allowed",
    "status_to_cn",
]

