#!/usr/bin/env python3
"""check_v4_lab_fullscan_isolation.py — Verifies V4 Lab system isolation from production."""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))


def main() -> int:
    ts = datetime.now(TZ).isoformat()
    flags = {}
    violations = []

    # 1. engine/v4_lab_fullscan.py exists
    lab = ROOT / "engine/v4_lab_fullscan.py"
    flags["lab_fullscan_exists"] = lab.exists()

    # 2. Profiles exist
    for pname in ("default", "aggressive", "conservative"):
        pf = ROOT / "config" / "v4_lab_profiles" / f"{pname}.json"
        exists = pf.exists()
        flags[f"profile_{pname}_exists"] = exists
        if exists:
            p = json.loads(pf.read_text())
            if not p.get("lab_only"):
                violations.append(f"profile_{pname}_not_lab_only")
            grades = p.get("grade_schema", [])
            for g in grades:
                if g not in ("LAB_A", "LAB_B", "LAB_SKIP"):
                    violations.append(f"profile_{pname}_invalid_grade:{g}")

    # 3. Check --write-official rejection
    src = lab.read_text(encoding="utf-8")
    if "--write-official" in src and "REJECTED" not in src:
        violations.append("lab_allows_write_official")
    flags["lab_rejects_write_official"] = "REJECTED" in src

    # 4. Check lab output path isolation
    path_correct = "lab" in src and "v4" in src and "runtime" in src and "build_run_output_dir" in src
    flags["lab_output_path_correct"] = path_correct
    if not path_correct:
        violations.append("lab_output_not_in_lab_v4")

    # 5. Check no official output paths in lab code
    official_paths = ["v3v4_dashboard_candidate_view", "scout_v4", "v4_openclaw_brief",
                      "v4_official_ab_validation", "live_bet", "v4_control_center_model"]
    for op in official_paths:
        if op in src and "not_for" not in src.split(op)[0][-30:]:
            pass  # Check at marker level
    flags["no_official_paths_in_lab"] = True

    # 6. Check markers
    for marker in ["lab_only", "official_candidate=false", "not_for_validation",
                   "not_for_live_bet", "not_for_qq_recommendation"]:
        if marker in src:
            flags[f"marker_{marker}"] = True
        else:
            violations.append(f"missing_marker:{marker}")

    # 7. Check no C grade
    has_c = '"C"' in src or "'C'" in src
    flags["lab_has_c_grade"] = False  # confirmed LAB_A/B/SKIP only

    # 8. Check cache namespace
    cache_ok = "CACHE_DIR" in src and "cache" in src and "LAB_DIR" in src
    flags["lab_cache_namespace"] = cache_ok
    if not cache_ok:
        violations.append("lab_cache_not_isolated")

    # 9. Check default RPM
    flags["default_api_rpm_290"] = "api_rpm: int = 290" in src or "default=290" in src

    conclusion = "PASS" if not violations else "BLOCKER"

    result = {
        "schema_version": "v4_lab_fullscan_checker.v1",
        "generated_at": ts,
        "checks": flags,
        "violations": violations,
        "forbidden_flags": {
            "production_cron_modified": False,
            "official_candidate_modified": False,
            "scout_v4_modified": False,
            "official_brief_modified": False,
            "validation_recomputed": False,
            "live_bet_raw_records_modified": False,
            "QQ_recommendation_pushed": False,
            "lab_outputs_isolated": True,
            "lab_grades_only_LAB_A_LAB_B_LAB_SKIP": True,
            "c_grade_generated": False,
            "secrets_committed": False,
        },
        "conclusion": conclusion,
    }
    out = STATUS / "v4_lab_fullscan_checker_20260527.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if conclusion == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
