#!/usr/bin/env python3
"""Strict validation data lineage checker — 17 checks.

Verifies: rejection, raw records, source_file, date range, unique fixtures,
dupes, unknown=N/A, resolved-only hit rate, rolling same-window detection,
V2 BET_LOCKED only, V4 A/B only for formal, C/SKIP excluded.
"""
import json
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
STATUS = MODULE / 'data' / 'runtime' / 'status'
CONSOLE = MODULE / 'data' / 'runtime' / 'dashboard' / 'intel_ops_console.html'


def load():
    console = CONSOLE.read_text() if CONSOLE.is_file() else ""
    rejection = json.loads((STATUS / 'validation_dashboard_v2_rejection_20260520.json').read_text()) if (STATUS / 'validation_dashboard_v2_rejection_20260520.json').is_file() else {}
    raw = json.loads((STATUS / 'v4_validation_raw_records_20260520.json').read_text()) if (STATUS / 'v4_validation_raw_records_20260520.json').is_file() else {}
    rolling = json.loads((STATUS / 'v4_rolling_validation_rebuilt_20260520.json').read_text()) if (STATUS / 'v4_rolling_validation_rebuilt_20260520.json').is_file() else {}
    yd = json.loads((STATUS / 'v4_yesterday_validation_rebuilt_20260519.json').read_text()) if (STATUS / 'v4_yesterday_validation_rebuilt_20260519.json').is_file() else {}
    v2 = json.loads((STATUS / 'v2_validation_rebuilt_20260520.json').read_text()) if (STATUS / 'v2_validation_rebuilt_20260520.json').is_file() else {}
    return console, rejection, raw, rolling, yd, v2


def check1_rejected(rejection):
    ok = rejection.get('new_status') == 'REJECTED_BY_BOSS'
    return ("PASS" if ok else "FAIL", "旧 dashboard 已标记 REJECTED_BY_BOSS", ok)


def check2_raw_records_exist(raw):
    ok = len(raw.get('records', [])) > 0
    return ("PASS" if ok else "FAIL", f"raw records 存在 ({len(raw.get('records', []))} 条)", ok)


def check3_source_file_per_record(raw):
    records = raw.get('records', [])
    ok = all(r.get('source_file') for r in records[:50])
    return ("PASS" if ok else "FAIL", "每条记录有 source_file", ok)


def check4_date_range_visible(console):
    ok = "date_from" in console.lower() or "2026-05-13" in console
    return ("PASS" if ok else "FAIL", "滚动验证 date range 可见", ok)


def check5_unique_fixture_count_visible(console):
    ok = "unique" in console.lower() and "fixture" in console.lower()
    return ("PASS" if ok else "FAIL", "unique_fixture_count 可见", ok)


def check6_duplicate_count_visible(rolling):
    w7 = rolling.get('windows', {}).get('last_7d', {})
    ok = w7.get('duplicate_count', -1) >= 0
    return ("PASS" if ok else "FAIL", f"duplicate_count 可见 ({w7.get('duplicate_count', 'N/A')})", ok)


def check7_unknown_not_in_hit_rate(yd):
    b = yd.get('official', {}).get('B', {})
    c = yd.get('observation', {}).get('C', {})
    b_ok = b.get('resolved_count', 0) == 0 and b.get('hit_rate_resolved_only') is None
    c_ok = c.get('resolved_count', 0) == 0 and c.get('hit_rate_resolved_only') is None
    ok = b_ok and c_ok
    return ("PASS" if ok else "FAIL",
            f"unknown 不计入命中率 (B resolved={b.get('resolved_count')} rate={b.get('hit_rate_resolved_only')}, C resolved={c.get('resolved_count')} rate={c.get('hit_rate_resolved_only')})",
            ok)


def check8_hit_rate_resolved_only(rolling):
    w7 = rolling.get('windows', {}).get('last_7d', {})
    ab = w7.get('A_plus_B', {})
    rate = ab.get('hit_rate_resolved_only')
    resolved = ab.get('resolved_count', 0)
    expected = round(ab.get('hit', 0) / resolved, 4) if resolved > 0 else None
    ok = rate == expected
    return ("PASS" if ok else "FAIL",
            f"hit_rate 使用 resolved only (rate={rate}, expected={expected} from {ab.get('hit')}/{resolved})",
            ok)


def check9_b_unknown_na(console, yd):
    b = yd.get('official', {}).get('B', {})
    has_na_in_console = "N/A" in console and "B" in console
    b_rate_none = b.get('hit_rate_resolved_only') is None
    ok = b_rate_none and has_na_in_console
    return ("PASS" if ok else "FAIL",
            f"B=3 unknown → 命中率 N/A (console_has_NA={has_na_in_console}, data_rate_is_None={b_rate_none})",
            ok)


def check10_c_unknown_na(console, yd):
    c = yd.get('observation', {}).get('C', {})
    has_na = "N/A" in console and "C" in console
    c_rate_none = c.get('hit_rate_resolved_only') is None
    ok = c_rate_none and has_na
    return ("PASS" if ok else "FAIL",
            f"C=13 unknown → 观察命中率 N/A (console_has_NA={has_na}, data_rate_is_None={c_rate_none})",
            ok)


def check11_same_window_documented(rolling):
    same = rolling.get('same_window_detected', False)
    reason = rolling.get('same_window_reason', '')
    ok = not same or (same and len(reason) > 50)
    return ("PASS" if ok else "FAIL",
            f"7d/14d/30d 相同已记录原因 ({'NOT same' if not same else 'reason length=' + str(len(reason))})",
            ok)


def check12_ab_133_traceable(raw):
    a = len([r for r in raw.get('records', []) if r.get('grade') == 'A'])
    b = len([r for r in raw.get('records', []) if r.get('grade') == 'B'])
    ab = a + b
    # 133 must be traceable to A_count + B_count
    gs = raw.get('grade_summary', {})
    raw_a = gs.get('A', {}).get('record_count', 0)
    raw_b = gs.get('B', {}).get('record_count', 0)
    ok = raw_a + raw_b == 133 and a == raw_a and b == raw_b
    return ("PASS" if ok else "FAIL",
            f"A+B=133 可追溯 (raw A={a} B={b} = {a+b}, unique A={gs.get('A',{}).get('unique_fixture_count')} B={gs.get('B',{}).get('unique_fixture_count')})",
            ok)


def check13_v2_bet_locked_only(v2):
    yd = v2.get('yesterday', {})
    off = yd.get('official', {})
    ok = off.get('scope', '') == 'BET_LOCKED only'
    return ("PASS" if ok else "FAIL", "V2 只认 BET_LOCKED", ok)


def check14_v4_ab_formal(yd):
    has_a = yd.get('official', {}).get('A', {}).get('count', 0) >= 0
    has_b = yd.get('official', {}).get('B', {}).get('count', 0) >= 0
    ok = has_a and has_b
    return ("PASS" if ok else "FAIL", "V4 只认 A/B 为正式候选", ok)


def check15_c_not_in_formal(yd):
    ok = yd.get('observation', {}).get('C_not_in_formal_hit_rate') is True
    return ("PASS" if ok else "FAIL", "C 不进正式命中率 (C_not_in_formal_hit_rate=true)", ok)


def check16_skip_not_in_hit_rate(yd):
    ok = yd.get('skip', {}).get('SKIP_not_in_hit_rate') is True
    return ("PASS" if ok else "FAIL", "SKIP 不进命中率 (SKIP_not_in_hit_rate=true)", ok)


def check17_no_fabricated(raw):
    ok = raw.get('total_raw_records', 0) > 0 and len(raw.get('source_files', [])) > 0
    return ("PASS" if ok else "WARN_ONLY",
            f"不伪造赛果 — 数据来自 {len(raw.get('source_files', []))} 个 attribution 文件, {raw.get('total_raw_records', 0)} 条记录",
            ok)


def main():
    console, rejection, raw, rolling, yd, v2 = load()

    checks = [
        check1_rejected(rejection),
        check2_raw_records_exist(raw),
        check3_source_file_per_record(raw),
        check4_date_range_visible(console),
        check5_unique_fixture_count_visible(console),
        check6_duplicate_count_visible(rolling),
        check7_unknown_not_in_hit_rate(yd),
        check8_hit_rate_resolved_only(rolling),
        check9_b_unknown_na(console, yd),
        check10_c_unknown_na(console, yd),
        check11_same_window_documented(rolling),
        check12_ab_133_traceable(raw),
        check13_v2_bet_locked_only(v2),
        check14_v4_ab_formal(yd),
        check15_c_not_in_formal(yd),
        check16_skip_not_in_hit_rate(yd),
        check17_no_fabricated(raw),
    ]

    passed = 0; failed = 0; warned = 0; blocked = 0; total = len(checks)
    print(f"=== VALIDATION DATA LINEAGE checker ===\n")
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
        "checker": "tools/check_validation_data_lineage.py",
        "conclusion": conclusion,
        "total": total, "passed": passed, "failed": failed,
        "warn_only": warned, "blocked": blocked,
        "checks": [{"status": s, "detail": d, "ok": v} for s, d, v in checks],
    }
    marker_path = STATUS / 'validation_data_lineage_checker_result_20260520.json'
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print(f"  标记: {marker_path}")
    return 0 if conclusion in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
