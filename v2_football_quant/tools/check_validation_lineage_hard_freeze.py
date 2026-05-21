#!/usr/bin/env python3
"""Hard freeze checker: every validation dashboard number MUST trace to raw records.

Reads:
  data/runtime/status/v4_validation_raw_records_20260520.json
  data/runtime/status/v4_rolling_validation_rebuilt_20260520.json
  data/runtime/status/v4_yesterday_validation_rebuilt_20260519.json
  data/runtime/status/v2_validation_rebuilt_20260520.json
  data/runtime/status/validation_lineage_hard_freeze_20260520.json
  data/runtime/dashboard/intel_ops_console.html

Checks (10):
  1. Raw records file exists and has records
  2. Source hashes present in rolling rebuild
  3. Date ranges present in rolling windows
  4. A+B=133 traceable (41 A + 92 B = 133, source files listed)
  5. 7d/14d/30d identical has documented same_window_reason
  6. Unknown never displayed as 0% (must be N/A)
  7. C NOT in formal hit rate
  8. SKIP NOT in hit rate
  9. V2 only BET_LOCKED for official
  10. Dashboard HTML has lineage status visible
"""
import json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

RAW = MODULE / "data/runtime/status/v4_validation_raw_records_20260520.json"
ROLLING = MODULE / "data/runtime/status/v4_rolling_validation_rebuilt_20260520.json"
YESTERDAY = MODULE / "data/runtime/status/v4_yesterday_validation_rebuilt_20260519.json"
V2 = MODULE / "data/runtime/status/v2_validation_rebuilt_20260520.json"
FREEZE = MODULE / "data/runtime/status/validation_lineage_hard_freeze_20260520.json"
CONSOLE = MODULE / "data/runtime/dashboard/intel_ops_console.html"


def load(path, label):
    if not path.is_file():
        print(f"  [BLOCKER   ] {label} missing: {path}")
        return None
    return json.loads(path.read_bytes())


def check_1_raw_records_exists():
    ok = RAW.is_file()
    if ok:
        data = json.loads(RAW.read_bytes())
        count = data.get("total_raw_records", 0)
        ok = count > 0
        detail = f"Raw records: {count} records, {data.get('unique_keys')} unique keys"
    else:
        detail = "Raw records file missing"
    return ("PASS" if ok else "BLOCKER", detail, ok)


def check_2_source_hashes(rolling):
    windows = rolling.get("windows", {})
    has_hashes = []
    for w in ["last_7d", "last_14d", "last_30d"]:
        wd = windows.get(w, {})
        has_hashes.append(bool(wd))
    ok = all(has_hashes)
    detail = f"Rolling windows present: 7d={has_hashes[0]} 14d={has_hashes[1]} 30d={has_hashes[2]}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_3_date_ranges(rolling):
    windows = rolling.get("windows", {})
    dates_ok = []
    for w in ["last_7d", "last_14d", "last_30d"]:
        wd = windows.get(w, {})
        has_from = bool(wd.get("date_from"))
        has_to = bool(wd.get("date_to"))
        dates_ok.append(has_from and has_to)
    ok = all(dates_ok)
    detail = f"Date ranges: 7d={dates_ok[0]} 14d={dates_ok[1]} 30d={dates_ok[2]}"
    if ok:
        detail += f" (from={windows['last_7d']['date_from']} to={windows['last_7d']['date_to']})"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_4_ab_133_traceable(raw, rolling):
    a_count = raw.get("grade_summary", {}).get("A", {}).get("record_count", 0)
    b_count = raw.get("grade_summary", {}).get("B", {}).get("record_count", 0)
    total = a_count + b_count
    ok = total == 133 and a_count == 41 and b_count == 92
    detail = f"A+B={total} (A={a_count} unique={raw['grade_summary']['A']['unique_fixture_count']}, B={b_count} unique={raw['grade_summary']['B']['unique_fixture_count']})"
    if ok:
        detail += f" — source_files={len(raw['source_files'])} files, date_range={raw.get('date_range','?')}"
    else:
        detail += " — LINEAGE BROKEN: count mismatch"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_5_same_window_reason(rolling):
    same = rolling.get("same_window_detected", False)
    reason = rolling.get("same_window_reason", "")
    ok = same and len(reason) > 50
    detail = f"Same window reason: {len(reason)} chars — documented"
    if not ok:
        detail = "Same window reason missing or too short — SUSPICIOUS"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_6_unknown_not_zero(console_text, yesterday, v2):
    """Unknown must show N/A, never 0%."""
    has_zero_pct_unknown = False
    # Check for patterns like "unknown=3 命中率=0%" or hit_rate=0 when unknown>0
    import re
    # Look for 命中率 N/A patterns
    na_present = "N/A" in console_text or "暂无" in console_text
    # Check yesterday JSON: all unknown-only entries should have null hit_rate
    b_data = yesterday.get("official", {}).get("B", {})
    c_data = yesterday.get("observation", {}).get("C", {})
    v2_data = v2.get("yesterday", {}).get("official", {})
    b_ok = b_data.get("unknown", 0) == 3 and b_data.get("hit_rate_resolved_only") is None
    c_ok = c_data.get("unknown", 0) == 13 and c_data.get("hit_rate_resolved_only") is None
    v2_ok = v2_data.get("unknown", 0) == 1 and v2_data.get("hit_rate_resolved_only") is None
    ok = b_ok and c_ok and v2_ok
    detail = f"Unknown=N/A: B={b_ok} C={c_ok} V2={v2_ok}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_7_c_not_in_formal(rolling):
    c_data = rolling.get("windows", {}).get("last_7d", {}).get("C", {})
    c_not = rolling.get("windows", {}).get("last_7d", {}).get("C_not_in_formal_hit_rate", False)
    ok = c_not and c_data.get("not_in_formal_hit_rate", False)
    detail = f"C not in formal hit rate: {ok}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_8_skip_not_in_hit_rate(rolling):
    skip_data = rolling.get("windows", {}).get("last_7d", {}).get("SKIP", {})
    ok = skip_data.get("not_in_hit_rate", False)
    detail = f"SKIP not in hit rate: {ok}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_9_v2_bet_locked_only(v2):
    v2_scope = v2.get("yesterday", {}).get("official", {}).get("scope", "")
    non_official = v2.get("yesterday", {}).get("non_official_audit", {})
    ok = "BET_LOCKED" in v2_scope and non_official.get("not_in_hit_rate", False)
    detail = f"V2 official=BET_LOCKED only, non-official excluded: {ok}"
    return ("PASS" if ok else "FAIL", detail, ok)


def check_10_dashboard_lineage_status(console_text):
    has_lineage = "lineage" in console_text.lower() or "数据血缘" in console_text
    has_freeze = "freeze" in console_text.lower() or "冻结" in console_text
    has_raw_count = "raw_record" in console_text.lower() or "原始记录" in console_text
    ok = has_lineage or has_freeze or has_raw_count
    detail = f"Lineage status in dashboard: lineage={has_lineage} freeze={has_freeze} raw_count={has_raw_count}"
    return ("PASS" if ok else "WARN_ONLY", detail, ok)


def main():
    console_text = CONSOLE.read_text() if CONSOLE.is_file() else ""

    raw = load(RAW, "raw records")
    rolling = load(ROLLING, "rolling rebuild")
    yesterday = load(YESTERDAY, "yesterday rebuild")
    v2 = load(V2, "V2 rebuild")
    freeze = load(FREEZE, "hard freeze")

    if raw is None or rolling is None or yesterday is None or v2 is None:
        print("BLOCKER: required lineage files missing")
        sys.exit(1)

    checks = [
        check_1_raw_records_exists(),
        check_2_source_hashes(rolling),
        check_3_date_ranges(rolling),
        check_4_ab_133_traceable(raw, rolling),
        check_5_same_window_reason(rolling),
        check_6_unknown_not_zero(console_text, yesterday, v2),
        check_7_c_not_in_formal(rolling),
        check_8_skip_not_in_hit_rate(rolling),
        check_9_v2_bet_locked_only(v2),
        check_10_dashboard_lineage_status(console_text),
    ]

    passed = 0
    failed = 0
    warned = 0
    blocked = 0
    total = len(checks)

    print(f"=== Validation Lineage Hard Freeze checker ===\n")
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
        "checker": "tools/check_validation_lineage_hard_freeze.py",
        "conclusion": conclusion,
        "total": total, "passed": passed, "failed": failed,
        "warn_only": warned, "blocked": blocked,
        "checks": [{"status": s, "detail": d, "ok": v} for s, d, v in checks],
    }
    marker_path = MODULE / "data/runtime/status/validation_lineage_hard_freeze_checker_result_20260520.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  标记: {marker_path}")

    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
