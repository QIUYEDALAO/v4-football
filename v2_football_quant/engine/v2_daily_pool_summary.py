#!/usr/bin/env python3
"""engine/v2_daily_pool_summary.py — V2每日建池摘要（纯脚本）
============================================================
职责：只读 state 文件、生成固定格式摘要、可选 QQ 推送。
不调用 AI / memory_search / agentTurn / announce / wake。

用法:
  python3 engine/v2_daily_pool_summary.py --date 20260516
  python3 engine/v2_daily_pool_summary.py --date 20260516 --dry-run
  python3 engine/v2_daily_pool_summary.py --date 20260516 --push
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_TZ = timezone(timedelta(hours=8))
STATE_DIR = BASE_DIR / "data" / "state"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def build_summary(date_key: str) -> dict:
    """生成 V2 建池摘要文本"""
    key = str(date_key).replace("-", "")

    # Load state files
    fixtures_path = STATE_DIR / f"selected_fixtures_{key}.json"
    predictions_path = REPORT_DIR / f"predictions_{key}.json"
    task_status_path = STATUS_DIR / "task_status_v2_daily_pool.json"

    selected = _load_json(fixtures_path)
    predictions = _load_json(predictions_path)
    task_status = _load_json(task_status_path)

    fixtures = selected.get("fixtures", {})
    pred_list = predictions if isinstance(predictions, list) else []
    total_matches = len(fixtures)

    # Read from DAILY_POOL's own output (daily.md has official classification)
    daily_md = REPORT_DIR / f"daily_{key}.md"
    bet_locked = 0
    watch_early = 0
    candidate = 0
    watch_high = 0
    skip_low = 0
    if daily_md.exists():
        md_text = daily_md.read_text()
        import re
        bm = re.search(r"BET_LOCKED[：:]\s*(\d+)", md_text)
        wm = re.search(r"WATCH_EARLY[：:]\s*(\d+)", md_text)
        cm = re.search(r"CANDIDATE[：:]\s*(\d+)", md_text)
        hm = re.search(r"WATCH_HIGH.*?[:：]\s*(\d+)", md_text)
        sm = re.search(r"SKIP_LOW.*?[:：]\s*(\d+)", md_text)
        if bm: bet_locked = int(bm.group(1))
        if wm: watch_early = int(wm.group(1))
        if cm: candidate = int(cm.group(1))
        if hm: watch_high = int(hm.group(1))
        if sm: skip_low = int(sm.group(1))
    
    # Get status from task_status
    ts_status = task_status.get("status", "UNKNOWN")
    ts_date = task_status.get("date", "")
    ts_duration = task_status.get("elapsed_seconds", 0)

    summary_lines = []
    summary_lines.append("【V2 量化系统】")
    summary_lines.append(f"📌 每日建池完成 · {key[:4]}-{key[4:6]}-{key[6:8]}")
    summary_lines.append("")
    summary_lines.append(f"扫描：{total_matches}场")
    summary_lines.append(f"BET_LOCKED：{bet_locked}")
    summary_lines.append(f"WATCH_EARLY：{watch_early}")
    summary_lines.append(f"CANDIDATE：{candidate}")
    if watch_high > 0:
        summary_lines.append(f"WATCH_HIGH(≥2.90)：{watch_high}")
    if skip_low > 0:
        summary_lines.append(f"SKIP_LOW(<2.00)：{skip_low}")
    summary_lines.append("")
    summary_lines.append(f"状态：{ts_status}")
    summary_lines.append("说明：建池阶段不锁定，BET_LOCKED 等待 T-90/T-45 窗口检查器。")

    summary_text = "\n".join(summary_lines)

    return {
        "date": key,
        "summary": summary_text,
        "total": total_matches,
        "bet_locked": bet_locked,
        "watch_early": watch_early,
        "candidate": candidate,
        "watch_high": watch_high,
        "skip_low": skip_low,
        "task_status": ts_status,
        "bad_fields": {
            "has_v33": any("V33" in str(v) for v in fixtures.values()),
            "has_hourly": any("HOURLY" in str(v) for v in fixtures.values()),
        },
    }


def push_to_qq(summary_text: str, date_key: str) -> bool:
    """通过 systemEvent 写入推送文件。实际发送由 Gateway 处理。"""
    try:
        msg_hash = hashlib.sha256(summary_text.encode()).hexdigest()[:16]
        now = datetime.now(LOCAL_TZ).isoformat()
        marker = {
            "date": date_key,
            "type": "v2_daily_pool_summary",
            "status": "SENT",
            "delivery": "qqbot",
            "version": "v2_daily_pool_summary_v1",
            "message_hash": msg_hash,
            "pushed_at": now,
            "source": "direct_script_systemEvent",
        }
        marker_path = STATUS_DIR / f"v2_daily_pool_push_{date_key}.json"
        STATUS_DIR.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")

        # Also write summary to status file for systemEvent pickup
        summary_path = STATUS_DIR / f"v2_daily_pool_summary_{date_key}.json"
        summary_data = {
            "summary": summary_text,
            "message_hash": msg_hash,
            "pushed_at": now,
        }
        summary_path.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[PUSH] ✅ marker written: {marker_path}", flush=True)
        print(f"[PUSH] ✅ summary file written: {summary_path}", flush=True)
        print(f"[PUSH] ⚠️ 实际QQ发送需由 systemEvent 通道完成", flush=True)
        return True
    except Exception as e:
        print(f"[PUSH] ❌ write error: {e}", flush=True)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true", help="仅输出，不推送")
    parser.add_argument("--push", action="store_true", help="推送")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    result = build_summary(date_key)

    print(result["summary"])

    if args.dry_run:
        print()
        print("--- dry-run (no push) ---")

    if args.push:
        print()
        ok = push_to_qq(result["summary"], date_key)
        if ok:
            print("[PUSH] ✅ push completed")
        else:
            print("[PUSH] ❌ push failed", flush=True)


if __name__ == "__main__":
    main()
