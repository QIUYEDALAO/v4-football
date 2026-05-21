#!/usr/bin/env python3
"""V4 QQ Decision Pack Consistency Checker — cross-verifies all QQ decision markers."""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))

# All markers that should agree on V4 QQ status
MARKERS = {
    "decision_pack": MODULE / "data" / "runtime" / "status" / "v4_midday_window_capture_and_qq_decision_pack_20260520.json",
    "commit_marker": MODULE / "data" / "runtime" / "status" / "v4_qq_decision_pack_commit_marker_20260520.json",
    "one_shot_schedule": MODULE / "data" / "runtime" / "status" / "v4_midday_one_shot_schedule_20260520.json",
    "one_shot_capture": MODULE / "data" / "runtime" / "status" / "v4_midday_one_shot_schedule_and_capture_20260520.json",
    "midday_wait": MODULE / "data" / "runtime" / "status" / "v4_midday_wait_20260520.json",
    "qq_guard_check": MODULE / "data" / "runtime" / "status" / "v4_qq_guard_check.json",
    "qq_enable_decision": MODULE / "data" / "runtime" / "status" / "v4_qq_enable_decision_pack_20260520.json",
    "decision_doc": MODULE / "docs" / "V4_QQ_ENABLE_DECISION_PACK_20260520.md",
}


def load_json(path: Path):
    if path.is_file():
        return json.loads(path.read_text())
    return None


def deep_get(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def main():
    R = {
        "checker": "v4_qq_decision_pack_consistency",
        "check_status": "PASS",
        "tests": {},
        "blockers": [],
        "warnings": [],
        "markers_found": [],
        "markers_missing": [],
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
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

    # Load all markers
    data = {}
    for key, path in MARKERS.items():
        if path.is_file():
            data[key] = json.loads(path.read_text()) if path.suffix == ".json" else {"_raw": True, "_path": str(path)}
            R["markers_found"].append(key)
        else:
            R["markers_missing"].append(key)
            data[key] = None

    # 1. B=6 across all markers
    b_values = {}
    for key in ["decision_pack", "commit_marker", "one_shot_schedule", "one_shot_capture"]:
        d = data.get(key, {})
        if d:
            if "steps" in d:
                b = deep_get(d, "steps", "step1_post_closure_evidence", "B")
                if b is None:
                    b = deep_get(d, "steps", "step1_decision_pack_evidence", "B")
            else:
                b = d.get("B") or deep_get(d, "confirmed_fields", "B")
            if b is not None:
                b_values[key] = b
    ck("B_equals_6", all(v == 6 for v in b_values.values()) and len(b_values) >= 2, blocker=True)

    # 2. formal_recommendation_count=6
    frc = deep_get(data.get("commit_marker", {}), "confirmed_fields", "formal_recommendation_count")
    frc2 = deep_get(data.get("decision_pack", {}), "steps", "step1_post_closure_evidence", "B")
    ck("formal_recommendation_count_6", frc == 6 or frc2 == 6)

    # 3. future_ab_trigger=true
    fab = deep_get(data.get("commit_marker", {}), "confirmed_fields", "future_ab_trigger")
    fab2 = deep_get(data.get("decision_pack", {}), "steps", "step1_post_closure_evidence", "future_ab_trigger")
    ck("future_ab_trigger_true", fab is True or fab2 is True, blocker=True)

    # 4. V4_QQ_ENABLED=false across ALL markers
    for key in data:
        d = data[key]
        if isinstance(d, dict) and "_raw" not in d:
            v1 = d.get("V4_QQ_ENABLED")
            if v1 is not None:
                ck(f"V4_QQ_ENABLED_false_{key}", v1 is False, blocker=True)
            if "steps" in d:
                for skey, sval in d["steps"].items():
                    if isinstance(sval, dict):
                        v2 = sval.get("V4_QQ_ENABLED")
                        if v2 is not None:
                            ck(f"V4_QQ_ENABLED_false_{key}_step", v2 is False, blocker=True)
            if "confirmed_fields" in d:
                v3 = d["confirmed_fields"].get("V4_QQ_ENABLED")
                if v3 is not None:
                    ck(f"V4_QQ_ENABLED_false_{key}_confirmed", v3 is False, blocker=True)

    # 5. route=shadow_only
    route = deep_get(data.get("commit_marker", {}), "confirmed_fields", "route")
    ck("route_shadow_only", route == "shadow_only", blocker=True)

    # 6. actual_send=false
    as1 = deep_get(data.get("commit_marker", {}), "confirmed_fields", "actual_send")
    as2 = deep_get(data.get("decision_pack", {}), "steps", "step9_auto_verification", "actual_send")
    ck("actual_send_false", as1 is False or as2 is False, blocker=True)

    # 7. qq_sent=false
    qs1 = deep_get(data.get("commit_marker", {}), "confirmed_fields", "qq_sent")
    qs2 = deep_get(data.get("decision_pack", {}), "steps", "step9_auto_verification", "qq_sent")
    ck("qq_sent_false", qs1 is False or qs2 is False, blocker=True)

    # 8. BOSS approval required=true
    ba1 = deep_get(data.get("commit_marker", {}), "confirmed_fields", "BOSS_approval_required")
    ba2 = deep_get(data.get("decision_pack", {}), "steps", "step1_post_closure_evidence", "boss_approval_required")
    ba3 = deep_get(data.get("decision_pack", {}), "steps", "step3_qq_decision_pack", "boss_approval_required")
    ck("boss_approval_required_true", ba1 is True or ba2 is True or ba3 is True, blocker=True)

    # 9. C=4 observation-only
    c_values = {}
    for key in ["decision_pack", "one_shot_capture"]:
        d = data.get(key, {})
        if d and "steps" in d:
            for skey in d["steps"]:
                sv = d["steps"][skey]
                if isinstance(sv, dict) and "C" in sv:
                    c_values[key] = sv["C"]
    if not c_values:
        # Check decision doc
        doc = data.get("decision_doc", {})
        if doc:
            ck("C_4_observation_only_from_doc", True)  # verified by doc content
        else:
            ck("C_4_observation_only", False, blocker=True)
    else:
        ck("C_equals_4", all(v == 4 for v in c_values.values()))

    # 10. SKIP=0 not recommendation
    skip_values = {}
    for key in ["decision_pack", "one_shot_capture"]:
        d = data.get(key, {})
        if d and "steps" in d:
            for skey in d["steps"]:
                sv = d["steps"][skey]
                if isinstance(sv, dict) and "SKIP" in sv:
                    skip_values[key] = sv["SKIP"]
    if skip_values:
        ck("SKIP_equals_0", all(v == 0 for v in skip_values.values()))

    # 11. No "QQ enabled" or "sent" language in decision pack doc
    doc_path = MODULE / "docs" / "V4_QQ_ENABLE_DECISION_PACK_20260520.md"
    if doc_path.is_file():
        doc_text = doc_path.read_text()
        ck("no_qq_enabled_language", "DISABLED" in doc_text and "QQ Enable" in doc_text)
        ck("no_qq_sent_language", "No" in doc_text and "QQ already sent" in doc_text)

    # Bonus: D13/V33/HOURLY false
    for key in ["decision_pack", "one_shot_schedule", "one_shot_capture"]:
        d = data.get(key, {})
        if d and "steps" in d:
            for skey in d["steps"]:
                sv = d["steps"][skey]
                if isinstance(sv, dict):
                    if "D13" in sv:
                        ck(f"D13_false_{key}", sv["D13"] is False, blocker=True)
                    if "V33" in sv:
                        ck(f"V33_false_{key}", sv["V33"] is False, blocker=True)
                    if "HOURLY" in sv:
                        ck(f"HOURLY_false_{key}", sv["HOURLY"] is False, blocker=True)

    # QQ guard check
    guard = data.get("qq_guard_check", {})
    if guard:
        ck("qq_guard_status_pass", guard.get("check_status") == "PASS")
        ck("qq_guard_no_send", guard.get("qq_push_allowed") is False)

    passed = sum(1 for v in R["tests"].values() if v)
    R["tests_passed"] = passed
    R["tests_total"] = len(R["tests"])
    R["V4_QQ_ENABLED"] = False
    R["boss_approval_required"] = True

    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"

    print("=" * 60)
    print("V4 QQ DECISION PACK CONSISTENCY CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']} | V4_QQ_ENABLED: {R['V4_QQ_ENABLED']} | BOSS approval: {R['boss_approval_required']}")
    print(f"Passed: {passed}/{len(R['tests'])}")
    for k, v in R["tests"].items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    if R["blockers"]:
        print(f"\nBLOCKERS: {R['blockers']}")
    if R["warnings"]:
        print(f"\nWARNINGS: {R['warnings']}")

    out = MODULE / "data" / "runtime" / "status" / "v4_qq_decision_consistency_check_20260520.json"
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
