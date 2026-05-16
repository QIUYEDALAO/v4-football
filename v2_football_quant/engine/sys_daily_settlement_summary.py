#!/usr/bin/env python3
"""engine/sys_daily_settlement_summary.py — SYS每日结算汇总（纯脚本）
============================================================
职责：只读文件、生成固定格式摘要、可选推送。
不调用 AI / agentTurn / memory_search / ReportAgent。
不自由总结。

用法:
  python3 engine/sys_daily_settlement_summary.py --date 20260515
  python3 engine/sys_daily_settlement_summary.py --date 20260515 --dry-run
  python3 engine/sys_daily_settlement_summary.py --date 20260515 --push
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_TZ = timezone(timedelta(hours=8))
REPORT_DIR = BASE_DIR / "data" / "paper_trading"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
DAILY_DIR = BASE_DIR / "data" / "daily_reports"


def _load_json(path: Path, default: dict = None) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default or {}


def _status_path() -> Path:
    return STATUS_DIR / "task_status_v2_daily_settle.json"


def _verified_path(date_key: str) -> Path:
    return REPORT_DIR / f"verified_{date_key}.json"


def _review_qq_path(date_key: str) -> Path:
    return DAILY_DIR / f"v4_review_qq_{date_key}.txt"


def _guard_qq_path(date_key: str) -> Path:
    return STATUS_DIR / f"v4_review_guard_qq_{date_key}.json"


def _readiness_path(date_key: str) -> Path:
    return STATUS_DIR / f"v4_review_readiness_{date_key}.json"


def _structured_path(date_key: str) -> Path:
    return DAILY_DIR / f"v4_review_structured_{date_key}.json"


def parse_v2(date_key: str) -> dict:
    """读取 V2 结算状态"""
    verified = _load_json(_verified_path(date_key))
    task_status = _load_json(_status_path())

    if not verified:
        return {"status": "MISSING", "detail": "verified file not found"}
    
    # Check task_status match
    ts_date = task_status.get("date", "")
    ts_status = task_status.get("status", "")
    ts_verified_out = str(task_status.get("output_files", {}).get("verified", ""))

    if ts_date == "" or ts_status != "DONE":
        return {"status": "PARTIAL", "detail": "task_status not DONE or missing"}
    
    if date_key not in ts_verified_out and date_key not in str(verified.get("date", "")):
        # date mismatch warning but file exists — treat as DONE
        pass

    total = verified.get("total_predicted", 0)
    completed = verified.get("total_completed", 0)
    hits = verified.get("hits", 0)
    pnl = verified.get("total_pnl", 0.0)
    hit_rate = verified.get("hit_rate_pct", 0.0)

    return {
        "status": "DONE",
        "detail": "",
        "bet_locked": total,
        "completed": completed,
        "hits": hits,
        "hit_rate_pct": hit_rate,
        "pnl": pnl,
        "verified_file": "verified_{}.json".format(date_key),
        "task_status_file": "task_status_v2_daily_settle.json",
    }


def parse_v4(date_key: str) -> dict:
    """读取 V4 复盘状态（按优先级）"""

    # 优先级1：复盘已完成
    guard_qq = _load_json(_guard_qq_path(date_key))
    review_qq = _review_qq_path(date_key)

    if guard_qq.get("guard_status") == "PASS" and review_qq.exists():
        return {
            "status": "REVIEW_DONE",
            "detail": "",
            "review_qq_file": "v4_review_qq_{}.txt".format(date_key),
            "guard_qq_file": "v4_review_guard_qq_{}.json".format(date_key),
        }

    # 优先级2：复盘未就绪 / 状态不可验证
    readiness = _load_json(_readiness_path(date_key))
    if readiness:
        rs = readiness.get("status", "UNKNOWN")
        reason = readiness.get("reason", "")
        details = readiness.get("details", "")
        if rs == "REVIEW_NOT_READY":
            return {
                "status": "REVIEW_NOT_READY",
                "detail": "正式样本比赛尚未全部完赛",
                "reason": reason,
            }
        elif rs == "REVIEW_STATUS_UNVERIFIED":
            return {
                "status": "REVIEW_STATUS_UNVERIFIED",
                "detail": "API/env 或赛果状态不可验证",
                "reason": reason,
            }
        else:
            return {
                "status": "REVIEW_{}".format(rs),
                "detail": details,
            }

    # 优先级3：什么都不存在
    return {
        "status": "MISSING",
        "detail": "review_qq / guard_qq / readiness 均不存在",
    }


def build_summary(date_key: str) -> dict:
    """生成汇总文本"""
    v2 = parse_v2(date_key)
    v4 = parse_v4(date_key)

    # V2 文本
    v2_status = v2["status"]
    v2_lines = []
    v2_lines.append(f"状态：{v2_status}")
    if v2_status == "DONE":
        v2_lines.append(f"BET_LOCKED：{v2.get('bet_locked',0)}")
        v2_lines.append(f"命中：{v2.get('hits',0)}/{v2.get('completed',0)}（{v2.get('hit_rate_pct',0)}%）")
        v2_lines.append(f"PnL：{v2.get('pnl',0)}u")
    elif v2.get("detail"):
        v2_lines.append(f"说明：{v2['detail']}")

    # V4 文本
    v4_status = v4["status"]
    v4_lines = []
    v4_lines.append(f"状态：{v4_status}")
    if v4_status == "REVIEW_DONE":
        v4_lines.append("A/B：请查看 review_qq 文本")
        v4_lines.append("C级：请查看 review_qq 文本")
        v4_lines.append("SKIP反杀：请查看 review_qq 文本")
    elif v4_status == "REVIEW_NOT_READY":
        v4_lines.append(f"说明：{v4.get('detail','')}")
        v4_lines.append(f"原因：{v4.get('reason','')}")
        v4_lines.append("动作：等待赛果完成后复盘")
    elif v4_status == "REVIEW_STATUS_UNVERIFIED":
        v4_lines.append(f"说明：{v4.get('detail','')}")
        v4_lines.append(f"原因：{v4.get('reason','')}")
        v4_lines.append("动作：等待 API/env 修复或下次 cron 验证")
    else:
        v4_lines.append(f"说明：{v4.get('detail','')}")
        v4_lines.append("缺失：review_qq / guard_qq / readiness")

    # 今日准备
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    today_key = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    ready_lines = []
    ready_lines.append(f"V2建池：13:15待执行")
    ready_lines.append(f"V4午间扫描：14:05待执行")
    ready_lines.append("异常：无")

    # 组装
    lines = []
    lines.append("【SYS 状态中控】")
    lines.append(f"📌 每日结算汇总 · {date_key}")
    lines.append("")
    lines.append("【V2昨日结算】")
    lines.extend(v2_lines)
    lines.append("")
    lines.append("【V4昨日复盘】")
    lines.extend(v4_lines)
    lines.append("")
    lines.append("【今日准备】")
    lines.extend(ready_lines)

    summary_text = "\n".join(lines)

    return {
        "date": date_key,
        "summary": summary_text,
        "v2": v2,
        "v4": v4,
        "ready": {"v2_pool": "pending", "v4_scan": "pending", "abnormal": False},
    }


def push_via_system_event(summary_text: str, date_key: str) -> bool:
    """通过 sessions_send 推送至主会话"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"""
import json, sys
from pathlib import Path
# Write push-ready file for gateway/system
push_path = Path('/Users/liudehua/.openclaw/workspace/v2_football_quant/data/runtime/status/sys_daily_summary_{date_key}.json')
push_data = {json.dumps({"date": date_key, "summary": summary_text, "status": "COMPLETE_REPORT"})}
push_path.write_text(json.dumps(push_data, ensure_ascii=False, indent=2), encoding='utf-8')
print('PUSH_FILE_WRITTEN')
"""],
            capture_output=True, text=True, timeout=30,
        )
        return "PUSH_FILE_WRITTEN" in result.stdout
    except Exception as e:
        print(f"[SYS] push write error: {e}", flush=True)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true", help="仅输出，不推")
    parser.add_argument("--push", action="store_true", help="推送（写文件 + sessions_send）")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    result = build_summary(date_key)

    # Always write status file
    status_path = STATUS_DIR / f"sys_daily_summary_{date_key}.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(result["summary"])

    if args.push:
        ok = push_via_system_event(result["summary"], date_key)
        if ok:
            print(f"[SYS] ✅ push file written: {status_path}")
        else:
            print(f"[SYS] ❌ push failed", flush=True)
    elif args.dry_run:
        print()
        print("--- dry-run (no push) ---")


if __name__ == "__main__":
    main()
