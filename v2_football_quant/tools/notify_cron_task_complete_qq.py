#!/usr/bin/env python3
"""tools/notify_cron_task_complete_qq.py — V3/V4 定时任务完成后 QQ 通知脚本
===========================================================================
职责：每个 V3/V4 定时任务完成后，生成 iPhone 友好短文案并调用 QQ sender 发送通知。
不修改主任务状态，不运行 scan/validation/cloud，不改策略，不改 cron 时间。

用法：
  # Dry-run（只生成文案，不发送）
  python3 tools/notify_cron_task_complete_qq.py \
    --task V4_DAILY_SCAN_REAL_COMPLETED \
    --date 20260525 \
    --status PASS \
    --duration 269 \
    --dry-run

  # 真实发送
  python3 tools/notify_cron_task_complete_qq.py \
    --task V4_DAILY_SCAN_REAL_COMPLETED \
    --date 20260525 \
    --status PASS \
    --duration 269 \
    --exit-code 0

  # 从 marker 自动读取状态
  python3 tools/notify_cron_task_complete_qq.py \
    --task V4_DAILY_SCAN_REAL_COMPLETED \
    --date 20260525 \
    --exit-code 0

通知不会泄露 secret / token / webhook / 投注建议 / 盘口推荐 / 候选长表。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

TZ = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
QQ_SENDER = os.path.join(BASE_DIR, "engine", "qqbot_safe_send.py")

# 通知去重 marker 目录 - 与通知同目录
DEDUP_DIR = STATUS_DIR

# 报告 QQ Bot target（与 safe_outbound_sender.py 一致）
REPORT_TARGET = "D1BC6F68CBBAC6A473947C53ECB861EC"

# V3/V4 定时任务配置。
# 12:00 V4 拆成两个不同语义:
# - V4_DAILY_SCAN_WATCHDOG_CHECK: OpenClaw isolated session 只读值守检查，不代表扫描完成。
# - V4_DAILY_SCAN_REAL_COMPLETED: launchd durable runner 真实扫描结束后的 artifact-aware 通知。
TASK_CONFIG = {
    "V4_DAILY_SCAN_WATCHDOG_CHECK": {
        "scheduled_time": "12:00",
        "scan_result": False,
        "watchdog_check": True,
        "dashboard_for": None,
        "task_names": {
            "watchdog": "V4_DAILY_SCAN_WATCHDOG_CHECK",
        },
    },
    "V4_DAILY_SCAN_REAL_COMPLETED": {
        "scheduled_time": "12:00",
        "scan_result": True,
        "artifact_aware": True,
        "dashboard_for": None,
        "task_names": {
            "scan": "V4_DAILY_SCAN_REAL_COMPLETED",
        },
    },
    "V4_CONTROL_CENTER_REFRESH_AFTER_SCAN": {
        "scheduled_time": "13:00",
        "scan_result": False,
        "dashboard_for": "SCAN",
        "task_names": {
            "dashboard": "V4_CONTROL_CENTER_REFRESH_AFTER_SCAN",
        },
    },
    "V4_VALIDATION_DRY_RUN": {
        "scheduled_time": "13:00",
        "scan_result": False,
        "dashboard_for": None,
        "task_names": {
            "validation": "V4_VALIDATION_DRY_RUN",
        },
    },
    "V4_CONTROL_CENTER_REFRESH_AFTER_VALIDATION": {
        "scheduled_time": "13:30",
        "scan_result": False,
        "dashboard_for": "VALIDATION",
        "task_names": {
            "dashboard": "V4_CONTROL_CENTER_REFRESH_AFTER_VALIDATION",
        },
    },
    "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH": {
        "scheduled_time": "14:00",
        "scan_result": False,
        "dashboard_for": "FINAL",
        "task_names": {
            "dashboard": "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH",
            "validation": "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH",
        },
    },
}

STATUS_MARKER_MAP = {
    "V4_CONTROL_CENTER_REFRESH_AFTER_SCAN": {
        "pattern": "v4_control_center_refresh_after_scan_apply_{date}.json",
        "key": "conclusion",
    },
    "V4_VALIDATION_DRY_RUN": {
        "pattern": "v3v4_validation_summary_{date}.json",
        "key": None,  # 复合解析
    },
    "V4_CONTROL_CENTER_REFRESH_AFTER_VALIDATION": {
        "pattern": "v4_control_center_refresh_after_validation_apply_{date}.json",
        "key": "conclusion",
    },
    "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH": {
        "pattern": "v3v4_validation_final_and_dashboard_refresh_{date}.json",
        "key": "check_status",
    },
}


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def now_str() -> str:
    return datetime.now(TZ).strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _scan_paths(date: str) -> dict[str, Path]:
    daily = BASE_DIR / "data" / "daily_reports"
    return {
        "scan_perf": daily / f"scan_perf_v4_{date}.json",
        "scout": daily / f"scout_v4_{date}.json",
        "brief": daily / f"v4_openclaw_brief_{date}.txt",
        "candidate_view": STATUS_DIR / f"v4_official_candidate_view_{date}.json",
        "durable_status": STATUS_DIR / "v4_durable_daily_scan_status.json",
    }


def read_real_scan_artifacts(date: str) -> dict[str, Any]:
    """Read real V4 scan artifacts and classify scan completion without secrets."""
    paths = _scan_paths(date)
    exists = {name: path.exists() and path.stat().st_size > 0 for name, path in paths.items()}
    missing = [name for name, ok in exists.items() if not ok]
    scan_perf = load_json(paths["scan_perf"]) if exists["scan_perf"] else {}
    candidate = load_json(paths["candidate_view"]) if exists["candidate_view"] else {}
    durable = load_json(paths["durable_status"]) if exists["durable_status"] else {}

    durable_ok = (
        str(durable.get("scan_date") or "") == date
        and str(durable.get("state") or "").upper() in {
            "COMPLETED",
            "SCAN_COMPLETED_NOTIFY_PENDING",
            "QQ_FAILED_SCAN_OK",
        }
        and int(durable.get("scan_exit_code") or durable.get("last_exit_code") or 0) == 0
    )
    scan_total = candidate.get("scan_total", scan_perf.get("total_fixtures"))
    counts = {
        "A": int(candidate.get("A_count") or 0),
        "B": int(candidate.get("B_count") or 0),
        "C": int(candidate.get("C_count") or 0),
        "SKIP": int(candidate.get("SKIP_count") or 0),
    }
    artifact_ok = not missing and durable_ok and scan_total is not None
    status = "PASS" if artifact_ok else "FAIL"
    return {
        "status": status,
        "data": {
            "artifact_guard_status": "PASS" if artifact_ok else "MISSING_OR_FAILED",
            "exists": exists,
            "missing_artifacts": missing,
            "durable_status_ok": durable_ok,
            "durable_state": durable.get("state"),
            "scan_exit_code": durable.get("scan_exit_code", durable.get("last_exit_code")),
            "scan_total": scan_total,
            "scouted_count": scan_perf.get("scouted_count"),
            "elapsed_seconds": scan_perf.get("elapsed_seconds") or durable.get("duration_seconds"),
            "api_calls_total": scan_perf.get("api_calls_total"),
            "remote_requests": scan_perf.get("remote_requests"),
            "api_cache_hits": scan_perf.get("api_cache_hits"),
            "api_cache_misses": scan_perf.get("api_cache_misses"),
            "counts": counts,
            "formal_recommendation_count": candidate.get("formal_recommendation_count"),
            "actual_send": bool(candidate.get("actual_send")),
            "qq_sent": bool(candidate.get("qq_sent")),
            "paths": {name: str(path.relative_to(BASE_DIR)) for name, path in paths.items()},
        },
        "path": str(paths["candidate_view"]),
    }


def read_marker_status(task_name: str, date: str) -> Optional[dict[str, Any]]:
    """从任务状态 marker 文件中读取状态信息。"""
    if task_name == "V4_DAILY_SCAN_REAL_COMPLETED":
        return read_real_scan_artifacts(date)
    if task_name == "V4_DAILY_SCAN_WATCHDOG_CHECK":
        return {"status": "PASS", "data": {"watchdog_check_only": True}, "path": ""}
    cfg = STATUS_MARKER_MAP.get(task_name)
    if not cfg:
        return None
    pattern = cfg["pattern"].format(date=date)
    path = STATUS_DIR / pattern
    if not path.exists():
        return None
    data = load_json(path)
    if cfg["key"]:
        status_raw = str(data.get(cfg["key"], "")).upper()
    else:
        status_raw = str(data.get("status", "")).upper()
    return {"status": status_raw, "data": data, "path": str(path)}


def classify_status(exit_code: int, status_text: str) -> str:
    """将 exit code + status text 归类为标准状态。"""
    if exit_code == 0 or exit_code is None:
        if "BLOCKER" in status_text:
            return "BLOCKER"
        if "FAIL" in status_text:
            return "FAIL"
        if "WARN" in status_text:
            return "WARN_ONLY"
        return "PASS"
    else:
        if "WARN" in status_text:
            return "WARN_ONLY"
        if "BLOCKER" in status_text:
            return "BLOCKER"
        return "FAIL"


def build_result_lines(task_name: str, date: str, status: str, duration: int, marker_info: Optional[dict]) -> dict[str, Any]:
    """构建文案关键结果字段，不返回完整文本，留给生成器做。"""
    config = TASK_CONFIG.get(task_name, {})
    results = {}

    if task_name == "V4_DAILY_SCAN_WATCHDOG_CHECK":
        results["scan"] = "未运行（值守检查）"
        results["dashboard"] = "N/A"
        results["validation"] = "N/A"
        results["pending"] = "N/A"
    elif task_name == "V4_DAILY_SCAN_REAL_COMPLETED":
        data = marker_info.get("data", {}) if marker_info else {}
        results["scan"] = "真实扫描完成" if status in ("PASS", "WARN_ONLY") else "失败/超时/无产物"
        results["dashboard"] = "N/A"
        results["validation"] = "待补验"
        results["pending"] = str(data.get("formal_recommendation_count", "0"))
        results["scan_total"] = data.get("scan_total", "?")
        results["scouted_count"] = data.get("scouted_count", "?")
        results["elapsed_seconds"] = data.get("elapsed_seconds", "?")
        results["api_calls_total"] = data.get("api_calls_total", "?")
        results["remote_requests"] = data.get("remote_requests", "?")
        results["counts"] = data.get("counts", {})
        results["missing_artifacts"] = data.get("missing_artifacts", [])
        results["artifact_guard_status"] = data.get("artifact_guard_status", "?")
    elif task_name == "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH":
        results["scan"] = "未运行"
        dashboard_ok = status in ("PASS", "WARN_ONLY")
        results["dashboard"] = "已刷新(终验)" if dashboard_ok else "失败"
        results["validation"] = "已生成" if dashboard_ok else "失败"
    elif "DASHBOARD" in task_name:
        results["scan"] = "未运行"
        phase = config.get("dashboard_for", "?")
        dashboard_ok = status in ("PASS", "WARN_ONLY")
        results["dashboard"] = f"已刷新({phase})" if dashboard_ok else "失败"
        results["validation"] = "N/A"
    elif "VALIDATION" in task_name:
        results["scan"] = "未运行"
        results["dashboard"] = "N/A"
        results["validation"] = "已生成" if status in ("PASS", "WARN_ONLY") else "失败"
    else:
        results["scan"] = "?"
        results["dashboard"] = "?"
        results["validation"] = "?"

    # 通过 status marker 获取 pending 场次信息
    if marker_info and marker_info.get("data"):
        data = marker_info["data"]
        if "pending" in data:
            results["pending"] = str(data["pending"])
        elif "pending_count" in data:
            results["pending"] = str(data["pending_count"])
        elif "no_data" in str(data):
            results["pending"] = "N/A"
        # 从 validation summary 获取 pending
        if task_name == "V4_VALIDATION_DRY_RUN":
            vs = data.get("validation_stage", {})
            pending = vs.get("pending", vs.get("pending_count", "?"))
            results["pending"] = str(pending)

    # ── 兜底：如果 pending 没有被任何分支设置，给合理默认值 ──
    if "pending" not in results:
        if marker_info is None:
            results["pending"] = "未知（无marker）"
        else:
            results["pending"] = "0（无字段）"

    return results


def build_notification_text(
    task_name: str, date: str, status: str, duration: int, results: dict[str, Any]
) -> str:
    """生成 iPhone 友好 QQ 通知文案。"""
    lines = []
    if task_name == "V4_DAILY_SCAN_WATCHDOG_CHECK":
        lines.append("【V4值守检查完成】")
    elif task_name == "V4_DAILY_SCAN_REAL_COMPLETED" and status in ("PASS", "WARN_ONLY"):
        lines.append("【V4真实扫描完成】")
    elif task_name == "V4_DAILY_SCAN_REAL_COMPLETED":
        lines.append("【V4扫描失败/超时/无产物】")
    else:
        lines.append("【V3/V4定时任务完成】")
    # 避免 QQ Markdown 把下划线当作斜体标记，用全角下划线替代
    display_name = task_name.replace("_", "＿")
    lines.append(f"任务：{display_name}")
    config = TASK_CONFIG.get(task_name, {})
    lines.append(f"时间：{config.get('scheduled_time', '?')}")
    lines.append(f"状态：{status}")
    if isinstance(duration, (int, float)) and duration > 0:
        lines.append(f"耗时：{duration}秒")
    lines.append(f"日期：{date}")
    lines.append("")
    lines.append("结果：")
    if task_name == "V4_DAILY_SCAN_REAL_COMPLETED":
        counts = results.get("counts") or {}
        lines.append(f"- scan: {results.get('scan', '?')}")
        lines.append(f"- total/scouted: {results.get('scan_total', '?')}/{results.get('scouted_count', '?')}")
        lines.append(
            "- A/B/C/SKIP: "
            f"{counts.get('A', 0)}/{counts.get('B', 0)}/{counts.get('C', 0)}/{counts.get('SKIP', 0)}"
        )
        lines.append(f"- API calls: {results.get('api_calls_total', '?')} (remote {results.get('remote_requests', '?')})")
        lines.append(f"- artifact guard: {results.get('artifact_guard_status', '?')}")
    else:
        lines.append(f"- scan: {results.get('scan', '?')}")
        lines.append(f"- dashboard: {results.get('dashboard', '?')}")
        lines.append(f"- validation: {results.get('validation', '?')}")
        lines.append(f"- pending: {results.get('pending', '?')}场")
    lines.append("")
    if status in ("FAIL", "BLOCKER"):
        lines.append("异常：")
        if task_name == "V4_DAILY_SCAN_REAL_COMPLETED" and results.get("missing_artifacts"):
            lines.append("原因：真实扫描产物缺失：" + ", ".join(results.get("missing_artifacts", [])))
        else:
            lines.append(f"原因：任务状态为{status}")
    elif status == "WARN_ONLY":
        lines.append("异常：")
        lines.append("原因：部分步骤有警告")
    else:
        lines.append("异常：无")
    if task_name == "V4_DAILY_SCAN_WATCHDOG_CHECK":
        lines.append("说明：这是值守检查完成，不代表真实扫描完成。")
    if task_name == "V4_DAILY_SCAN_REAL_COMPLETED":
        lines.append("说明：仅通知扫描状态；不推shadow/C/SKIP长表，不输出推荐。")
    return "\n".join(lines)


def check_dedup(task_name: str, date: str, run_id: str) -> bool:
    """检查是否已通知过。已通知返回 True。"""
    marker_path = DEDUP_DIR / f"qq_notify_done_{task_name}_{date}_{run_id}.json"
    if marker_path.exists():
        return True
    return False


def write_dedup_marker(task_name: str, date: str, run_id: str, status: str) -> None:
    """写入通知去重 marker。"""
    marker = {
        "task_name": task_name,
        "date": date,
        "run_id": run_id,
        "status": status,
        "notified_at": now_str(),
        "source": "notify_cron_task_complete_qq",
    }
    marker_path = DEDUP_DIR / f"qq_notify_done_{task_name}_{date}_{run_id}.json"
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[NOTIFY] ✅ dedup marker: {marker_path.name}", flush=True)


def send_via_openclaw(message: str, dry_run: bool) -> dict[str, Any]:
    """通过 openclaw message send 发送 QQ 通知。"""
    result = {
        "sent": False,
        "command": "",
        "stdout": "",
        "stderr": "",
        "returncode": -1,
    }

    if dry_run:
        result["sent"] = False
        result["command"] = "[DRY-RUN]"
        result["stdout"] = message[:200] + "..."
        return result

    cmd = [
        "openclaw", "message", "send",
        "--channel", "qqbot",
        "--account", "report",
        "--target", REPORT_TARGET,
        "--message", message,
        "--json",
    ]
    result["command"] = " ".join(cmd)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        result["returncode"] = proc.returncode
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["sent"] = proc.returncode == 0
    except subprocess.TimeoutExpired:
        result["stderr"] = "TIMEOUT: openclaw message send"
    except Exception as e:
        result["stderr"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="V3/V4 定时任务完成后 QQ 通知")
    parser.add_argument("--task", required=True, choices=list(TASK_CONFIG.keys()),
                        help="任务名称")
    parser.add_argument("--date", default=datetime.now(TZ).strftime("%Y%m%d"),
                        help="日期 YYYYMMDD（默认今天）")
    parser.add_argument("--status", choices=["PASS", "WARN_ONLY", "FAIL", "BLOCKER"],
                        help="手动指定状态（默认自动从 exit_code + marker 推导）")
    parser.add_argument("--exit-code", type=int, default=0,
                        help="主任务 exit code（默认 0）")
    parser.add_argument("--duration", type=int, default=0,
                        help="任务耗时（秒）")
    parser.add_argument("--run-id",
                        help="运行标识（默认 date+now）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只生成文案和验证，不发送")
    args = parser.parse_args()

    run_id = args.run_id or f"{args.date}_{now_str()}"
    text = ""
    delivery_result = {}

    # ── Step 1: 读取状态 marker ──
    marker_info = read_marker_status(args.task, args.date)

    # ── Step 2: 确定状态 ──
    if args.status:
        status = args.status
    else:
        marker_status = marker_info.get("status", "") if marker_info else ""
        status = classify_status(args.exit_code, marker_status)

    # ── Step 3: 去重检查 ──
    if check_dedup(args.task, args.date, run_id):
        print(f"[NOTIFY] ⏭️ 已通知过 (task={args.task} date={args.date} run={run_id})", flush=True)
        return

    # ── Step 4: 生成结果字段 ──
    results = build_result_lines(args.task, args.date, status, args.duration, marker_info)

    # ── Step 5: 生成文案 ──
    text = build_notification_text(args.task, args.date, status, args.duration, results)

    # ── Step 6: 安全校验 ──
    forbidden = [
        "sk-", "api_key", "apikey", "secret", "token",
        "webhook", "OPENCLAW_", "DASHSCOPE_",
        "appid", "app_secret", "clientSecret",
    ]
    for f in forbidden:
        if f.lower() in text.lower():
            print(f"[NOTIFY] ❌ BLOCKER: 文案包含敏感词: {f}", flush=True)
            print(f"[NOTIFY] 文案:\n{text}", flush=True)
            sys.exit(1)

    if not text.strip():
        print("[NOTIFY] ❌ 文案为空", flush=True)
        sys.exit(1)

    # ── Step 7: 输出文案 ──
    print(f"[NOTIFY] {'=' * 40}", flush=True)
    print(f"[NOTIFY] 任务: {args.task}", flush=True)
    print(f"[NOTIFY] 日期: {args.date}", flush=True)
    print(f"[NOTIFY] 状态: {status}", flush=True)
    print(f"[NOTIFY] 耗时: {args.duration}秒", flush=True)
    print(f"[NOTIFY] 运行ID: {run_id}", flush=True)
    print(f"[NOTIFY] 去重: {'⏭️ 已存在' if check_dedup(args.task, args.date, run_id) else '✅ 新通知'}", flush=True)
    print(f"[NOTIFY] {'=' * 40}", flush=True)
    print(f"[NOTIFY] 文案:", flush=True)
    print(text, flush=True)
    print(f"[NOTIFY] {'=' * 40}", flush=True)

    if args.dry_run:
        print(f"\n✅ DRY-RUN PASS — 文案已生成，未发送", flush=True)
        return

    # ── Step 8: 发送 QQ 通知 ──
    delivery_result = send_via_openclaw(text, dry_run=False)

    if delivery_result["sent"]:
        print(f"[NOTIFY] ✅ QQ已发送 | stdout: {delivery_result['stdout'][:200]}", flush=True)
        write_dedup_marker(args.task, args.date, run_id, status)
    else:
        print(f"[NOTIFY] ⚠️ QQ发送失败: {delivery_result['stderr'][:300]}", flush=True)
        # QQ 发送失败不返回非0，不影响主任务状态
        # 但写入失败 marker 以便后期排查
        fail_marker = {
            "task_name": args.task,
            "date": args.date,
            "run_id": run_id,
            "status": status,
            "qq_delivered": False,
            "error": delivery_result.get("stderr", "unknown"),
            "notified_at": now_str(),
            "source": "notify_cron_task_complete_qq",
        }
        fail_path = DEDUP_DIR / f"qq_notify_failed_{args.task}_{args.date}_{run_id}.json"
        fail_path.write_text(json.dumps(fail_marker, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[NOTIFY] ⚠️ QQ发送失败 marker: {fail_path.name}", flush=True)


if __name__ == "__main__":
    main()
