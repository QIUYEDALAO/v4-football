#!/usr/bin/env python3
"""Intel Desk Checker — full validation including C/SKIP terminology"""
import json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
IDIR = MODULE / "reports" / "intel_desk"

def main():
    R = {"check_status": "PASS", "md_exists": False, "json_exists": False,
         "latest_exists": False, "json_parsed": False, "v2_current_ok": False,
         "v2_historical_ok": False, "v4_section": False, "risk_section": False,
         "actions_section": False, "c_observation_text": False,
         "skip_not_recommendation_text": False, "guards_ok": False,
         "blockers": [], "warnings": []}
    block = False

    for f, key in [("INTEL_DASHBOARD_20260520.md", "md_exists"),
                   ("INTEL_DASHBOARD_20260520.json", "json_exists"),
                   ("INTEL_DASHBOARD_LATEST.md", "latest_exists")]:
        R[key] = (IDIR / f).is_file()
        if not R[key]: R["blockers"].append(f"Missing: {f}"); block = True

    # JSON checks
    jf = IDIR / "INTEL_DASHBOARD_20260520.json"
    if jf.is_file():
        try:
            d = json.loads(jf.read_text())
            R["json_parsed"] = True

            R["v2_current_ok"] = d.get("v2_current") is not None
            R["v2_historical_ok"] = d.get("v2_historical") is not None
            if not R["v2_current_ok"]: R["blockers"].append("v2_current missing"); block = True
            if not R["v2_historical_ok"]: R["blockers"].append("v2_historical missing"); block = True

            v4t = d.get("v4_today", {})
            R["v4_section"] = bool(v4t)
            c_note = v4t.get("C_note", "")
            skip_note = v4t.get("SKIP_note", "")
            R["c_observation_text"] = "observation-only" in c_note.lower() or "观察" in c_note
            R["skip_not_recommendation_text"] = "not recommendation" in skip_note.lower() or "非推荐" in skip_note
            if not R["c_observation_text"]: R["warnings"].append("C observation-only text missing in JSON")
            if not R["skip_not_recommendation_text"]: R["warnings"].append("SKIP not-recommendation text missing in JSON")

            R["risk_section"] = bool(d.get("risk"))
            R["actions_section"] = bool(d.get("actions"))
            if not R["actions_section"]: R["blockers"].append("actions section missing"); block = True

            g = d.get("guards", {})
            R["guards_ok"] = all(not g.get(f, True) for f in
                ["qq_sent", "state_written", "verified_written", "proof_executed", "d13", "cron"])
            if not R["guards_ok"]: R["blockers"].append("Guard violation"); block = True
        except Exception as e: R["blockers"].append(f"JSON parse: {e}"); block = True

    # Markdown checks
    mdf = IDIR / "INTEL_DASHBOARD_20260520.md"
    if mdf.is_file():
        md_text = mdf.read_text()
        if "observation-only" in md_text.lower() or "observation" in md_text.lower():
            R["c_observation_text"] = True
        if "not recommendation" in md_text.lower() or "非推荐" in md_text or "not recommendation" in md_text:
            R["skip_not_recommendation_text"] = True
        if "操作" in md_text or "actions" in md_text.lower() or "action" in md_text.lower():
            R["actions_section"] = True
        # Forbidden terms in markdown
        forbidden = ["主推", "强推", "重点推荐", "重注", "梭哈", "WATCH_EARLY 正式", "CANDIDATE 正式"]
        for term in forbidden:
            if term in md_text and "observation" not in md_text.split(term)[0][-30:].lower():
                R["warnings"].append(f"Possible forbidden term: {term}")

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"

    print("=" * 50)
    print("INTEL DESK CHECKER")
    print("=" * 50)
    print(f"Status: {R['check_status']}")
    for k in ["md_exists", "json_exists", "latest_exists", "json_parsed", "v2_current_ok",
              "v2_historical_ok", "v4_section", "risk_section", "actions_section",
              "c_observation_text", "skip_not_recommendation_text", "guards_ok"]:
        print(f"  {k}: {R[k]}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]: print(f"  ~ {w}")
    print("Dashboard OK.")
    sys.exit(0)

if __name__ == "__main__":
    main()
