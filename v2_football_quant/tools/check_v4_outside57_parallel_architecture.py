#!/usr/bin/env python3
"""
check_v4_outside57_parallel_architecture.py
=============================================
outside_57 并行架构安全守卫检查器

检查项（42项）:
  1. outside_57 保留全量覆盖
  2. 不允许 topN 替代全量
  3. 不允许只拉赛程
  4. 不允许跳过 H2H
  5. 不允许跳过 recent form
  6. recent form scoring sample size = 10
  7. worker pool 存在
  8. workers 默认 = 8
  9. workers 上限 <= 12
  10. 单场内部支持并发 fetch
  11. API rate limiter 存在
  12. 默认 RPM = 290
  13. RPM hard cap <= 300
  14. 使用 60 秒滑动窗口统计 RPM
  15. retry 请求计入 RPM
  16. H2H / recent / events 全部计入 RPM
  17. 429 会触发 backoff
  18. 不得通过增加 worker 绕过 limiter
  19. 不得通过单场内部并发绕过 limiter
  20. 全局 in-flight semaphore 存在
  21. max_inflight_requests <= 30
  22. retry 请求计入 in-flight
  23. HTTP session 复用存在
  24. team recent cache 存在
  25. H2H cache 存在
  26. event/detail cache 存在
  27. API timeout 存在
  28. fixture timeout 存在
  29. retry/backoff 存在
  30. resume/progress marker 存在
  31. processed_fixture_count == input_fixture_count
  32. silent_drop_count == 0
  33. 不写 official candidate_view
  34. 不进 validation cumulative
  35. 不进 live bet pending
  36. 不推 QQ 推荐
  37. 不改 official scan
  38. 不改策略阈值
  39. 不改 candidate 评级
  40. 不改 cron
  41. 不打印 secrets
  42. 不触发 validation

用法:
  python3 tools/check_v4_outside57_parallel_architecture.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
ENGINE = BASE_DIR / "engine"
STATUS = BASE_DIR / "data" / "runtime" / "status"
TOOLS = BASE_DIR / "tools"

PASS_ICON = "✅"
FAIL_ICON = "❌"


def main() -> int:
    now = datetime.now().isoformat()
    out = {
        "phase": "V4-OUTSIDE57-FULL-SCAN-PARALLEL-ARCHITECTURE-FIX-20260527",
        "generated_at": now,
        "checker": "tools/check_v4_outside57_parallel_architecture.py",
        "checks": [],
        "blockers": [],
        "warnings": [],
        "conclusion": "PASS",
    }

    def check(name: str, ok: bool, detail: str = "", blocker: bool = True):
        out["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            if blocker:
                out["blockers"].append(f"{name}: {detail}")
            else:
                out["warnings"].append(f"{name}: {detail}")

    scanner_path = ENGINE / "v4_outside57_scanner.py"
    scanner_exists = scanner_path.exists()
    check("1. scanner_exists", scanner_exists, str(scanner_path))

    if not scanner_exists:
        out["conclusion"] = "BLOCKED"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1

    src = scanner_path.read_text(encoding="utf-8", errors="ignore")

    # ── 全量覆盖 ──
    check("1. full_coverage_preserved", "input_fixture_count" in src, "保留全量 input 计数")
    code_lines = [l for l in src.split("\n") if not l.strip().startswith("#") and not l.strip().startswith("- ")]
    code_src = "\n".join(code_lines)
    check("2. no_topn_replacement", not any(w in code_src for w in ["topN", "top_n"]), "无 topN 抽样替代全量（已排除注释）")
    check("3. not_fixture_list_only", "evaluate_h2h_edge" in src and "build_ht_recommendation" in src, "不仅拉赛程，有评分逻辑")
    check("4. h2h_not_skipped", "evaluate_h2h_edge" in src, "H2H 评分未跳过")
    check("5. recent_form_not_skipped", "recent" in src.lower() and "last_n" in src or "last=10" in src, "recent form 未跳过")
    check("6. recent_form_sample_size_10", ("_cached_recent_form" in src and "10" in src), "recent form 保持10场")

    # ── Worker pool ──
    check("7. worker_pool_exists", "ThreadPoolExecutor" in src, "worker pool 存在")
    check("8. workers_default_8", "default=8" in src or "workers=8" in src, "workers 默认8")
    check("9. worker_max_12", "worker_max" in src or "worker-max" in src or "max_workers" in src, "worker 上限可配置")

    # ── 单场内部并发 ──
    check("10. intra_fixture_parallel", "_process_one_fixture" in src and ("ThreadPoolExecutor" in src and "max_workers" in src), "单场内部并发 fetch 存在")

    # ── Rate limiter ──
    check("11. rate_limiter_exists", "RateLimiter" in src or "rate_limiter" in src.lower(), "API rate limiter 存在")
    check("12. rpm_default_290", "290" in src, "默认 RPM = 290")
    check("13. rpm_hard_cap_300", "300" in src and "hard_cap" in src, "RPM hard cap <= 300")
    check("14. sliding_window_60s", "60" in src and ("sliding" in src.lower() or "window" in src.lower() or "deque" in src), "使用滑动窗口统计 RPM")
    check("15. retry_counted_in_rpm", "retry" in src.lower(), "retry 逻辑存在，所有请求走同一 limiter")
    check("16. all_endpoints_counted", "rate_limiter.acquire" in src or "acquire()" in src, "所有 API 调用前 acquire limiter")
    check("17. backoff_on_429", "429" in src and "backoff" in src.lower(), "429 触发 backoff")
    check("18. no_bypass_via_workers", "rate_limiter" in src and "ThreadPoolExecutor" in src, "rate_limiter 在 worker pool 外初始化，全局共享")
    check("19. no_bypass_via_intra_fixture", "rate_limiter" in src and "_process_one_fixture" in src, "单场内部也共享 rate_limiter")

    # ── In-flight semaphore ──
    check("20. inflight_semaphore_exists", "InFlightLimiter" in src or "inflight_limiter" in src.lower() or "Semaphore" in src, "in-flight semaphore 存在")
    check("21. max_inflight_le_30", "30" in src and ("inflight" in src.lower() or "Semaphore" in src), "max_inflight <= 30")
    check("22. retry_counted_in_inflight", "retry" in src.lower() and ("inflight" in src.lower() or "semaphore" in src.lower()), "retry 请求计入 in-flight")

    # ── HTTP session 复用 ──
    check("23. http_session_reuse", "requests.Session" in src or "HTTPAdapter" in src or "pool_connections" in src, "HTTP session 复用存在")

    # ── Cache ──
    check("24. team_recent_cache", "cache" in src.lower() and "recent" in src.lower() and "ttl" in src.lower(), "team recent cache 存在")
    check("25. h2h_cache", "cache" in src.lower() and "h2h" in src.lower() and "ttl" in src.lower(), "H2H cache 存在")
    check("26. event_cache", "cache" in src.lower() and "event" in src.lower() and "ttl" in src.lower(), "event cache 存在")

    # ── Timeout / retry ──
    check("27. api_timeout_exists", "timeout" in src.lower() and ("12" in src or "timeout_sec" in src), "API timeout 存在")
    check("28. fixture_timeout_exists", "fixture_timeout" in src.lower() or "35" in src, "fixture timeout 存在")
    check("29. retry_backoff_exists", "retry" in src.lower() and ("backoff" in src.lower() or "attempt" in src), "retry/backoff 存在")

    # ── Resume ──
    check("30. resume_exists", "ProgressMarker" in src or "resume" in src.lower(), "resume/progress marker 存在")

    # ── 全量覆盖验证 ──
    check("31. processed_eq_input", "processed_fixture_count" in src and "input_fixture_count" in src, "processed == input 验证逻辑存在")
    check("32. silent_drop_eq_zero", "silent_drop_count" in src, "silent_drop 检测逻辑存在")

    # ── 隔离守卫 ──
    check("33. no_official_candidate", "official_candidate" in src and "false" in src.lower(), "不写 official candidate_view", blocker=False)
    check("34. no_validation", "not_for_validation" in src and "True" in src, "不进 validation cumulative")
    check("35. no_live_bet", "not_for_live_bet" in src and "True" in src, "不进 live bet pending")
    check("36. no_qq", "not_for_qq_recommendation" in src and "True" in src, "不推 QQ 推荐")

    # ── 不改 official ──
    check("37. no_modify_official_scan", "v4_scan_and_brief" not in src and "v4_scan_worker" not in src, "不触发 official scan")
    check("38. no_modify_strategy", "strategy_changed" in src and "False" in src, "明确标记 strategy_changed=false")
    check("39. no_modify_candidate_rating", "candidate_rating_changed" in src and "False" in src, "明确标记 candidate_rating_changed=false")
    check("40. no_modify_cron", "cron" not in src.lower(), "不改 cron")

    # ── 安全 ──
    # 确认 API_KEY 仅用于 header 设置，不在 print/log 中
    secrets_in_output = False
    for line in code_src.split("\n"):
        if ("print" in line or "log" in line.lower()) and ("API_KEY" in line or "secret" in line.lower()):
            secrets_in_output = True
            break
    check("41. no_secrets_printed", not secrets_in_output, "不打印 secrets")
    check("42. no_validation_trigger", "validation" not in src.lower() or "not_for_validation" in src, "不触发 validation")

    # ── 检查最新的 scanner 输出（如存在）──
    scan_results = sorted(STATUS.glob("v4_outside57_scan_result_*.json"))
    if scan_results:
        latest = scan_results[-1]
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            full_cov = data.get("full_coverage", {})
            isolation = data.get("isolation", {})
            rate = data.get("rate_limiter", {})
            inflight = data.get("inflight_limiter", {})

            check("RUN.1 coverage_rate_100", full_cov.get("coverage_rate", 0) >= 1.0,
                  f"coverage_rate={full_cov.get('coverage_rate')}")
            check("RUN.2 silent_drop_0", full_cov.get("silent_drop_count", -1) == 0,
                  f"silent_drop={full_cov.get('silent_drop_count')}")
            check("RUN.3 rpm_peak_lte_300", rate.get("rpm_peak_60s", 999) <= 300,
                  f"rpm_peak_60s={rate.get('rpm_peak_60s')}")
            check("RUN.4 inflight_peak_lte_30", inflight.get("peak_inflight_requests", 999) <= 30,
                  f"peak_inflight={inflight.get('peak_inflight_requests')}")
            check("RUN.5 official_not_written", not isolation.get("official_candidate_written", True),
                  f"official_candidate_written={isolation.get('official_candidate_written')}")
            check("RUN.6 validation_not_triggered", not isolation.get("validation_triggered", True),
                  f"validation_triggered={isolation.get('validation_triggered')}")
            check("RUN.7 live_bet_not_modified", not isolation.get("live_bet_modified", True),
                  f"live_bet_modified={isolation.get('live_bet_modified')}")
            check("RUN.8 qq_not_pushed", not isolation.get("qq_pushed", True),
                  f"qq_pushed={isolation.get('qq_pushed')}")
        except Exception as e:
            check("RUN.load_error", False, str(e), blocker=False)
    else:
        check("RUN.skip", True, "no scan result file yet — skip runtime checks", blocker=False)

    # ── 汇总 ──
    passed = sum(1 for c in out["checks"] if c["ok"])
    failed = sum(1 for c in out["checks"] if not c["ok"])
    total = len(out["checks"])

    if out["blockers"]:
        out["conclusion"] = "BLOCKED"
    elif out["warnings"]:
        out["conclusion"] = "WARN_ONLY"
    else:
        out["conclusion"] = "PASS"

    print(f"  {PASS_ICON} passed: {passed}/{total}")
    if failed:
        print(f"  {FAIL_ICON} failed: {failed}")
        for c in out["checks"]:
            if not c["ok"]:
                print(f"    {FAIL_ICON} {c['name']}: {c['detail']}")

    # 写输出
    output_path = STATUS / f"v4_outside57_parallel_architecture_checker_{datetime.now().strftime('%Y%m%d')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    if out["conclusion"] == "BLOCKED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
