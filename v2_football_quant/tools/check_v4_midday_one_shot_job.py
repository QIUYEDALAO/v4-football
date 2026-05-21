#!/usr/bin/env python3
"""V4 Midday One-Shot Job Checker — validates the 14:05 one-shot job configuration."""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
JOB_MARKER = MODULE / "data" / "runtime" / "status" / "v4_midday_one_shot_schedule_20260520.json"
CAPTURE_MARKER = MODULE / "data" / "runtime" / "status" / "v4_midday_one_shot_schedule_and_capture_20260520.json"

TZ = timezone(timedelta(hours=8))


def main():
    R = {
        "checker": "v4_midday_one_shot_job",
        "check_status": "PASS",
        "job_marker_path": str(JOB_MARKER),
        "job_marker_exists": False,
        "tests": {},
        "blockers": [],
        "warnings": [],
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }

    # Load the primary job marker
    if not JOB_MARKER.is_file():
        R["check_status"] = "BLOCKER"
        R["blockers"].append("one_shot_job_marker_not_found")
        R["job_marker_exists"] = False
        print(json.dumps(R, ensure_ascii=False, indent=2))
        return 2

    R["job_marker_exists"] = True
    job = json.loads(JOB_MARKER.read_text())

    # Also load capture marker if available
    capture = {}
    if CAPTURE_MARKER.is_file():
        capture = json.loads(CAPTURE_MARKER.read_text())

    def ck(name, cond, blocker=False):
        R["tests"][name] = cond
        if not cond:
            msg = f"{name}: FAIL"
            if blocker:
                R["blockers"].append(msg)
            else:
                R["warnings"].append(msg)
        return cond

    # 1. job_type=one_shot
    ck("job_type_is_one_shot", job.get("job_type") == "one_shot", blocker=True)

    # 2. not_cron=true
    ck("not_cron_is_true", job.get("not_cron") is True, blocker=True)

    # 3. scheduled_time=2026-05-20 14:05 CST
    sched = job.get("scheduled_time", "")
    ck("scheduled_time_14_05_cst", "14:05" in sched and "2026-05-20" in sched, blocker=True)

    # 4. command contains --window midday
    cmd = job.get("command", "")
    ck("command_has_window_midday", "--window midday" in cmd or "--window=midday" in cmd, blocker=True)

    # 5. command contains --scan-date 20260520
    ck("command_has_scan_date_20260520", "--scan-date 20260520" in cmd, blocker=True)

    # 6. command contains --no-push
    ck("command_has_no_push", "--no-push" in cmd, blocker=True)

    # 7. command contains --no-d13
    ck("command_has_no_d13", "--no-d13" in cmd, blocker=True)

    # 8. command contains --no-v33
    ck("command_has_no_v33", "--no-v33" in cmd, blocker=True)

    # 9. command contains --no-hourly
    ck("command_has_no_hourly", "--no-hourly" in cmd, blocker=True)

    # 10. deleteAfterRun/autodelete equivalent
    ck("autodelete_after_run_true", job.get("autodelete_after_run") is True, blocker=True)

    # 11. CRON_ENABLED not modified
    ck("cron_modified_is_false", job.get("cron_modified") is False, blocker=True)

    # Bonus checks
    ck("guards_no_qq_push", job.get("guards", {}).get("no_qq_push") is True)
    ck("guards_no_d13", job.get("guards", {}).get("no_d13") is True)
    ck("guards_no_v33", job.get("guards", {}).get("no_v33") is True)
    ck("guards_no_hourly", job.get("guards", {}).get("no_hourly") is True)
    ck("guards_no_cron_modified", job.get("guards", {}).get("no_cron_modified") is True)
    ck("V4_QQ_ENABLED_false", job.get("V4_QQ_ENABLED") is False)
    ck("no_push_true", job.get("no_push") is True)
    ck("no_d13_true", job.get("no_d13") is True)
    ck("no_v33_true", job.get("no_v33") is True)
    ck("no_hourly_true", job.get("no_hourly") is True)
    ck("scheduler_type_openclaw_cron_one_shot", job.get("scheduler_type") == "openclaw_cron_one_shot")

    # Check capture marker for consistency
    if capture:
        ck("capture_marker_V4_QQ_ENABLED_false",
           capture.get("steps", {}).get("step1_decision_pack_evidence", {}).get("V4_QQ_ENABLED") is False)
        ck("capture_marker_not_cron_true",
           capture.get("steps", {}).get("step3_one_shot_job", {}).get("not_cron") is True)

    passed = sum(1 for v in R["tests"].values() if v)
    R["tests_passed"] = passed
    R["tests_total"] = len(R["tests"])
    R["job_status"] = job.get("job_status", "UNKNOWN")
    R["not_cron"] = job.get("not_cron", None)

    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"

    print("=" * 60)
    print("V4 MIDDAY ONE-SHOT JOB CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']} | Job: {R['job_status']} | not_cron: {R['not_cron']}")
    print(f"Passed: {passed}/{len(R['tests'])}")
    for k, v in R["tests"].items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    if R["blockers"]:
        print(f"\nBLOCKERS: {R['blockers']}")
    if R["warnings"]:
        print(f"\nWARNINGS: {R['warnings']}")

    out = MODULE / "data" / "runtime" / "status" / "v4_one_shot_job_check_20260520.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(R, ensure_ascii=False, indent=2))

    if R["check_status"] == "BLOCKER":
        sys.exit(2)
    elif R["check_status"] == "WARN":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
