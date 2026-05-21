#!/usr/bin/env python3
"""Check V4 script & goal-time distribution in intel_ops_console.html.

Reads:  data/runtime/dashboard/intel_ops_console.html
        data/runtime/status/intel_desk_v4_candidate_view_20260520.json
"""
import json
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CONSOLE_HTML = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
CANDIDATE_JSON = MODULE / "data" / "runtime" / "status" / "intel_desk_v4_candidate_view_20260520.json"

TAXONOMY_JSON = MODULE / "data" / "runtime" / "status" / "v4_script_taxonomy_20260520.json"

def _load_taxonomy():
    if TAXONOMY_JSON.is_file():
        t = json.loads(TAXONOMY_JSON.read_bytes())
        return list(t.get("scripts", {}).keys())
    return [
        "开局冲击型", "慢热绝杀型", "开局冲击型（高压）",
        "中段压迫型", "中后段发力型",
        "均衡持续型", "双峰拉扯型", "低压观察型",
        "数据不足",
    ]

ALLOWED_SCRIPTS = _load_taxonomy()

FORBIDDEN_AS_SCRIPT = [
    "FULLTIME_OVER", "SECOND_HALF_OVER", "SH_OU", "FT_OU",
]


def load_data():
    console = CONSOLE_HTML.read_text() if CONSOLE_HTML.is_file() else ""
    model = json.loads(CANDIDATE_JSON.read_text()) if CANDIDATE_JSON.is_file() else {}
    return console, model


def check_script_label_visible(console):
    """A and B cards must show 剧本："""
    ok = "剧本：" in console
    count = console.count("剧本：")
    return ("PASS" if ok else "FAIL",
            f"'剧本：' 在页面出现 {count} 次", ok)


def check_time_distribution_visible(console):
    """A and B cards must show 时段：0-15m or fallback."""
    ok = "时段：" in console or "card-r4" in console or "0-15m" in console
    count = console.count("时段：") + console.count("card-r4")
    return ("PASS" if ok else "FAIL",
            f"'时段：' 在页面出现 {console.count('时段：')} 次, time_bins via card-r4={console.count('card-r4')}", ok)


def check_missing_distribution_handled(console, model):
    """If distribution unavailable → must show 暂无完整时间分布数据. If available → must NOT show it."""
    has_missing = "暂无完整时间分布数据" in console
    # Check if data is actually available
    a = model.get("A_candidate", {})
    a_dist = a.get("goal_time_distribution", {}) or {}
    b_list = model.get("B_candidates", [])
    any_available = a_dist.get("available", False)
    for b in b_list:
        if (b.get("goal_time_distribution", {}) or {}).get("available", False):
            any_available = True
            break
    if any_available:
        # Data is available → placeholder MUST NOT appear
        ok = not has_missing
        return ("PASS" if ok else "FAIL",
                "分布数据可用，不应出现'暂无完整时间分布数据'" + (" (但出现了)" if has_missing else ""), ok)
    else:
        # Data unavailable → placeholder MUST appear
        return ("PASS" if has_missing else "FAIL",
                "分布数据不可用，应显示'暂无完整时间分布数据'" + (" (缺失)" if not has_missing else ""), has_missing)


def check_no_fulltime_over_as_script(console):
    """FULLTIME_OVER must NOT appear as script name (only as model tag)."""
    # Check if FULLTIME_OVER appears in cs class (the script line)
    import re
    cs_lines = re.findall(r'<div class="cs">(.*?)</div>', console)
    for line in cs_lines:
        for forbidden in FORBIDDEN_AS_SCRIPT:
            if forbidden in line:
                return ("FAIL",
                        f"剧本行出现禁止的标签: {forbidden} in '{line[:80]}'", False)
    return ("PASS", "剧本行无 FULLTIME_OVER/SH_OU/FT_OU 作为剧本名称", True)


def check_no_sh_ou_ft_ou_as_script(console):
    """SH_OU and FT_OU must NOT appear in the cs/script line."""
    import re
    cs_lines = re.findall(r'<div class="cs">(.*?)</div>', console)
    for line in cs_lines:
        for forbidden in ["SH_OU", "FT_OU"]:
            if forbidden in line:
                return ("FAIL",
                        f"剧本行出现禁止的标签: {forbidden} in '{line[:80]}'", False)
    return ("PASS", "剧本行无 SH_OU/FT_OU 作为剧本名称", True)


def check_script_types_in_allowlist(console):
    """All script types displayed must be in the allowed list."""
    import re
    script_matches = re.findall(r'剧本：([^<\s]+)', console)
    bad = [s for s in script_matches if s not in ALLOWED_SCRIPTS]
    ok = len(bad) == 0
    detail = f"剧本类型: {script_matches}"
    if bad:
        detail += f" 不在允许列表: {bad}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_c_is_observation(console):
    """C cards must still say 仅观察，不是推荐."""
    ok = "仅观察，不是推荐" in console
    return ("PASS" if ok else "FAIL",
            "C级卡片标注 '仅观察，不是推荐'", ok)


def check_no_fabricated_distribution(console, model):
    """Verify we don't claim distribution data that doesn't exist in model."""
    a = model.get("A_candidate", {})
    a_dist = a.get("goal_time_distribution", {}) or {}
    b_list = model.get("B_candidates", [])

    any_available = a_dist.get("available", False)
    for b in b_list:
        b_dist = b.get("goal_time_distribution", {}) or {}
        if b_dist.get("available", False):
            any_available = True

    if not any_available:
        # All should show 暂无完整时间分布数据
        # Count occurrences
        missing_count = console.count("暂无完整时间分布数据")
        a_count = model.get("A_count", 0)
        b_count = model.get("B_count", 0)
        # Each A/B card should show the missing message
        expected = a_count + b_count
        ok = missing_count >= expected
        return ("PASS" if ok else "FAIL",
                f"分布数据不可用：{missing_count}/{expected} 张卡片正确显示'暂无完整时间分布数据'", ok)
    else:
        return ("PASS", "分布数据可用，卡片应显示真实时段数据", True)


def check_team_names_chinese(console):
    """Chinese team names visible in cards."""
    required = ["帕尔梅拉斯", "浙江队", "山东泰山"]
    missing = [n for n in required if n not in console]
    ok = len(missing) == 0
    return ("PASS" if ok else "FAIL",
            f"中文队名: {len(required)-len(missing)}/{len(required)}" + (f" 缺失: {missing}" if missing else ""), ok)


def check_league_and_kickoff(console):
    """Cards must show league and kickoff time."""
    has_league = "中超" in console and "自由杯" in console
    has_kickoff = "20:00" in console and "08:30" in console
    ok = has_league and has_kickoff
    return ("PASS" if ok else "FAIL",
            "联赛和开球时间可见", ok)


def check_palmeiras_classification(candidate_json):
    """Palmeiras (40/60/30) MUST be 中段压迫型, NOT 开局冲击型."""
    a = candidate_json.get("A_candidate", {})
    st = a.get("script_type", "")
    ok = st == "中段压迫型"
    return ("PASS" if ok else "FAIL",
            f"Palmeiras script='{st}' (must be 中段压迫型)" + ("" if ok else " — REGRESSION: wrongly classified"),
            ok)


def check_b1_classification(candidate_json):
    """B1 Hangzhou (20/30/60) MUST be 慢热绝杀型."""
    b1 = candidate_json.get("B_candidates", [{}])[0] if candidate_json.get("B_candidates") else {}
    st = b1.get("script_type", "")
    ok = st == "慢热绝杀型"
    return ("PASS" if ok else "FAIL",
            f"B1 script='{st}' (must be 慢热绝杀型)" + ("" if ok else " — REGRESSION"),
            ok)


def check_source_field_on_all_entries(candidate_json):
    """All entries with available time_bins must have source_field."""
    entries = []
    a = candidate_json.get("A_candidate")
    if a: entries.append(("A", a))
    for b in candidate_json.get("B_candidates", []):
        entries.append((f"B{b.get('index','?')}", b))
    for c in candidate_json.get("C_candidates", []):
        entries.append((f"C{c.get('index','?')}", c))
    missing = []
    for label, e in entries:
        gtd = e.get("goal_time_distribution", {}) or {}
        if gtd.get("available") and not gtd.get("source_field"):
            missing.append(label)
    ok = len(missing) == 0
    return ("PASS" if ok else "FAIL",
            f"source_field present: missing={missing}" if missing else "source_field present on all entries",
            ok)


def check_taxonomy_json_exists():
    """Taxonomy JSON must exist as single source of truth for script types."""
    ok = TAXONOMY_JSON.is_file()
    return ("PASS" if ok else "FAIL",
            "Taxonomy JSON exists" if ok else f"Taxonomy JSON missing: {TAXONOMY_JSON}",
            ok)


def check_v2_lock_not_new(console):
    """V2 lock card must not be described as today's new recommendation."""
    has_historical = "不是今日新推荐" in console or "历史审计" in console
    has_not_real_bet = "real_bet=否" in console or "真实投注：否" in console or "真实投注=否" in console
    ok = has_historical and has_not_real_bet
    return ("PASS" if ok else "FAIL",
            "V2锁仓卡正确标注历史/非今日推荐", ok)


def main():
    if not CONSOLE_HTML.is_file():
        print("BLOCKER: intel_ops_console.html does not exist")
        sys.exit(1)

    console, model = load_data()

    checks = [
        check_taxonomy_json_exists(),
        check_script_label_visible(console),
        check_time_distribution_visible(console),
        check_missing_distribution_handled(console, model),
        check_no_fulltime_over_as_script(console),
        check_no_sh_ou_ft_ou_as_script(console),
        check_script_types_in_allowlist(console),
        check_palmeiras_classification(model),
        check_b1_classification(model),
        check_source_field_on_all_entries(model),
        check_c_is_observation(console),
        check_no_fabricated_distribution(console, model),
        check_team_names_chinese(console),
        check_league_and_kickoff(console),
        check_v2_lock_not_new(console),
    ]

    passed = 0
    failed = 0
    warned = 0
    blocked = 0
    total = len(checks)

    print(f"=== V4 剧本 & 进球时间分布 checker ===\n")
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
        "checker": "tools/check_v4_script_goal_distribution.py",
        "conclusion": conclusion,
        "total": total, "passed": passed, "failed": failed,
        "warn_only": warned, "blocked": blocked,
        "checks": [{"status": s, "detail": d, "ok": v} for s, d, v in checks],
    }
    marker_path = MODULE / "data" / "runtime" / "status" / "v4_script_goal_distribution_checker_result_20260520.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  标记: {marker_path}")

    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
