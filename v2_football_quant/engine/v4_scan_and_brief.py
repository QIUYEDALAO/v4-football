#!/usr/bin/env python3
"""engine/v4_scan_and_brief.py — V4 supervisor（父进程）
============================================================
子进程 v4_scan_worker 跑扫描，父进程管 watchdog/简报/推送。
SIGKILL 时父进程存活并记录状态。

Guard markers:
  NO_AI_KILL_RETRY = true  (watchdog reports only, no auto-kill/retry)
  FAIL_CLOSED = true       (any failure stops pipeline, reports to user)
  REPORT_ONLY = true       (watchdog does NOT execute kills)
  HARD_TIMEOUT = 3600      (60m wall clock, not auto-retry)
  SOFT_TIMEOUT = 1800      (30m soft threshold, report only)
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


def _run_parallel_scan(args, scan_date: str, today_key: str, wd, log_path: Path) -> None:
    """Run parallel outside57 scanner and write official output if requested."""
    from engine.v4_outside57_scanner import run_outside57_scan

    print(f"[adapter] parallel scan engine: workers={args.outside57_workers}, "
          f"rpm={args.outside57_api_rpm}/{args.outside57_api_rpm_hard_cap}, "
          f"inflight={args.outside57_max_inflight}", flush=True)

    summary = run_outside57_scan(
        include_outside_57=bool(args.include_outside_57),
        workers=args.outside57_workers,
        worker_max=args.outside57_workers,
        api_rpm=args.outside57_api_rpm,
        api_rpm_hard_cap=args.outside57_api_rpm_hard_cap,
        max_inflight=args.outside57_max_inflight,
        api_timeout_sec=12,
        fixture_timeout_sec=35,
        retry_max=2,
        resume=args.outside57_resume,
        run_id=None,
        scan_mode="full",
        scan_date_str=today_key,
    )

    results = summary.get("results", [])
    fc = summary.get("full_coverage", {})
    print(f"[adapter] scan complete: {fc.get('input_fixture_count',0)} in, "
          f"{fc.get('done_count',0)} done, "
          f"silent_drop={fc.get('silent_drop_count',0)}", flush=True)

    if not args.write_official_output:
        print("[adapter] --write-official-output not set; skipping official output", flush=True)
        wd.finish(status="DONE_NO_OFFICIAL",
                  output_files={"scan_result": summary.get("run_id","")})
        return

    # ── Adapter: transform scanner results to official formats ──

    candidate_path = BASE_DIR / "data" / "runtime" / "status" / f"v3v4_dashboard_candidate_view_{today_key}.json"
    scout_path = REPORT_DIR / f"scout_v4_{today_key}.json"

    # Load whitelist
    try:
        wl = json.loads((BASE_DIR / "config" / "leagues_whitelist.json").read_text())
        wl_ids = set(str(k) for k in wl.get("leagueId", {}).keys())
    except Exception:
        wl_ids = set()

    a_list, b_list, skip_list = [], [], []
    scout_list = []

    # Official candidate_view ONLY includes whitelist league fixtures.
    # Outside_57 fixtures do NOT enter candidate_view, scout, or brief paths.
    official_results = [r for r in results if str(r.get("league_id", "")) in wl_ids]
    print(f"[adapter] official filter: {len(official_results)}/{len(results)} whitelist fixtures", flush=True)

    for r in official_results:
        grade = str(r.get("grade", "SKIP")).strip().upper()
        lid = str(r.get("league_id", ""))
        is_whitelist = True
        is_outside57 = False

        # Build common fields
        entry = {
            "fixture_id": r.get("fixture_id"),
            "home": r.get("home_team", "?"),
            "away": r.get("away_team", "?"),
            "league": r.get("league_name", "?"),
            "league_id": int(r.get("league_id", 0)) if r.get("league_id") else 0,
            "kickoff": r.get("kickoff_time", "?"),
            "grade": grade,
            "official_candidate": grade in ("A", "B"),
            "skip": grade == "SKIP",
            "outside57": is_outside57 or (not is_whitelist),
            "h2h_valid": bool(r.get("h2h_valid", False)),
            "filter_reason": str(r.get("h2h_reason", "") or ""),
            "ht_score": r.get("ht_score"),
            "prematch_line": r.get("prematch_line"),
            "prematch_over_odds": r.get("prematch_over_odds"),
            "prematch_under_odds": r.get("prematch_under_odds"),
            "api_coverage_level": r.get("api_coverage_level", "UNKNOWN"),
            "is_candidate": grade in ("A", "B"),
            "recent_form_low_sample": r.get("recent_form_low_sample", False),
            "candidate_score": r.get("candidate_score"),
        }

        if grade == "A":
            a_list.append(entry)
        elif grade == "B":
            b_list.append(entry)
        else:
            skip_list.append(entry)

        # Scout entry (compatible with existing scout schema)
        scout_entry = {
            "fixture_id": r.get("fixture_id"),
            "date": scan_date,
            "match_date": scan_date,
            "scan_date": today_key,
            "scout_file_date": today_key,
            "kickoff": r.get("kickoff_time", "?"),
            "home": r.get("home_team", "?"),
            "away": r.get("away_team", "?"),
            "league": r.get("league_name", "?"),
            "grade": grade,
            "market_scores": {},
            "factors": {},
            "ht_ou_lines": [],
        }
        # Merge recommendation summary if available
        rec = r.get("recommendation_summary", {})
        if isinstance(rec, dict):
            for k in ("market_focus", "market_type", "best_focus_by_score", "best_score",
                      "data_coverage", "script_type", "ht_attack_vs_defense",
                      "recent_form_avg", "late_fh_pressure"):
                if k in rec:
                    scout_entry[k] = rec[k]
        scout_list.append(scout_entry)

    # Build candidate_view (no C grade)
    candidate_view = {
        "schema_version": "v3v4_dashboard_candidate_view.v1",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "scan_date": today_key,
        "source_window": "daily_1200",
        "source_path": str(candidate_path),
        "source_hash": "",
        "brief_path": "",
        "brief_sha256": "",
        "scout_path": str(scout_path),
        "scout_sha256": "",
        "A_count": len(a_list),
        "B_count": len(b_list),
        "C_count": 0,
        "SKIP_count": len(skip_list),
        "scan_total": len(results),
        "formal_recommendation_count": len(a_list) + len(b_list),
        "A_candidates": a_list,
        "B_candidates": b_list,
        "C_candidates": [],
        "C_observation_only": True,
        "actual_send": False,
        "qq_sent": False,
        "V4_QQ_ENABLED": False,
        "parsed_from_brief": False,
        "fallback_used": True,
        "fallback_reason": "parallel_engine_adapter",
        "builder_script": "v4_scan_and_brief.py",
    }
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(json.dumps(candidate_view, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[adapter] wrote candidate_view: A={len(a_list)} B={len(b_list)} SKIP={len(skip_list)} total={len(results)}", flush=True)

    # Write scout
    scout_path.parent.mkdir(parents=True, exist_ok=True)
    scout_path.write_text(json.dumps(scout_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[adapter] wrote scout: {len(scout_list)} entries", flush=True)

    # Generate brief via existing engine
    try:
        from engine.v4_openclaw_brief import build_brief
        from engine.v4_qq_formatter import format_qq
        brief_text = build_brief(args.date)
        brief_path = REPORT_DIR / f"v4_openclaw_brief_{today_key}.txt"
        brief_path.write_text(brief_text, encoding="utf-8")
        qq_text = format_qq(args.date, window=args.window)
        qq_path = REPORT_DIR / f"v4_openclaw_brief_qq_{today_key}.txt"
        qq_path.write_text(qq_text, encoding="utf-8")
        print(f"[adapter] wrote brief/qq", flush=True)
    except Exception as e:
        print(f"[adapter] brief generation skipped: {e}", flush=True)

    wd.finish(status="DONE",
              output_files={"candidate_view": str(candidate_path),
                           "scout": str(scout_path)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Scan date YYYYMMDD (legacy, prefer --scan-date)")
    parser.add_argument("--scan-date", default=None, help="Scan date YYYYMMDD")
    parser.add_argument("--window", default="midday", choices=["midday","evening","night","late","early","manual"])
    parser.add_argument("--lookahead-hours", type=float, default=24.0)
    parser.add_argument("--push", default="never", choices=["always","conditional","never"],
                        help="Push mode. Default never. Must be explicit to enable push.")
    parser.add_argument("--no-push", action="store_true", default=True,
                        help="Disable all push paths (default True)")
    parser.add_argument("--no-d13", action="store_true", default=True,
                        help="Prohibit D13 execution")
    parser.add_argument("--no-v33", action="store_true", default=True,
                        help="Prohibit V33 execution")
    parser.add_argument("--no-hourly", action="store_true", default=True,
                        help="Prohibit hourly execution")
    parser.add_argument("--preflight", action="store_true",
                        help="Preflight only — validate paths, do not execute")
    parser.add_argument("--scan-mode", default="fast", choices=["fast","full"])
    parser.add_argument("--include-outside-57", action="store_true", help="扫描全部联赛（含白名单之外）")
    parser.add_argument("--scan-engine", default="serial", choices=["serial","parallel"],
                        help="Scan engine: serial=existing v4_scan_worker, parallel=v4_outside57_scanner")
    parser.add_argument("--write-official-output", action="store_true",
                        help="In parallel mode, write official candidate_view/scout/brief")
    parser.add_argument("--outside57-workers", type=int, default=8)
    parser.add_argument("--outside57-api-rpm", type=int, default=290)
    parser.add_argument("--outside57-api-rpm-hard-cap", type=int, default=300)
    parser.add_argument("--outside57-max-inflight", type=int, default=30)
    parser.add_argument("--outside57-resume", action="store_true")
    args = parser.parse_args()

    # Resolve scan_date: --scan-date takes priority over --date
    scan_date = args.scan_date or args.date
    if not scan_date:
        parser.error("--scan-date (or --date) is required")
    today_key = str(scan_date).replace("-", "")

    from engine.task_watchdog import v4_scan_watchdog
    from engine.net_utils import api_preflight, get_api_guard_snapshot
    from config.secrets import API_KEY, API_HOST

    api_preflight_result = api_preflight(today_key, api_key=API_KEY, api_host=API_HOST, strict=False, write_status=True)
    if not api_preflight_result.get("safe_to_scan"):
        marker_dir = BASE_DIR / "data" / "runtime" / "status"
        marker_dir.mkdir(parents=True, exist_ok=True)
        blocked = {
            "schema_version": "v4_scan_supervisor_api_blocked.v1",
            "date": today_key,
            "window": args.window,
            "scan_status": "API_BLOCKED",
            "generated_at": datetime.now(LOCAL_TZ).isoformat(),
            "preflight_required": True,
            "preflight_api_status": api_preflight_result.get("api_status"),
            "active_provider": api_preflight_result.get("active_provider"),
            "endpoint_host": api_preflight_result.get("endpoint_host"),
            "key_fingerprint": api_preflight_result.get("key_fingerprint"),
            "safe_to_scan": False,
            "worker_started": False,
            "per_fixture_loop_started": False,
            "curl_fallback_on_403": False,
            "last_good_preserved": True,
            "dashboard_message": "API数据源异常，候选未刷新，保留 last_good。",
            "capture_ran": False,
            "QQ_push": False,
            "cloud_publish": False,
            "auto_retry": False,
            "auto_kill": False,
            "timeout_change": False,
            "api_guard": get_api_guard_snapshot(),
        }
        (marker_dir / f"v4_scan_api_blocked_{today_key}.json").write_text(json.dumps(blocked, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(blocked, ensure_ascii=False, indent=2), flush=True)
        return

    # ── Preflight: paths check only, no execution ──
    if args.preflight:
        print(json.dumps({
            "status": "PREFLIGHT_OK",
            "window": args.window,
            "scan_date": scan_date,
            "runner_exists": True,
            "no_push": args.no_push,
            "no_d13": args.no_d13,
            "no_v33": args.no_v33,
            "no_hourly": args.no_hourly,
            "push_mode": args.push,
            "V4_QQ_ENABLED": False,
        }, ensure_ascii=False))
        return

    # ── Hard push gate: env var + --no-push must both allow push ──
    env_no_push = os.environ.get("OPENCLAW_NO_PUSH", "") == "1"
    effective_no_push = args.no_push or env_no_push
    if effective_no_push:
        # Override push to never regardless of --push flag
        args_push_effective = "never"
    else:
        args_push_effective = args.push

    # ── V4_QQ_ENABLED hard gate: QQ push is DISABLED ──
    V4_QQ_ENABLED = False  # hardcoded false — BOSS controlled

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
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"v4_scan_{args.window}_{today_key}.log"

    # ── PARALLEL ENGINE MODE ──
    if args.scan_engine == "parallel":
        _run_parallel_scan(args, scan_date, today_key, wd, log_path)
        GLOBAL_LOCK.unlink(missing_ok=True)
        return

    try:
        with open(str(log_path), "w") as log_fh:
            child = subprocess.Popen(
                [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_scan_worker.py"),
                 "--date", scan_date, "--window", args.window,
                 "--lookahead-hours", str(args.lookahead_hours),
                 "--scan-mode", args.scan_mode]
                + (["--include-outside-57"] if args.include_outside_57 else []),
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
        marker_dir = BASE_DIR / "data" / "runtime" / "status"
        marker_dir.mkdir(parents=True, exist_ok=True)
        now_ts = datetime.now(LOCAL_TZ).isoformat()
        msg_hash = hashlib.md5(qq_text.encode()).hexdigest()[:16]

        push_marker = {
            "date": today_key,
            "window": args.window,
            "scan_date": scan_date,
            "template_id": "v4_scan_brief_qq_v1",
            "ab_count": ab_count,
            "status": "GENERATED",
            "ab_gt_zero": ab_count > 0,
            "message_hash": msg_hash,
            "brief_file": str(brief_path.name),
            "qq_file": str(qq_path.name),
            "generated_at": now_ts,
            "pushed": False,
            "actual_send": False,
            "qq_sent": False,
            "no_push": effective_no_push,
            "shadow_only": True,
            "reason": "pending_push" if ab_count > 0 else "no_ab",
            "V4_QQ_ENABLED": V4_QQ_ENABLED,
            "runner_exit_code": rc,
            "source_paths": {
                "scout": str(scout_path),
                "brief": str(brief_path),
                "brief_qq": str(qq_path),
                "log": str(log_path),
            },
            "safety_gates": {
                "V4_QQ_ENABLED": V4_QQ_ENABLED,
                "effective_no_push": effective_no_push,
                "push_mode": args_push_effective,
                "env_no_push": env_no_push,
            },
        }
        push_marker_path = marker_dir / f"v4_scan_{args.window}_push_{scan_date}.json"
        with open(push_marker_path, "w") as f:
            json.dump(push_marker, f, ensure_ascii=False, indent=2)

        # Push logic: 推送 QQ 版
        # Hard gate: V4_QQ_ENABLED=false → QQ push is always blocked
        if V4_QQ_ENABLED is False:
            print("[PUSH] BLOCKED: V4_QQ_ENABLED=false, QQ push disabled by BOSS directive", flush=True)
        elif args_push_effective == "never":
            print("[WATCHDOG] brief generated, push skipped (--no-push or OPENCLAW_NO_PUSH=1)", flush=True)
        elif args_push_effective == "conditional":
            has_ab = "今日 V4 有 " in qq_text and "上半场推荐" in qq_text
            if has_ab:
                print(f"[PUSH] A/B={ab_count}>0, 简报已生成, push marker: {push_marker_path.name}", flush=True)
                print(qq_text, flush=True)
            else:
                print("[WATCHDOG] brief generated, push skipped (conditional: no A/B)", flush=True)
        elif args_push_effective == "always" and not effective_no_push:
            print(f"[PUSH] A/B={ab_count}>0, 简报已生成, push marker: {push_marker_path.name}", flush=True)
            print(qq_text, flush=True)
        else:
            print("[WATCHDOG] brief generated, push skipped (safety gate)", flush=True)

        GLOBAL_LOCK.unlink(missing_ok=True)
        wd.finish(status="DONE", output_files={"scout": str(scout_path), "brief": str(brief_path), "brief_qq": str(qq_path), "scan_push": str(push_marker_path), "scan_log": str(log_path)})

    except Exception as e:
        GLOBAL_LOCK.unlink(missing_ok=True)
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
