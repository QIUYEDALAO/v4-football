#!/usr/bin/env python3
"""tools/notify_cron_task_complete_qq.py — V3/V4 定时任务完成后 QQ 通知脚本
===========================================================================
职责：每个 V3/V4 定时任务完成后，生成 iPhone 友好短文案并调用 QQ sender 发送通知。
不修改主任务状态，不运行 scan/validation/cloud，不改策略，不改 cron 时间。

用法：
  # Dry-run（只生成文案，不发送）
  python3 tools/notify_cron_task_complete_qq.py \
    --task V4_DAILY_SCAN_READONLY \
    --date 20260525 \
    --status PASS \
    --duration 269 \
    --dry-run

  # 真实发送
  python3 tools/notify_cron_task_complete_qq.py \
    --task V4_DAILY_SCAN_READONLY \
    --date 20260525 \
    --status PASS \
    --duration 269 \
    --exit-code 0

  # 从 marker 自动读取状态
  python3 tools/notify_cron_task_complete_qq.py \
    --task V4_DAILY_SCAN_READONLY \
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

# 5 个 V3/V4 定时任务配置
TASK_CONFIG = {
    "V4_DAILY_SCAN_READONLY": {
        "scheduled_time": "12:00",
        "scan_result": True,
        "dashboard_for": None,
        "task_names": {
            "scan": "V4_DAILY_SCAN_READONLY",
        },
    },
    "V3V4_DASHBOARD_AFTER_SCAN_REFRESH": {
        "scheduled_time": "13:00",
        "scan_result": False,
        "dashboard_for": "SCAN",
        "task_names": {
            "dashboard": "V3V4_DASHBOARD_AFTER_SCAN_REFRESH",
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
    "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH": {
        "scheduled_time": "13:30",
        "scan_result": False,
        "dashboard_for": "VALIDATION",
        "task_names": {
            "dashboard": "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH",
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
    "V4_DAILY_SCAN_READONLY": {
        "pattern": "v3v4_dashboard_brief_resolution_{date}.json",
        "key": "scan_resolution",
    },
    "V3V4_DASHBOARD_AFTER_SCAN_REFRESH": {
        "pattern": "v3v4_dashboard_daily_update_after_scan_apply_{date}.json",
        "key": "check_status",
    },
    "V4_VALIDATION_DRY_RUN": {
        "pattern": "v3v4_validation_summary_{date}.json",
        "key": None,  # 复合解析
    },
    "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH": {
        "pattern": "v3v4_dashboard_daily_update_after_validation_apply_{date}.json",
        "key": "check_status",
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


def read_marker_status(task_name: str, date: str) -> Optional[dict[str, Any]]:
    """从任务状态 marker 文件中读取状态信息。"""
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

    if task_name == "V4_DAILY_SCAN_READONLY":
        results["scan"] = "成功" if status in ("PASS", "WARN_ONLY") else "失败"
        results["dashboard"] = "N/A"
        results["validation"] = "待补验"
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

    return results


def build_notification_text(
    task_name: str, date: str, status: str, duration: int, results: dict[str, Any]
) -> str:
    """生成 iPhone 友好 QQ 通知文案。"""
    lines = []
    lines.append("【V3/V4定时任务完成】")
    lines.append(f"任务：{task_name}")
    config = TASK_CONFIG.get(task_name, {})
    lines.append(f"时间：{config.get('scheduled_time', '?')}")
    lines.append(f"状态：{status}")
    if isinstance(duration, (int, float)) and duration > 0:
        lines.append(f"耗时：{duration}秒")
    lines.append(f"日期：{date}")
    lines.append("")
    lines.append("结果：")
    lines.append(f"- scan: {results.get('scan', '?')}")
    lines.append(f"- dashboard: {results.get('dashboard', '?')}")
    lines.append(f"- validation: {results.get('validation', '?')}")
    lines.append(f"- pending: {results.get('pending', '?')}场")
    lines.append("")
    if status in ("FAIL", "BLOCKER"):
        lines.append("异常：")
        lines.append(f"原因：任务状态为{status}")
    elif status == "WARN_ONLY":
        lines.append("异常：")
        lines.append("原因：部分步骤有警告")
    else:
        lines.append("异常：无")
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
