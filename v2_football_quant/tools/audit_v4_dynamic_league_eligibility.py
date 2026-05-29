#!/usr/bin/env python3
"""audit_v4_dynamic_league_eligibility.py — Audit dynamic league eligibility under all_eligible no-league-id-gate.

Outputs: data/runtime/status/v4_dynamic_league_eligibility_YYYYMMDD.json
"""
from __future__ import annotations
import json, sys, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))


def main() -> int:
    ts = datetime.now(TZ).isoformat()
    today = datetime.now(TZ).strftime("%Y%m%d")

    result = {
        "schema_version": "v4_dynamic_league_eligibility_audit.v1",
        "generated_at": ts,
        "audit_date": today,
    }

    # Load pyramid map
    pm_path = ROOT / "config/v4_league_pyramid_map.json"
    pyramid_map = {}
    if pm_path.exists():
        with open(pm_path) as f:
            pyramid_map = json.load(f).get("pyramid_map", {})

    # Load latest candidate_view
    cv_files = sorted(STATUS.glob("v3v4_dashboard_candidate_view_*.json"))
    cv_data = {}
    if cv_files:
        with open(cv_files[-1]) as f:
            cv_data = json.load(f)

    # Try loading scan output for H2H traces
    scan_outputs = sorted(STATUS.glob("v4_scan_output_*.json"))
    scan_data = {}
    if scan_outputs:
        try:
            with open(scan_outputs[-1]) as f:
                scan_data = json.load(f)
        except Exception:
            pass

    # Classification counters
    mapped_senior = 0
    dynamic_unmapped_senior = 0
    excluded_cup = 0
    excluded_friendly = 0
    excluded_youth = 0
    excluded_reserve = 0
    excluded_women = 0
    excluded_international = 0
    review_required = 0
    pyramid_unknown_legacy = 0

    sample_dynamic = []
    sample_excluded = []

    # Try to import _is_non_senior_league for classification
    try:
        import importlib, sys as _sys
        _sys.path.insert(0, str(ROOT))
        h2h_mod = importlib.import_module("engine.data_sources.h2h_engine")
        is_non_senior_fn = getattr(h2h_mod, "_is_non_senior_league", None)
    except Exception:
        is_non_senior_fn = None

    # Collect unique leagues from candidate_view
    unique_leagues = {}
    for key in ["A_candidates", "B_candidates", "C_candidates"]:
        cands = cv_data.get(key, [])
        for c in cands:
            lid = str(c.get("league_id", ""))
            lname = c.get("league", "")
            if lid and lid not in unique_leagues:
                unique_leagues[lid] = {
                    "league_id": lid,
                    "league_name": lname,
                    "source_group": c.get("source_group", "unknown"),
                    "fixture_count": 1,
                    "in_pyramid_map": lid in pyramid_map,
                    "eligible_for_h2h": pyramid_map.get(lid, {}).get("eligible_for_h2h", None) if lid in pyramid_map else None,
                }
            elif lid in unique_leagues:
                unique_leagues[lid]["fixture_count"] += 1

    # Extend with scan data if available
    all_fixtures = scan_data.get("all_fixtures", []) or scan_data.get("raw_fixtures", [])
    for fix in all_fixtures:
        lid = str(fix.get("league_id", fix.get("league", {}).get("id", "")))
        lname = fix.get("league_name", fix.get("league", {}).get("name", ""))
        if lid and lid not in unique_leagues:
            unique_leagues[lid] = {
                "league_id": lid,
                "league_name": lname,
                "source_group": fix.get("source_group", "unknown"),
                "fixture_count": 1,
                "in_pyramid_map": lid in pyramid_map,
                "eligible_for_h2h": pyramid_map.get(lid, {}).get("eligible_for_h2h", None) if lid in pyramid_map else None,
            }

    # Classify each league
    for lid, info in unique_leagues.items():
        if info["in_pyramid_map"]:
            entry = pyramid_map[lid]
            if entry.get("eligible_for_h2h", True):
                mapped_senior += 1
                info["category"] = "mapped_senior"
            else:
                comp_type = entry.get("competition_type", "unknown")
                if comp_type == "cup":
                    excluded_cup += 1
                    info["category"] = "excluded_cup"
                elif comp_type in ("friendly", "exhibition"):
                    excluded_friendly += 1
                    info["category"] = "excluded_friendly"
                elif comp_type in ("youth", "reserve"):
                    excluded_youth += 1
                    info["category"] = "excluded_youth"
                else:
                    excluded_youth += 1
                    info["category"] = "excluded_other"
            info["classification_source"] = "pyramid_map"
        else:
            # Dynamic classification
            lname = info["league_name"]
            if is_non_senior_fn and lname:
                is_ns, reason = is_non_senior_fn(lname)
                if is_ns:
                    info["category"] = f"excluded_{reason}"
                    info["classification_source"] = "dynamic"
                    if reason == "youth":
                        excluded_youth += 1
                    elif reason == "cup":
                        excluded_cup += 1
                    elif reason == "friendly":
                        excluded_friendly += 1
                    elif reason == "women":
                        excluded_women += 1
                    elif reason == "reserve":
                        excluded_reserve += 1
                    elif reason == "international":
                        excluded_international += 1
                    else:
                        review_required += 1
                        info["category"] = "review_required"
                    if len(sample_excluded) < 10:
                        sample_excluded.append({"league_id": lid, "league_name": lname, "reason": reason})
                else:
                    dynamic_unmapped_senior += 1
                    info["category"] = "dynamic_senior"
                    info["classification_source"] = "dynamic"
                    if len(sample_dynamic) < 10:
                        sample_dynamic.append({"league_id": lid, "league_name": lname, "country": info.get("country", "?")})
            else:
                review_required += 1
                info["category"] = "review_required"
                info["classification_source"] = "unknown"

    # Build result
    result["summary"] = {
        "total_unique_leagues": len(unique_leagues),
        "mapped_senior_league_count": mapped_senior,
        "dynamic_unmapped_senior_league_count": dynamic_unmapped_senior,
        "excluded_cup_count": excluded_cup,
        "excluded_friendly_count": excluded_friendly,
        "excluded_youth_count": excluded_youth,
        "excluded_reserve_count": excluded_reserve,
        "excluded_women_count": excluded_women,
        "excluded_international_count": excluded_international,
        "review_required_count": review_required,
        "pyramid_map_total_entries": len(pyramid_map),
    }

    # Before/after from candidate_view
    result["candidate_view"] = {
        "A_count": cv_data.get("A_count", 0),
        "B_count": cv_data.get("B_count", 0),
        "A_WHITELIST_57_count": cv_data.get("A_WHITELIST_57_count", 0),
        "A_OUTSIDE_57_count": cv_data.get("A_OUTSIDE_57_count", 0),
        "B_WHITELIST_57_count": cv_data.get("B_WHITELIST_57_count", 0),
        "B_OUTSIDE_57_count": cv_data.get("B_OUTSIDE_57_count", 0),
        "fixture_universe": cv_data.get("fixture_universe", "unknown"),
        "scan_total": cv_data.get("scan_total", 0),
    }

    result["sample_dynamic_senior_leagues"] = sample_dynamic
    result["sample_excluded_leagues"] = sample_excluded

    # Per-league detail for all unique leagues
    result["league_details"] = []
    for lid in sorted(unique_leagues.keys()):
        info = unique_leagues[lid]
        result["league_details"].append({
            "league_id": lid,
            "league_name": info["league_name"],
            "fixture_count": info["fixture_count"],
            "in_pyramid_map": info["in_pyramid_map"],
            "category": info.get("category", "unknown"),
            "classification_source": info.get("classification_source", "unknown"),
            "source_group": info["source_group"],
        })

    # Write output
    out_path = STATUS / f"v4_dynamic_league_eligibility_{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Audit written to {out_path}")
    print(f"Summary:")
    for k, v in result["summary"].items():
        print(f"  {k}: {v}")
    print(f"\nCandidate view summary:")
    for k, v in result["candidate_view"].items():
        print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
