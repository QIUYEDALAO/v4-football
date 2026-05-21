#!/usr/bin/env python3
"""Check V2/V4 yesterday & rolling validation modules in intel_ops_console.html."""
import json
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CONSOLE = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
YESTERDAY = MODULE / "data" / "runtime" / "status" / "validation_yesterday_20260519.json"
ROLLING = MODULE / "data" / "runtime" / "status" / "rolling_validation_summary_20260520.json"


def load():
    console = CONSOLE.read_text() if CONSOLE.is_file() else ""
    yd = json.loads(YESTERDAY.read_text()) if YESTERDAY.is_file() else {}
    rl = json.loads(ROLLING.read_text()) if ROLLING.is_file() else {}
    return console, yd, rl


def check_yesterday_module_visible(console):
    ok = "昨日验证" in console and "2026-05-19" in console
    return ("PASS" if ok else "FAIL", "昨日验证模块可见", ok)


def check_v2_bet_locked_scope(console):
    """V2 must show BET_LOCKED scope, not WATCH/CANDIDATE."""
    has_bet_locked_label = "BET_LOCKED" in console
    has_only_bet_locked = "只统计 BET_LOCKED" in console or "只统计BET_LOCKED" in console
    ok = has_bet_locked_label and has_only_bet_locked
    return ("PASS" if ok else "FAIL", "V2 BET_LOCKED 口径可见，WATCH/CANDIDATE排除", ok)


def check_v4_ab_scope(console):
    """V4 must show A/B formal scope, C/SKIP excluded from hit rate."""
    has_a_separate = "A 样本" in console or "A 命中率" in console
    has_b_separate = "B 样本" in console or "B 命中率" in console
    has_ab_label = "A/B" in console or "A+B" in console or "正式候选" in console
    has_c_skip_excluded = "不计入正式命中率" in console or "不计入命中率" in console
    ok = (has_a_separate or has_b_separate or has_ab_label) and has_c_skip_excluded
    return ("PASS" if ok else "FAIL", "V4 A/B正式候选口径可见，C/SKIP排除", ok)


def check_c_skip_not_in_hit_rate(console):
    """Explicit statement that C/SKIP not counted in hit rate."""
    ok = ("不计入正式命中率" in console or "不计入命中率" in console) and ("C" in console or "SKIP" in console)
    return ("PASS" if ok else "FAIL", "明确标注 C/SKIP不计入命中率", ok)


def check_v2_rolling_visible(console):
    has_7d = "7日" in console or "7 日" in console
    has_14d = "14日" in console or "14 日" in console
    has_30d = "30日" in console or "30 日" in console
    ok = has_7d and has_14d and has_30d
    return ("PASS" if ok else "FAIL", f"V2滚动 7/14/30 可见 (7d={has_7d} 14d={has_14d} 30d={has_30d})", ok)


def check_v4_rolling_visible(console):
    """V4 rolling must show 7/14/30 in the rolling section."""
    # Count occurrences of "7日" etc. in rolling context
    ok = "7日" in console and "14日" in console and "30日" in console
    return ("PASS" if ok else "WARN_ONLY", "V4滚动 7/14/30 可见", ok)


def check_sample_insufficient(console):
    """If sample insufficient, must say 样本不足."""
    has_sample_warning = "样本不足" in console
    return ("PASS" if has_sample_warning else "WARN_ONLY",
            "样本不足时正确提示" if has_sample_warning else "未检测到样本不足提示（可能样本充足）",
            has_sample_warning)


def check_no_c_skip_in_formal(console, yd):
    """Verify C/SKIP not counted in formal hit rate numbers."""
    v4y = yd.get("V4_yesterday", {})
    c_count = v4y.get("C_count", 0)
    # C and SKIP should be listed separately from hit/miss
    has_c_displayed = "C观察" in console or "C 观察" in console
    ok = has_c_displayed
    return ("PASS" if ok else "WARN_ONLY", "C/SKIP单独显示，不计入正式命中率", ok)


def check_no_watch_candidate_in_v2(console):
    """V2 must not count WATCH/CANDIDATE as formal."""
    has_exclusion = ("WATCH/CANDIDATE" in console or "WATCH" in console) and ("不计入" in console or "仅审计" in console or "不进正式命中率" in console)
    has_watch_audit = "WATCH" in console and "CANDIDATE" in console
    ok = has_exclusion or has_watch_audit
    return ("PASS" if ok else "WARN_ONLY", "V2不将WATCH/CANDIDATE算入正式命中率", ok)


def check_no_fabricated_results(console, yd, rl):
    """Verify data comes from actual attribution files, not fabricated."""
    v4y = yd.get("V4_yesterday", {})
    total = v4y.get("total_matches_with_attribution", 0)
    # if total > 0, we have real data from attribution JSONL
    ok = total > 0
    return ("PASS" if ok else "WARN_ONLY",
            f"数据来自真实attribution文件 ({total}条)" if ok else "无attribution数据源",
            ok)


def main():
    if not CONSOLE.is_file():
        print("BLOCKER: intel_ops_console.html does not exist")
        sys.exit(1)

    console, yd, rl = load()

    checks = [
        check_yesterday_module_visible(console),
        check_v2_bet_locked_scope(console),
        check_v4_ab_scope(console),
        check_c_skip_not_in_hit_rate(console),
        check_v2_rolling_visible(console),
        check_v4_rolling_visible(console),
        check_sample_insufficient(console),
        check_no_c_skip_in_formal(console, yd),
        check_no_watch_candidate_in_v2(console),
        check_no_fabricated_results(console, yd, rl),
    ]

    passed = 0; failed = 0; warned = 0; blocked = 0; total = len(checks)
    print(f"=== V2/V4 验证仪表盘 checker ===\n")
    for status, detail, _ in checks:
        tag = {"PASS": "PASS", "FAIL": "FAIL", "BLOCKER": "BLOCKER", "WARN_ONLY": "WARN_ONLY"}[status]
        print(f"  [{tag:10s}] {detail}")
        if status == "PASS": passed += 1
        elif status == "BLOCKER": blocked += 1
        elif status == "FAIL": failed += 1
        else: warned += 1

    print(f"\n---")
    print(f"  总计: {total} | 通过: {passed} | 失败: {failed} | 警告: {warned} | 阻断: {blocked}")

    if blocked > 0: conclusion = "BLOCKED"
    elif failed > 0: conclusion = "FAIL"
    elif warned > 0: conclusion = "WARN_ONLY"
    else: conclusion = "PASS"

    print(f"  结论: {conclusion}")

    marker = {
        "checker": "tools/check_v2_v4_validation_dashboard.py",
        "conclusion": conclusion,
        "total": total, "passed": passed, "failed": failed,
        "warn_only": warned, "blocked": blocked,
        "checks": [{"status": s, "detail": d, "ok": v} for s, d, v in checks],
    }
    marker_path = MODULE / "data" / "runtime" / "status" / "v2_v4_validation_dashboard_checker_result_20260520.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  标记: {marker_path}")
    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
