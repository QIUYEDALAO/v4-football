#!/usr/bin/env python3
"""Strict regression checker: V4 goal-time distribution source trace.

Verifies:
  1. time_bins source = factors.recent_time_bins (source_priority=1)
  2. factors.time_bins all-zero NOT used
  3. All 11 cards have source_field
  4. Palmeiras NOT wrongly classified as 开局冲击型
  5. B1 20/30/60 NOT wrongly classified as 开局冲击型
  6. '数据不足' never appears when recent_time_bins is available
  7. FULLTIME_OVER/SH_OU/FT_OU never used as script name
  8. C cards still observation-only
  9. All script_type values belong to formal taxonomy
  10. Taxonomy JSON exists

Reads: data/runtime/status/intel_desk_v4_candidate_view_20260520.json
       data/runtime/status/v4_script_taxonomy_20260520.json
       data/runtime/dashboard/intel_ops_console.html
       data/daily_reports/scout_v4_20260520.json
"""
import json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CV = MODULE / "data/runtime/status/intel_desk_v4_candidate_view_20260520.json"
TAXONOMY = MODULE / "data/runtime/status/v4_script_taxonomy_20260520.json"
CONSOLE = MODULE / "data/runtime/dashboard/intel_ops_console.html"
SCOUT = MODULE / "data/daily_reports/scout_v4_20260520.json"

FORBIDDEN_SCRIPT_TOKENS = ["FULLTIME_OVER", "SECOND_HALF_OVER", "SH_OU", "FT_OU"]


def load_json(path, label):
    if not path.is_file():
        print(f"  [BLOCKER   ] {label} missing: {path}")
        return None
    return json.loads(path.read_bytes())


def check_1_time_bins_source_recent(cv, scout):
    """All available time_bins must source from factors.recent_time_bins (priority=1)."""
    entries = []
    a = cv.get("A_candidate")
    if a: entries.append(("A", a))
    for b in cv.get("B_candidates", []):
        entries.append((f"B{b.get('index','?')}", b))
    for c in cv.get("C_candidates", []):
        entries.append((f"C{c.get('index','?')}", c))

    bad = []
    for label, e in entries:
        gtd = e.get("goal_time_distribution", {}) or {}
        if gtd.get("available") and gtd.get("source_field") != "factors.recent_time_bins":
            bad.append(f"{label}: source_field={gtd.get('source_field')} (expected recent_time_bins)")
    ok = len(bad) == 0
    return ("PASS" if ok else "FAIL",
            f"time_bins source = recent_time_bins: {len(entries)-len(bad)}/{len(entries)}" + (f" BAD: {bad}" if bad else ""),
            ok)


def check_2_time_bins_all_zero_not_used(scout):
    """factors.time_bins is all-zero for all matches; verify NOT used as source_field."""
    any_time_bins_used = False
    for m in (scout if isinstance(scout, list) else []):
        gtd = m.get("goal_time_distribution", {}) or {}
        if gtd.get("source_field") == "factors.time_bins":
            any_time_bins_used = True
    # Check candidate view entries
    return ("PASS" if not any_time_bins_used else "FAIL",
            "factors.time_bins (all-zero) NOT used as source",
            not any_time_bins_used)


def check_3_all_cards_have_source_field(cv):
    """All 11 cards with time_bins must have source_field."""
    entries = []
    a = cv.get("A_candidate")
    if a: entries.append(("A", a))
    for b in cv.get("B_candidates", []):
        entries.append((f"B{b.get('index','?')}", b))
    for c in cv.get("C_candidates", []):
        entries.append((f"C{c.get('index','?')}", c))

    missing = []
    for label, e in entries:
        gtd = e.get("goal_time_distribution", {}) or {}
        if gtd.get("available") and not gtd.get("source_field"):
            missing.append(label)
    ok = len(missing) == 0
    return ("PASS" if ok else "FAIL",
            f"source_field present on all available entries: missing={missing}" if missing else "source_field present on all entries",
            ok)


def check_4_palmeiras_not_kaijuchongji(cv):
    """Palmeiras (40/60/30) must NOT be 开局冲击型. Must be 中段压迫型."""
    a = cv.get("A_candidate", {})
    st = a.get("script_type", "")
    ok = st != "开局冲击型" and st == "中段压迫型"
    return ("PASS" if ok else "FAIL",
            f"Palmeiras script = '{st}' (expected 中段压迫型, NOT 开局冲击型)",
            ok)


def check_5_b1_not_kaijuchongji(cv):
    """B1 Hangzhou (20/30/60) must NOT be 开局冲击型. Must be 慢热绝杀型."""
    b1 = cv.get("B_candidates", [{}])[0] if cv.get("B_candidates") else {}
    st = b1.get("script_type", "")
    ok = st != "开局冲击型" and st == "慢热绝杀型"
    return ("PASS" if ok else "FAIL",
            f"B1 script = '{st}' (expected 慢热绝杀型, NOT 开局冲击型)",
            ok)


def check_6_no_data_buzu_with_recent(cv):
    """数据不足 must NOT appear when recent_time_bins data is available."""
    entries = []
    a = cv.get("A_candidate")
    if a: entries.append(("A", a))
    for b in cv.get("B_candidates", []):
        entries.append((f"B{b.get('index','?')}", b))
    for c in cv.get("C_candidates", []):
        entries.append((f"C{c.get('index','?')}", c))

    bad = []
    for label, e in entries:
        gtd = e.get("goal_time_distribution", {}) or {}
        st = e.get("script_type", "")
        if gtd.get("available") and "数据不足" in st:
            bad.append(f"{label}: available=True but script='{st}'")
    ok = len(bad) == 0
    return ("PASS" if ok else "FAIL",
            "数据不足 not used when recent_time_bins available" + (f" BAD: {bad}" if bad else ""),
            ok)


def check_7_no_forbidden_tokens(console_html):
    """FULLTIME_OVER / SH_OU / FT_OU must NOT appear in script lines."""
    import re
    cs_lines = re.findall(r'<div class="cs">(.*?)</div>', console_html)
    bad = []
    for line in cs_lines:
        for tok in FORBIDDEN_SCRIPT_TOKENS:
            if tok in line:
                bad.append(line[:80])
    ok = len(bad) == 0
    return ("PASS" if ok else "FAIL",
            f"No FULLTIME_OVER/SH_OU/FT_OU in script lines" + (f" BAD: {bad}" if bad else ""),
            ok)


def check_8_c_observation_only(console_html):
    """C cards must be labeled observation-only."""
    has_label = "仅观察，不是推荐" in console_html
    has_c_section = "C级观察" in console_html or "C 级观察" in console_html
    ok = has_label and has_c_section
    return ("PASS" if ok else "FAIL",
            f"C observation-only: label={has_label} section={has_c_section}",
            ok)


def check_9_all_scripts_in_taxonomy(cv, taxonomy):
    """All script_types must belong to the formal taxonomy JSON."""
    allowed = list(taxonomy.get("scripts", {}).keys())
    entries = []
    a = cv.get("A_candidate")
    if a: entries.append(("A", a))
    for b in cv.get("B_candidates", []):
        entries.append((f"B{b.get('index','?')}", b))
    for c in cv.get("C_candidates", []):
        entries.append((f"C{c.get('index','?')}", c))

    bad = []
    for label, e in entries:
        st = e.get("script_type", "")
        if st not in allowed:
            bad.append(f"{label}: '{st}' not in taxonomy")
    ok = len(bad) == 0
    return ("PASS" if ok else "FAIL",
            f"All scripts in taxonomy ({len(allowed)} types)" + (f" BAD: {bad}" if bad else ""),
            ok)


def check_10_taxonomy_exists():
    """Taxonomy JSON must exist and be valid."""
    ok = TAXONOMY.is_file()
    if ok:
        try:
            t = json.loads(TAXONOMY.read_bytes())
            script_count = len(t.get("scripts", {}))
            return ("PASS", f"Taxonomy JSON exists with {script_count} script types", True)
        except:
            return ("FAIL", "Taxonomy JSON is invalid", False)
    return ("FAIL", "Taxonomy JSON missing", False)


def main():
    console_html = CONSOLE.read_text() if CONSOLE.is_file() else ""

    cv = load_json(CV, "candidate view")
    taxonomy = load_json(TAXONOMY, "taxonomy")
    scout = load_json(SCOUT, "scout v4")

    if cv is None or taxonomy is None or scout is None or not console_html:
        print("BLOCKER: required files missing")
        sys.exit(1)

    checks = [
        check_1_time_bins_source_recent(cv, scout),
        check_2_time_bins_all_zero_not_used(scout),
        check_3_all_cards_have_source_field(cv),
        check_4_palmeiras_not_kaijuchongji(cv),
        check_5_b1_not_kaijuchongji(cv),
        check_6_no_data_buzu_with_recent(cv),
        check_7_no_forbidden_tokens(console_html),
        check_8_c_observation_only(console_html),
        check_9_all_scripts_in_taxonomy(cv, taxonomy),
        check_10_taxonomy_exists(),
    ]

    passed = 0
    failed = 0
    warned = 0
    blocked = 0
    total = len(checks)

    print(f"=== V4 Goal Distribution Source Trace checker ===\n")
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
        "checker": "tools/check_v4_goal_distribution_source_trace.py",
        "conclusion": conclusion,
        "total": total, "passed": passed, "failed": failed,
        "warn_only": warned, "blocked": blocked,
        "checks": [{"status": s, "detail": d, "ok": v} for s, d, v in checks],
    }
    marker_path = MODULE / "data/runtime/status/v4_goal_distribution_source_trace_checker_result_20260520.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  标记: {marker_path}")

    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
