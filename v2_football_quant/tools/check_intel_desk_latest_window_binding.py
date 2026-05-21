#!/usr/bin/env python3
"""Intel Desk Latest-Window Binding Checker

Verifies that the CURRENT window in candidate model is the latest completed window,
and that HTML pages reflect CURRENT (not stale early/midday data).
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))

CANDIDATE_JSON = MODULE / "data" / "runtime" / "status" / "intel_desk_v4_candidate_view_20260520.json"
DASH_DIR = MODULE / "data" / "runtime" / "dashboard"
ROUTES = ["index.html", "intel_desk.html", "ops_heartbeat.html", "v2_today.html"]

# Window chronology: latest completed window is the CURRENT source
WINDOW_ORDER = ["late", "early", "midday", "evening", "night"]


def main():
    R = {
        "checker": "intel_desk_latest_window_binding",
        "check_status": "PASS",
        "tests": {},
        "blockers": [],
        "warnings": [],
        "generated_at": datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }

    def ck(name, cond, blocker=False):
        R["tests"][name] = cond
        if not cond:
            msg = f"{name}: FAIL"
            if blocker:
                R["blockers"].append(msg)
            else:
                R["warnings"].append(msg)
        return cond

    # ── 1. Candidate model must exist ──
    ck("candidate_model_exists", CANDIDATE_JSON.is_file(), blocker=True)
    if not CANDIDATE_JSON.is_file():
        R["check_status"] = "BLOCKER"
        print(json.dumps(R, ensure_ascii=False, indent=2))
        return 2

    raw = CANDIDATE_JSON.read_bytes()
    source_hash = hashlib.md5(raw).hexdigest()[:12]
    data = json.loads(raw.decode())

    # ── 2. source_window must be defined ──
    source_window = data.get("source_window", "")
    ck("source_window_defined", bool(source_window), blocker=True)
    ck("source_window_is_known", source_window in WINDOW_ORDER)

    # ── 3. CURRENT must be the latest completed window ──
    window_history = data.get("window_history", {})
    ck("window_history_exists", bool(window_history))

    completed_windows = [w for w in WINDOW_ORDER if w in window_history]
    ck("at_least_one_window_completed", len(completed_windows) > 0)

    if completed_windows:
        latest_completed = completed_windows[-1]
        ck("source_window_is_latest_completed",
           source_window == latest_completed,
           blocker=True)
        R["latest_completed_window"] = latest_completed
        R["completed_windows"] = completed_windows

        # ── 4. Earlier windows must be marked historical ──
        for w in completed_windows[:-1]:
            wh = window_history.get(w, {})
            has_note = wh.get("note", "")
            is_historical = "historical" in has_note.lower() or "not current" in has_note.lower()
            ck(f"window_{w}_marked_historical", is_historical)

    # ── 5. CURRENT window must be marked as current ──
    if source_window in window_history:
        sw = window_history[source_window]
        is_current = "current" in sw.get("note", "").lower()
        ck(f"source_window_{source_window}_marked_current", is_current)

    # ── 6. A/B/C/SKIP must match CURRENT window values ──
    if source_window in window_history:
        sw = window_history[source_window]
        ck("A_count_matches_window_history", data.get("A_count") == sw.get("A"))
        ck("B_count_matches_window_history", data.get("B_count") == sw.get("B"))
        ck("C_count_matches_window_history", data.get("C_count") == sw.get("C"))
        ck("SKIP_count_matches_window_history", data.get("SKIP_count") == sw.get("SKIP"))

    # ── 7. Early window data must NOT contaminate CURRENT ──
    early_ref = data.get("early_window_b6_for_reference", [])
    early_note = data.get("early_window_b6_note", "")
    ck("early_window_data_not_current", "not current" in early_note.lower() or "historical" in early_note.lower())
    if early_ref:
        R["early_window_b6_count"] = len(early_ref)
        R["early_window_b6_note"] = early_note

    # ── 8. Safety gates ──
    ck("V4_QQ_ENABLED_false", data.get("V4_QQ_ENABLED") is False, blocker=True)
    ck("actual_send_false", data.get("actual_send") is False, blocker=True)
    ck("qq_sent_false", data.get("qq_sent") is False, blocker=True)
    ck("boss_approval_required", data.get("boss_approval_required") is True, blocker=True)

    # ── 9. B/C candidates source_window consistency ──
    b_candidates = data.get("B_candidates", [])
    c_candidates = data.get("C_candidates", [])
    b_mismatch_windows = []
    for b in b_candidates:
        bw = b.get("source_window", "")
        if bw and bw != source_window:
            b_mismatch_windows.append(f"B{b.get('index','?')}:{bw}")
    ck("B_candidates_source_window_consistent",
       len(b_mismatch_windows) == 0)
    if b_mismatch_windows:
        R["b_source_window_mismatches"] = b_mismatch_windows

    # ── 10. HTML 4 routes must reflect CURRENT (not early) ──
    b_count = data.get("B_count", 0)
    c_count = data.get("C_count", 0)
    a_count = data.get("A_count", 0)

    for route in ROUTES:
        html_path = DASH_DIR / route
        if not html_path.is_file():
            ck(f"html_{route}_exists", False)
            continue

        ck(f"html_{route}_exists", True)
        html = html_path.read_text()

        # source_hash must be present
        ck(f"html_{route}_has_source_hash", source_hash in html, blocker=True)

        # B count in HTML must match candidate model
        b_card_count = html.count('<div class="bcard">')
        ck(f"html_{route}_B_card_count_{b_count}", b_card_count == b_count,
           blocker=True)

        # C card count must match
        c_card_count = html.count('<div class="ccard">')
        ck(f"html_{route}_C_card_count_{c_count}", c_card_count == c_count)

        # Must contain current source_window name
        ck(f"html_{route}_has_source_window_{source_window}",
           source_window in html.lower())

        # Must NOT hardcode early values
        ck(f"html_{route}_not_hardcode_early_B6",
           not re.search(r'early\s+B\s*[=:：]\s*6', html))

        # V4_QQ_ENABLED false in HTML
        ck(f"html_{route}_V4_QQ_disabled",
           "V4_QQ_ENABLED" in html and "false" in html.lower())

        # qq_sent false in HTML
        ck(f"html_{route}_qq_not_sent",
           "qq_sent" in html.lower() or "QQ未发送" in html)

    # ── 11. Internal consistency ──
    ck("formal_rec_equals_A_plus_B",
       data.get("formal_recommendation_count") == a_count + b_count)
    ck("future_ab_trigger_correct",
       data.get("future_ab_trigger") == (a_count + b_count > 0))
    ck("B_candidates_count_matches_B_count",
       len(b_candidates) == b_count, blocker=True)
    ck("C_candidates_count_matches_C_count",
       len(c_candidates) == c_count, blocker=True)

    # ── Status ──
    R["source_window"] = source_window
    R["current_A"] = a_count
    R["current_B"] = b_count
    R["current_C"] = c_count
    R["current_SKIP"] = data.get("SKIP_count", 0)
    R["source_hash"] = source_hash

    passed = sum(1 for v in R["tests"].values() if v)
    R["tests_passed"] = passed
    R["tests_total"] = len(R["tests"])

    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"

    print("=" * 60)
    print("INTEL DESK LATEST-WINDOW BINDING CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']} | Passed: {passed}/{len(R['tests'])}")
    print(f"Source window: {source_window} | A={a_count} B={b_count} C={c_count} SKIP={data.get('SKIP_count',0)}")
    print(f"Source hash: {source_hash}")
    print(f"Completed windows: {R.get('completed_windows', [])}")
    for k, v in R["tests"].items():
        if not v:
            print(f"  FAIL: {k}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"  ! {b}")
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]:
            print(f"  ~ {w}")

    out = MODULE / "data" / "runtime" / "status" / "intel_desk_latest_window_binding_check_20260520.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str))

    if R["check_status"] == "BLOCKER":
        return 2
    elif R["check_status"] == "WARN":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
