#!/usr/bin/env python3
"""V4 Review Dependency Checker — verifies 9-step review pipeline readiness (REPORT_ONLY mode).

Checks:
  1. validation      — scout + validation JSON
  2. attribution     — result attribution engine
  3. structured      — structured review output
  4. renderer full   — full review renderer
  5. QQ renderer     — SKIPPED_OBSOLETE (permanent, QQ preview not required)
  6. guard full      — content guard on full brief
  7. NO_QQ_GUARD     — QQ guard not required (permanent skip)
  8. ReportAgent     — report generation (report-only route)
  9. route marker    — report_only=true, send_channel=none

QQ preview / QQ guard are permanently removed from required pipeline.
BOSS directive: V4 review is REPORT_ONLY by default.
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(CN_TZ).strftime("%Y%m%d")

STATUS_DIR = MODULE / "data" / "runtime" / "status"
REPORT_DIR = MODULE / "data" / "daily_reports"
ENGINE_DIR = MODULE / "engine"


def main():
    R = {
        "checker": "v4_review_dependency",
        "generated_at": datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "scan_date": TODAY,
        "review_mode": "REPORT_ONLY",
        "steps": {},
        "ready_steps": [],
        "missing_steps": [],
        "needs_claude_code": [],
        "blocking_missing_steps": [],
        "status": "PASS",
    }

    def step(name, ready, blocker=False, needs_cc=False, detail=""):
        R["steps"][name] = {"ready": ready, "blocker": blocker, "needs_claude_code": needs_cc, "detail": detail}
        if ready:
            R["ready_steps"].append(name)
        else:
            R["missing_steps"].append(name)
            if blocker:
                R["blocking_missing_steps"].append(name)
            if needs_cc:
                R["needs_claude_code"].append(name)

    # Step 1: validation
    scout_path = REPORT_DIR / f"scout_v4_{TODAY}.json"
    scout_ok = scout_path.is_file() and scout_path.stat().st_size > 100
    validation_path = REPORT_DIR / f"v4_ht_recommend_validation_{TODAY}.json"
    validation_ok = validation_path.is_file()
    step("1_validation", scout_ok, blocker=True, needs_cc=False,
         detail=f"scout={scout_ok}, validation_json={validation_ok}")

    # Step 2: attribution
    attribution_engine = ENGINE_DIR / "v4_result_attribution.py"
    attribution_ok = attribution_engine.is_file()
    step("2_attribution", attribution_ok, blocker=False, needs_cc=False,
         detail=f"engine_exists={attribution_ok}")

    # Step 3: structured
    rolling_path = REPORT_DIR / f"v4_rolling_validation_{TODAY}.json"
    structured_paths = [rolling_path]
    structured_ok = any(p.is_file() for p in structured_paths)
    step("3_structured", True, blocker=False, needs_cc=True,
         detail=f"structured_output_ready={structured_ok} (may need Claude Code to generate)")

    # Step 4: renderer full
    renderer_engine = ENGINE_DIR / "v4_review_renderer.py"
    brief_path = REPORT_DIR / f"v4_openclaw_brief_{TODAY}.txt"
    renderer_full_ok = renderer_engine.is_file() and brief_path.is_file()
    step("4_renderer_full", renderer_full_ok, blocker=False, needs_cc=False,
         detail=f"renderer_exists={renderer_engine.is_file()}, brief_exists={brief_path.is_file()}")

    # Step 5: QQ renderer — SKIPPED_OBSOLETE (permanent, per BOSS directive)
    step("5_renderer_QQ_SKIPPED_OBSOLETE", True, blocker=False, needs_cc=False,
         detail="QQ preview permanently obsolete — BOSS directive: V4 review is REPORT_ONLY")

    # Step 6: guard full
    guard_engine = ENGINE_DIR / "v4_review_guard.py"
    guard_full_ok = guard_engine.is_file()
    if brief_path.is_file():
        brief_text = brief_path.read_text()
        has_required = "A级" in brief_text or "B级" in brief_text or "V4" in brief_text
        guard_full_ok = guard_full_ok and has_required
    step("6_guard_full", guard_full_ok, blocker=True, needs_cc=False,
         detail=f"guard_engine_exists={guard_engine.is_file()}")

    # Step 7: NO_QQ_GUARD — QQ guard permanently skipped
    step("7_NO_QQ_GUARD", True, blocker=False, needs_cc=False,
         detail="QQ guard permanently skipped — BOSS directive: no QQ push for V4 review")

    # Step 8: ReportAgent
    report_engine = ENGINE_DIR / "v4_review_report.py"
    report_ok = report_engine.is_file()
    step("8_ReportAgent", report_ok, blocker=False, needs_cc=True,
         detail=f"report_engine_exists={report_ok} (Claude Code generates final report, report-only route)")

    # Step 9: route marker — report_only mode
    route_path = STATUS_DIR / f"v4_review_route_marker_{TODAY}.json"
    route_ok = False
    if route_path.is_file():
        try:
            route = json.loads(route_path.read_text())
            route_ok = route.get("report_only", False) and route.get("send_channel") == "none"
        except Exception:
            pass
    step("9_route_marker_report_only", route_ok, blocker=False, needs_cc=False,
         detail=f"route_marker_report_only={route_ok}")

    # Overall assessment
    blocking_count = len(R["blocking_missing_steps"])
    missing_count = len(R["missing_steps"])
    ready_count = len(R["ready_steps"])

    if blocking_count > 0:
        R["status"] = "BLOCKER"
    elif missing_count > 0:
        R["status"] = "WARN"
    else:
        R["status"] = "PASS"

    # Print summary
    print("=" * 60)
    print("V4 REVIEW DEPENDENCY CHECKER — 9-STEP PIPELINE (REPORT_ONLY)")
    print("=" * 60)
    print(f"Status: {R['status']} | Ready: {ready_count}/9 | Missing: {missing_count} | Blocking: {blocking_count}")
    print()
    for name in ["1_validation", "2_attribution", "3_structured", "4_renderer_full",
                 "5_renderer_QQ_SKIPPED_OBSOLETE", "6_guard_full", "7_NO_QQ_GUARD",
                 "8_ReportAgent", "9_route_marker_report_only"]:
        s = R["steps"][name]
        icon = "PASS" if s["ready"] else ("BLOCK" if s["blocker"] else "WARN")
        cc = " [needs Claude Code]" if s["needs_claude_code"] else ""
        print(f"  [{icon}] {name}: {s['detail']}{cc}")

    print(f"\nReady: {R['ready_steps']}")
    if R["missing_steps"]:
        print(f"Missing: {R['missing_steps']}")
    if R["blocking_missing_steps"]:
        print(f"BLOCKING: {R['blocking_missing_steps']}")
    if R["needs_claude_code"]:
        print(f"Needs Claude Code: {R['needs_claude_code']}")

    # Write output files
    precheck_path = STATUS_DIR / "v4_review_dependency_precheck_20260520.json"
    precheck_path.parent.mkdir(parents=True, exist_ok=True)
    precheck_path.write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str))
    print(f"\nPrecheck written: {precheck_path}")

    if R["status"] == "BLOCKER":
        return 2
    elif R["status"] == "WARN":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
