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


def push_to_qqbot(summary_text: str, date_key: str) -> bool:
    """推送到 QQBOT 正式通道。

    QQ_DELIVERY_CONTRACT:
    - target_type 必须 == qqbot
    - target 必须 != agent:main:main
    - delivery_mode 不得为 announce
    - source 不得为 wake / agentTurn
    - 有 delivery success log 才能写 SENT
    - 否则写 WRONG_TARGET / QQBOT_TARGET_NOT_FOUND
    """
    msg_hash = hashlib.sha256(summary_text.encode()).hexdigest()[:16]
    now = datetime.now(LOCAL_TZ)

    # ── 尝试 QQBOT 正式通道 ──
    # 写法一：写 cron/systemEvent deliverable 文件
    try:
        # 写 summary 文件（供 cron/systemEvent 通道消费）
        summary_path = STATUS_DIR / f"v2_daily_pool_summary_{date_key}.json"
        STATUS_DIR.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps({
            "summary": summary_text,
            "message_hash": msg_hash,
            "created_at": now.isoformat(),
            "target_type": "qqbot",
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        # 尝试通过 QQ Bot 通道发送
        from engine import net_utils
        qq_target = "fbc6f797a5c3b6fe2680a8b25f95e143"
        # 写入推送标记
        marker_path = STATUS_DIR / f"v2_daily_pool_push_{date_key}.json"

        # 检查是否可验证 QQ delivery
        # 当前架构中，纯脚本无法直接调用 QQ Bot API。
        # 只能写 summary 文件 + marker，由 Gateway systemEvent 通道消费。
        # 因此标记为 PENDING_QQ_CONFIRMATION，不做 SENT。
        marker = {
            "date": date_key,
            "type": "v2_daily_pool_summary",
            "status": "PENDING_QQ_CONFIRMATION",
            "delivery": "qqbot",
            "version": "v2_daily_pool_summary_v1",
            "message_hash": msg_hash,
            "target_type": "qqbot",
            "target": qq_target,
            "source": "direct_script_qqbot",
            "qq_delivered": False,
            "created_at": now.isoformat(),
            "note": "等待 QQ Bot 通道确认 delivery success 后才能更新为 SENT",
        }
        marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[PUSH] ✅ qqbot summary file written: {summary_path}", flush=True)
        print(f"[PUSH] ✅ qqbot push marker written (PENDING): {marker_path}", flush=True)
        print(f"[PUSH] ⚠️ 等待 Gateway systemEvent 通道确认 delivery success", flush=True)
        return True
    except Exception as e:
        # 失败：写失败 marker
        fail_marker = {
            "date": date_key,
            "type": "v2_daily_pool_summary",
            "status": "QQBOT_TARGET_NOT_FOUND",
            "delivery": "qqbot",
            "reason": str(e)[:200],
            "source": "direct_script_qqbot",
            "qq_delivered": False,
        }
        fail_path = STATUS_DIR / f"v2_daily_pool_push_{date_key}.json"
        fail_path.write_text(json.dumps(fail_marker, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[PUSH] ❌ qqbot push failed: {e}", flush=True)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true", help="仅输出，不推送")
    parser.add_argument("--push", choices=["qq"], help="推送目标 qq=QQBOT")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    result = build_summary(date_key)

    print(result["summary"])

    if args.dry_run:
        print()
        print("--- dry-run (no push) ---")

    if args.push == "qq":
        print()
        ok = push_to_qqbot(result["summary"], date_key)
        if ok:
            print("[PUSH] ✅ qqbot push completed (pending confirmation)")
        else:
            print("[PUSH] ❌ qqbot push failed", flush=True)


if __name__ == "__main__":
    main()
