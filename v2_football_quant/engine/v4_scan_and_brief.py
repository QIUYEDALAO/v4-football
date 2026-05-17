#!/usr/bin/env python3
"""engine/v4_scan_and_brief.py — V4 supervisor（父进程）
============================================================
子进程 v4_scan_worker 跑扫描，父进程管 watchdog/简报/推送。
SIGKILL 时父进程存活并记录状态。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
LOG_DIR = BASE_DIR / "data" / "runtime" / "logs"
LOCK_DIR = BASE_DIR / "data" / "runtime" / "locks"
GLOBAL_LOCK = LOCK_DIR / "v4_scan_global.lock"
LOCAL_TZ = timezone(timedelta(hours=8))

FORBIDDEN_KEYWORDS = [
    "SECOND_HALF_OVER", "FULLTIME_OVER", "market_scores",
    "球探扫描结果", "高评分", "全场大球", "下半场大球", "V33",
    "皇冠半场盘口", "交叉参考", "按V33策略", "需独立分析",
    "另出独立分析", "是否需要我", "评分体系不同",
]
REQUIRED_KEYWORDS = [
    "A级上半场强推荐", "B级上半场达标推荐", "C级观察池",
    "HT_SKIP跳过", "无A/B上半场主推荐",
    # QQ精简格式兼容
    "V4上半场情报", "V4最终结论",
    "A级强推荐", "B级达标推荐", "C级观察",
    "跳过原因", "昨日验证",
]

HARD_TIMEOUT = 3600  # 60 min
SOFT_TIMEOUT = 1800  # 30 min


def _content_guard(text: str) -> bool:
    for kw in FORBIDDEN_KEYWORDS:
        if kw in text:
            print(f"[GUARD] BLOCKED: '{kw}'", flush=True)
            return False
    return any(kw in text for kw in REQUIRED_KEYWORDS)


def _sigmask_push(window: str, date: str, status: str, progress: str, reason: str) -> None:
    print("【V4 情报系统】", flush=True)
    print(f"""⛔ V4扫描被系统终止
窗口：{window}
日期：{date}
状态：{status}
进度：{progress}
原因：{reason}
处理：不生成正式简报，不读取半成品 scout
下一步：等待下一窗口或手动低负载重跑""", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--window", default="midday", choices=["midday","evening","night","late","early","manual"])
    parser.add_argument("--lookahead-hours", type=float, default=24.0)
    parser.add_argument("--push", default="always", choices=["always","conditional","never"])
    parser.add_argument("--scan-mode", default="fast", choices=["fast","full"])
    args = parser.parse_args()

    from engine.task_watchdog import v4_scan_watchdog

    # Global lock
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    if GLOBAL_LOCK.exists():
        stale_s = time.time() - GLOBAL_LOCK.stat().st_mtime
        if stale_s < HARD_TIMEOUT:
            wd = v4_scan_watchdog(args.window)
            wd.start(total_items=0)
            wd.finish(status="SKIPPED_GLOBAL_LOCK", error="v4_scan_global.lock active")
            print("【V4 情报系统】", flush=True)
            print("[WATCHDOG] V4 global scan lock active, SKIPPED_GLOBAL_LOCK", flush=True)
            return
        else:
            GLOBAL_LOCK.unlink(missing_ok=True)
    GLOBAL_LOCK.write_text(str(os.getpid()))

    wd = v4_scan_watchdog(args.window)
    wd.start(total_items=0)
    now = datetime.now(LOCAL_TZ)
    today_key = str(args.date).replace("-", "")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"v4_scan_{args.window}_{today_key}.log"

    try:
        with open(str(log_path), "w") as log_fh:
            child = subprocess.Popen(
                [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_scan_worker.py"),
                 "--date", args.date, "--window", args.window,
                 "--lookahead-hours", str(args.lookahead_hours),
                 "--scan-mode", args.scan_mode],
                stdout=log_fh, stderr=subprocess.STDOUT,
            )

            started_at = time.time()

            while child.poll() is None:
                elapsed = time.time() - started_at
                wd.heartbeat(current=0, total=0, item="worker running", api_calls=0)
                if elapsed > HARD_TIMEOUT:
                    child.terminate()
                    time.sleep(10)
                    if child.poll() is None:
                        child.kill()
                    GLOBAL_LOCK.unlink(missing_ok=True)
                    wd.finish(status="TIMEOUT", error="hard timeout, worker killed")
                    _sigmask_push(args.window, args.date, "TIMEOUT", "unknown", "hard timeout 60min")
                    return
                if elapsed > SOFT_TIMEOUT:
                    wd._write_status("DELAYED", "超过30分钟")
                time.sleep(30)

            rc = child.returncode

        if rc == -9:
            GLOBAL_LOCK.unlink(missing_ok=True)
            wd.finish(status="KILLED_SIGKILL", error="worker received SIGKILL, likely OOM")
            _sigmask_push(args.window, args.date, "KILLED_SIGKILL", "unknown", "worker SIGKILL")
            return

        if rc != 0:
            GLOBAL_LOCK.unlink(missing_ok=True)
            wd.finish(status="FAILED", error=f"worker exit code {rc}")
            return

        # Worker success — validate scout
        scout_path = REPORT_DIR / f"scout_v4_{today_key}.json"
        scout_ok = scout_path.exists() and scout_path.stat().st_size > 0 and \
                   datetime.fromtimestamp(scout_path.stat().st_mtime, tz=LOCAL_TZ) >= now

        if not scout_ok:
            GLOBAL_LOCK.unlink(missing_ok=True)
            wd.finish(status="FAILED", error="scout校验失败")
            return

        # Step 3: 生成双版本简报
        from engine.v4_openclaw_brief import build_brief
        from engine.v4_qq_formatter import format_qq
        
        brief_text = build_brief(args.date)
        brief_path = REPORT_DIR / f"v4_openclaw_brief_{today_key}.txt"
        brief_path.write_text(brief_text, encoding="utf-8")
        
        qq_text = format_qq(args.date, window=args.window)
        qq_path = REPORT_DIR / f"v4_openclaw_brief_qq_{today_key}.txt"
        qq_path.write_text(qq_text, encoding="utf-8")

        if not _content_guard(qq_text):
            GLOBAL_LOCK.unlink(missing_ok=True)
            wd.finish(status="FAILED", error="内容守卫拦截")
            return

        # ── 解析A/B数量 ──
        ab_count = 0
        import re
        a_match = re.search(r'A级.*?[：:]\s*(\d+)', qq_text)
        b_match = re.search(r'B级.*?[：:]\s*(\d+)', qq_text)
        if a_match:
            ab_count += int(a_match.group(1))
        if b_match:
            ab_count += int(b_match.group(1))
        # Fallback: check QQ brief text
        if ab_count == 0:
            m = re.search(r'A0\s*B(\d+)', qq_text)
            if m:
                ab_count = int(m.group(1))

        # ── 写入 push marker（无论delivery如何）──
        import hashlib
        marker_dir = REPORT_DIR / ".." / "data" / "runtime" / "status"
        marker_dir = marker_dir.resolve()
        marker_dir.mkdir(parents=True, exist_ok=True)
        now_ts = datetime.now(LOCAL_TZ).isoformat()
        msg_hash = hashlib.md5(qq_text.encode()).hexdigest()[:16]

        push_marker = {
            "date": today_key,
            "window": args.window,
            "template_id": "v4_scan_brief_qq_v1",
            "ab_count": ab_count,
            "status": "GENERATED",
            "ab_gt_zero": ab_count > 0,
            "message_hash": msg_hash,
            "brief_file": str(brief_path.name),
            "qq_file": str(qq_path.name),
            "generated_at": now_ts,
            "pushed": False,
            "reason": "pending_push" if ab_count > 0 else "no_ab",
        }
        push_marker_path = marker_dir / f"v4_scan_push_{today_key}_{args.window}.json"
        with open(push_marker_path, "w") as f:
            json.dump(push_marker, f, ensure_ascii=False, indent=2)

        # Push logic: 推送 QQ 版
        if args.push == "never":
            print("[WATCHDOG] brief generated, push skipped (never)", flush=True)
        elif args.push == "conditional":
            has_ab = "今日 V4 有 " in qq_text and "上半场推荐" in qq_text
            if has_ab:
                print(f"[PUSH] A/B={ab_count}>0, 简报已生成, push marker: {push_marker_path.name}", flush=True)
                print(qq_text, flush=True)
            else:
                print("[WATCHDOG] brief generated, push skipped (conditional: no A/B)", flush=True)
        else:
            print(f"[PUSH] A/B={ab_count}>0, 简报已生成, push marker: {push_marker_path.name}", flush=True)
            print(qq_text, flush=True)

        GLOBAL_LOCK.unlink(missing_ok=True)
        wd.finish(status="DONE", output_files={"scout": str(scout_path), "brief": str(brief_path), "brief_qq": str(qq_path), "scan_push": str(push_marker_path), "scan_log": str(log_path)})

    except Exception as e:
        GLOBAL_LOCK.unlink(missing_ok=True)
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
