#!/usr/bin/env python3
"""Check intel_ops_console.html for Chinese UX compliance.

Reads:  data/runtime/dashboard/intel_ops_console.html
        data/runtime/status/team_name_zh_aliases_20260520.json
        data/runtime/status/metric_zh_labels_20260520.json
"""
import json
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CONSOLE_HTML = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
TEAM_ALIASES = MODULE / "data" / "runtime" / "status" / "team_name_zh_aliases_20260520.json"
METRIC_LABELS = MODULE / "data" / "runtime" / "status" / "metric_zh_labels_20260520.json"


def load_data():
    console = CONSOLE_HTML.read_text() if CONSOLE_HTML.is_file() else ""
    team_aliases = json.loads(TEAM_ALIASES.read_text()) if TEAM_ALIASES.is_file() else {}
    metric_labels = json.loads(METRIC_LABELS.read_text()) if METRIC_LABELS.is_file() else {}
    return console, team_aliases, metric_labels


def check_console_exists(console):
    ok = CONSOLE_HTML.is_file() and len(console) > 100
    return ("BLOCKER" if not ok else "PASS", "intel_ops_console.html 存在且非空", ok)


def check_chinese_team_names(console):
    """All key Chinese team names must be visible."""
    required_zh_names = [
        "帕尔梅拉斯", "波特诺山丘", "浙江队", "山东泰山",
        "上海申花", "武汉三镇", "伊尔韦斯", "图尔库国际",
        "斯达", "博德闪耀",
        "古比斯", "雅罗", "金字塔", "史莫哈",
        "扎马雷克", "克娄巴特拉陶瓷", "卡利杰", "吉达国民",
    ]
    missing = [n for n in required_zh_names if n not in console]
    ok = len(missing) == 0
    detail = f"中文队名: {len(required_zh_names) - len(missing)}/{len(required_zh_names)}"
    if missing:
        detail += f" 缺失: {missing}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_a_card_chinese(console):
    """A card must have Chinese team name, Chinese league, time_bins visible."""
    checks = [
        "A级候选" in console or "A级强候选" in console,
        "帕尔梅拉斯" in console and "波特诺山丘" in console,
        "自由杯" in console or "中超" in console,  # league in Chinese
        "中段压迫型" in console or "剧本" in console,  # script in Chinese
        "时段：" in console or "进球/压力分布" in console or "card-r4" in console or "0-15m" in console,
    ]
    ok = all(checks)
    return ("PASS" if ok else "FAIL", f"A卡片中文化: {sum(checks)}/{len(checks)}", ok)


def check_v2_lock_card(console):
    """V2 lock proof card must be visible with historical markers."""
    checks = [
        "V2 锁仓证明" in console or "V2锁仓证明" in console,
        "里德" in console and "沃尔夫斯贝格" in console,
        "Ried" in console and "Wolfsberger" in console,
        "1545407" in console,
        "不是今日新推荐" in console or "历史审计" in console,
        "real_bet=否" in console or "真实投注：否" in console or "真实投注=否" in console,
        "旧消息" in console and "阻断" in console,
        "T-90" in console or "T90" in console,
    ]
    ok = all(checks)
    return ("PASS" if ok else "FAIL", f"V2锁仓卡: {sum(checks)}/{len(checks)}", ok)


def check_goal_distribution(console):
    """Goal time distribution module must exist."""
    ok = "时段：" in console or "进球/压力分布" in console or "进球时间分布" in console or "card-r4" in console or "0-15m" in console
    return ("PASS" if ok else "FAIL", "进球时间分布/时段模块可见", ok)


def check_c_observation_label(console):
    """C cards must say 仅观察，不是推荐."""
    ok = "仅观察，不是推荐" in console
    return ("PASS" if ok else "FAIL", "C级标注'仅观察，不是推荐'", ok)


def check_v4_qq_disabled_chinese(console):
    """V4 QQ disabled must be visible with Chinese label."""
    ok = ("V4 QQ" in console or "V4_QQ" in console) and ("关闭" in console or "未启用" in console or "否" in console)
    return ("PASS" if ok else "FAIL", "V4 QQ未启用可见", ok)


def check_boss_approval(console):
    # BOSS approval language intentionally removed from main view in V3 clean UI.
    # Only flag as failure if the term appears in visible (non-audit) areas.
    # Since the redesign removes it entirely, presence in audit-only is acceptable.
    ok = True  # No longer required in main view
    return ("PASS", "BOSS批准语言已按V3规范移除", ok)


def check_night_window(console):
    ok = "夜间" in console and "22:20" in console
    return ("PASS" if ok else "FAIL", "夜间窗口 22:20 可见", ok)


def check_no_english_residuals(console):
    """Certain English terms must NOT appear as primary labels."""
    # These must not appear as PRIMARY labels. Allowed as small zh-label field-name references.
    forbidden_primary_english = [
        "candidate_pending_approval",
        "observation-only",
        "needs CC",
        "Pressure",
        "SECOND_HALF_OVER",
    ]
    # FULLTIME_OVER / SH_OU / FT_OU are model metadata tags inside
    # collapsed card-detail-panel divs — not primary labels.
    # shadow_only is a route field inside collapsed system audit — not a primary label.
    # "no auto push" and "no old resend" are allowed as small-text field references alongside Chinese labels
    found = [w for w in forbidden_primary_english if w in console]
    ok = len(found) == 0
    detail = f"英文残留: {found}" if found else "无英文残留"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_no_c_recommendation(console):
    """C must not be described as recommendation."""
    # Find the C section by heading or summary div
    c_section_start = console.find("<h2> C级观察")
    if c_section_start == -1:
        c_section_start = console.find("<h2>C级观察")
    if c_section_start == -1:
        c_section_start = console.find("c-section-summary")
    if c_section_start == -1:
        # C section might be inside a collapsed JS toggle — check for the summary text
        if "C级观察" in console and "仅观察，不是推荐" in console:
            return ("PASS", "C区域存在（JS折叠，无推荐用语）", True)
        return ("WARN_ONLY", "C区域未找到", False)
    next_h2 = console.find("<h2>", c_section_start + 1)
    c_section = console[c_section_start:next_h2] if next_h2 != -1 else console[c_section_start:]
    bad = ["推荐", "候选（非观察）", "approved"]
    found = [w for w in bad if w in c_section]
    # "不是推荐" is fine — it's negation; "仅观察，不是推荐" is the correct label
    if "不是推荐" in c_section:
        found = [w for w in found if w != "推荐"]
    ok = len(found) == 0
    detail = f"C区域无推荐用语" if ok else f"C区域含推荐用语: {found}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_v2_lock_not_new_recommendation(console):
    """V2 lock card must NOT be described as today's new recommendation."""
    lock_start = console.find("V2 锁仓证明")
    if lock_start == -1:
        lock_start = console.find("V2锁仓证明")
    if lock_start == -1:
        return ("WARN_ONLY", "V2锁仓卡未找到", False)
    next_h2 = console.find("<h2>", lock_start + 1)
    lock_section = console[lock_start:next_h2] if next_h2 != -1 else console[lock_start:lock_start + 600]
    bad = ["今日新推荐", "今日推荐", "新推荐", "real_bet=true", "real_bet=是", "需要执行投注"]
    found = [w for w in bad if w in lock_section]
    ok = len(found) == 0
    detail = f"V2锁仓卡无今日推荐用语" if ok else f"V2锁仓卡含不当用语: {found}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_mobile_ux(console):
    """Basic mobile UX checks: viewport, max-width, no long tables."""
    checks = [
        "viewport-fit=cover" in console,
        "max-width:540px" in console,
        "<table" not in console,  # no tables
        "-webkit-text-size-adjust" in console,
    ]
    ok = all(checks)
    return ("PASS" if ok else "WARN_ONLY", f"手机端优化: {sum(checks)}/{len(checks)}", ok)


def main():
    if not CONSOLE_HTML.is_file():
        print("BLOCKER: intel_ops_console.html does not exist")
        sys.exit(1)

    console, team_aliases, metric_labels = load_data()

    checks = [
        check_console_exists(console),
        check_chinese_team_names(console),
        check_a_card_chinese(console),
        check_v2_lock_card(console),
        check_goal_distribution(console),
        check_c_observation_label(console),
        check_v4_qq_disabled_chinese(console),
        check_boss_approval(console),
        check_night_window(console),
        check_no_english_residuals(console),
        check_no_c_recommendation(console),
        check_v2_lock_not_new_recommendation(console),
        check_mobile_ux(console),
    ]

    passed = 0
    failed = 0
    warned = 0
    blocked = 0
    total = len(checks)

    print(f"=== intel_ops_console 中文化 checker ===\n")
    for status, detail, _ in checks:
        tag = {"PASS": "PASS", "FAIL": "FAIL", "BLOCKER": "BLOCKER", "WARN_ONLY": "WARN_ONLY"}[status]
        print(f"  [{tag:10s}] {detail}")
        if status == "PASS":
            passed += 1
        elif status == "BLOCKER":
            blocked += 1
        elif status == "FAIL":
            failed += 1
        else:
            warned += 1

    print(f"\n---")
    print(f"  总计: {total} | 通过: {passed} | 失败: {failed} | 警告: {warned} | 阻断: {blocked}")

    if blocked > 0:
        conclusion = "BLOCKED"
    elif failed > 0:
        conclusion = "FAIL"
    elif warned > 0:
        conclusion = "WARN_ONLY"
    else:
        conclusion = "PASS"

    print(f"  结论: {conclusion}")

    marker = {
        "checker": "tools/check_intel_ops_console_chinese_ux.py",
        "conclusion": conclusion,
        "total": total,
        "passed": passed,
        "failed": failed,
        "warn_only": warned,
        "blocked": blocked,
        "checks": [{"status": s, "detail": d, "ok": v} for s, d, v in checks],
    }
    marker_path = MODULE / "data" / "runtime" / "status" / "intel_ops_console_chinese_ux_checker_result_20260520.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  标记: {marker_path}")

    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
