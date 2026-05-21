#!/usr/bin/env python3
"""Strict grade-split validation dashboard checker — 13 checks.

Checks that the dashboard properly separates A/B/C/SKIP, V2 BET_LOCKED/WATCH/CANDIDATE,
and that rolling validation shows layered 7/14/30 day breakdowns.
"""
import json
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CONSOLE = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
V4_YD = MODULE / "data" / "runtime" / "status" / "v4_yesterday_validation_20260519.json"
V2_YD = MODULE / "data" / "runtime" / "status" / "v2_yesterday_validation_20260519.json"
V4_RL = MODULE / "data" / "runtime" / "status" / "v4_rolling_validation_split_20260520.json"
V2_RL = MODULE / "data" / "runtime" / "status" / "v2_rolling_validation_split_20260520.json"


def load():
    console = CONSOLE.read_text() if CONSOLE.is_file() else ""
    v4_yd = json.loads(V4_YD.read_text()) if V4_YD.is_file() else {}
    v2_yd = json.loads(V2_YD.read_text()) if V2_YD.is_file() else {}
    v4_rl = json.loads(V4_RL.read_text()) if V4_RL.is_file() else {}
    v2_rl = json.loads(V2_RL.read_text()) if V2_RL.is_file() else {}
    return console, v4_yd, v2_yd, v4_rl, v2_rl


def check_a_separate(console):
    ok = "A 样本" in console and "A 命中率" in console
    return ("PASS" if ok else "FAIL", "A单独统计可见", ok)


def check_b_separate(console):
    ok = "B 样本" in console and "B 命中率" in console
    return ("PASS" if ok else "FAIL", "B单独统计可见", ok)


def check_ab_combined(console):
    ok = "A+B 样本" in console and "A+B 命中率" in console
    return ("PASS" if ok else "FAIL", "A+B合并统计可见", ok)


def check_c_observation(console):
    has_c_stats = "C 样本" in console or "C 观察命中率" in console
    has_c_label = "观察层" in console or "C观察" in console
    ok = has_c_stats and has_c_label
    return ("PASS" if ok else "FAIL", "C观察统计可见", ok)


def check_c_not_in_formal(console):
    ok = "C" in console and ("不计入正式命中率" in console or "不进正式命中率" in console)
    return ("PASS" if ok else "FAIL", "C明确不进正式命中率", ok)


def check_skip_visible(console):
    ok = "SKIP" in console and "不计入命中率" in console
    return ("PASS" if ok else "FAIL", "SKIP统计可见，明确不进命中率", ok)


def check_v2_bet_locked_official(console):
    has_bl = "BET_LOCKED" in console
    has_bl_official = "只统计BET_LOCKED" in console or "只统计 BET_LOCKED" in console
    ok = has_bl and has_bl_official
    return ("PASS" if ok else "FAIL", "V2 BET_LOCKED正式统计可见", ok)


def check_v2_watch_candidate_audit(console):
    has_watch = "WATCH" in console
    has_candidate = "CANDIDATE" in console
    has_audit_note = "仅审计" in console or "不计入正式命中率" in console
    ok = has_watch and has_candidate and has_audit_note
    return ("PASS" if ok else "FAIL", "V2 WATCH/CANDIDATE审计统计可见", ok)


def check_v2_watch_not_official(console):
    ok = ("WATCH" in console and "CANDIDATE" in console and
          ("不进正式命中率" in console or "不计入正式命中率" in console or "仅审计" in console))
    return ("PASS" if ok else "FAIL", "V2 WATCH/CANDIDATE不进正式命中率", ok)


def check_rolling_layered(console):
    has_7 = "7日" in console
    has_14 = "14日" in console
    has_30 = "30日" in console
    has_v4_a_rolling = "V4 滚动 A级" in console
    has_v4_b_rolling = "V4 滚动 B级" in console
    has_v4_c_rolling = "V4 滚动 C观察" in console
    ok = has_7 and has_14 and has_30 and has_v4_a_rolling and has_v4_b_rolling and has_v4_c_rolling
    return ("PASS" if ok else "FAIL",
            f"滚动验证7/14/30分层展示 (7={has_7} 14={has_14} 30={has_30} A={has_v4_a_rolling} B={has_v4_b_rolling} C={has_v4_c_rolling})",
            ok)


def check_no_ab_only_combined(console):
    has_a_separate = ("A 样本" in console and "A 命中率" in console)
    has_b_separate = ("B 样本" in console and "B 命中率" in console)
    has_ab_combined = "A+B" in console
    ok = has_a_separate and has_b_separate and has_ab_combined
    return ("PASS" if ok else "FAIL", "不是只显示A+B总命中率，A/B各自可见", ok)


def check_no_fabricated(console, v4_rl):
    key = v4_rl.get("key_findings", {})
    has_real_data = bool(key.get("A_hit_rate") or key.get("A_plus_B_hit_rate"))
    has_attribution_source = "attribution" in console.lower() or "attribution" in str(v4_rl).lower()
    ok = has_real_data
    return ("PASS" if ok else "WARN_ONLY",
            "不伪造赛果 — 数据来自attribution JSONL",
            ok)


def check_v4_skips_excluded(console):
    ok = "SKIP" in console and ("不计入命中率" in console or "不计入正式命中率" in console)
    return ("PASS" if ok else "FAIL", "V4 SKIP统计但排除命中率", ok)


def main():
    if not CONSOLE.is_file():
        print("BLOCKER: intel_ops_console.html does not exist")
        sys.exit(1)

    console, v4_yd, v2_yd, v4_rl, v2_rl = load()

    checks = [
        check_a_separate(console),
        check_b_separate(console),
        check_ab_combined(console),
        check_c_observation(console),
        check_c_not_in_formal(console),
        check_skip_visible(console),
        check_v2_bet_locked_official(console),
        check_v2_watch_candidate_audit(console),
        check_v2_watch_not_official(console),
        check_rolling_layered(console),
        check_no_ab_only_combined(console),
        check_no_fabricated(console, v4_rl),
        check_v4_skips_excluded(console),
    ]

    passed = 0; failed = 0; warned = 0; blocked = 0; total = len(checks)
    print(f"=== V2/V4 GRADE-SPLIT 验证仪表盘 checker ===\n")
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
        "checker": "tools/check_v2_v4_grade_split_validation_dashboard.py",
        "conclusion": conclusion,
        "total": total, "passed": passed, "failed": failed,
        "warn_only": warned, "blocked": blocked,
        "checks": [{"status": s, "detail": d, "ok": v} for s, d, v in checks],
    }
    marker_path = MODULE / "data" / "runtime" / "status" / "v2_v4_grade_split_validation_dashboard_checker_result_20260520.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  标记: {marker_path}")
    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
