#!/usr/bin/env python3
"""
V4-F: Rolling Validation Module

Pure functions for V4 rolling validation classification and summarization.
No API calls, no writes, no QQ, no state, no verified, no rule changes.

Usage:
  python3 engine/v4_rolling_validation.py --validate-only
  python3 engine/v4_rolling_validation.py --dry-run --records-file <path>

Guard markers:
  NO_API = true
  NO_WRITE = true
  NO_QQ = true
  NO_STATE = true
  NO_VERIFIED = true
  NO_RULE_CHANGE = true
"""

import argparse
import json
import sys
from typing import Any

# Attribution status to rolling classification
STATUS_TO_BUCKET = {
    "HIT": "hit",
    "MISS": "miss",
    "VOID": "void",
    "UNKNOWN": "unknown",
    "SKIP_NOT_SCORED": "skip",
}


def classify_rolling_sample(record: dict) -> dict:
    """
    Classify a single attribution record into rolling bucket.
    Returns dict with classification metadata.
    """
    grade = record.get("original_grade", "UNKNOWN")
    status = record.get("attribution_status", "UNKNOWN")
    result_known = record.get("result_known", True)
    result_source = record.get("result_source", "")

    classification = {
        "grade": grade,
        "status": status,
        "result_known": bool(result_known),
        "result_source": str(result_source),
        "bucket": None,
        "is_primary": False,
        "excluded": False,
        "reason": "",
    }

    # Exclusion rules
    if status == "UNKNOWN":
        classification["excluded"] = True
        classification["reason"] = "UNKNOWN attribution status"
        return classification

    if result_source == "API_DISABLED":
        classification["excluded"] = True
        classification["reason"] = "API_DISABLED — no result available"
        return classification

    if not result_known:
        classification["excluded"] = True
        classification["reason"] = "result_unknown"
        return classification

    if status == "VOID":
        classification["excluded"] = True
        classification["reason"] = "VOID — excluded from hit/miss"
        return classification

    # Grade-dependent classification
    if grade == "SKIP":
        classification["bucket"] = "skip"
        classification["reason"] = "SKIP — not a recommendation"
        return classification

    if grade == "C":
        classification["bucket"] = "c_observation"
        classification["reason"] = "C — observation only"
        return classification

    if grade in ("A", "B"):
        if status in ("HIT", "MISS"):
            classification["bucket"] = STATUS_TO_BUCKET.get(status, "unknown")
            classification["is_primary"] = True
            classification["reason"] = f"{grade} {status}"
        else:
            classification["excluded"] = True
            classification["reason"] = f"{grade} with unexpected status: {status}"
    else:
        classification["excluded"] = True
        classification["reason"] = f"Unknown grade: {grade}"

    return classification


def build_grade_bucket(records: list[dict]) -> dict:
    """Build grade-level statistics from attribution records."""
    buckets = {"A": {"hit": 0, "miss": 0}, "B": {"hit": 0, "miss": 0}}
    counts = {
        "total": 0,
        "excluded": 0,
        "skip": 0,
        "c_observation": 0,
        "unknown": 0,
        "api_disabled": 0,
        "void": 0,
        "primary_hit": 0,
        "primary_miss": 0,
    }

    for rec in records:
        cl = classify_rolling_sample(rec)
        counts["total"] += 1

        if cl["excluded"]:
            counts["excluded"] += 1
            if "API_DISABLED" in cl.get("reason", ""):
                counts["api_disabled"] += 1
            elif "UNKNOWN" in cl.get("reason", ""):
                counts["unknown"] += 1
            elif "VOID" in cl.get("reason", ""):
                counts["void"] += 1
            continue

        if cl["bucket"] == "skip":
            counts["skip"] += 1
        elif cl["bucket"] == "c_observation":
            counts["c_observation"] += 1
        elif cl["bucket"] == "hit" and cl["grade"] in ("A", "B"):
            buckets[cl["grade"]]["hit"] += 1
            counts["primary_hit"] += 1
        elif cl["bucket"] == "miss" and cl["grade"] in ("A", "B"):
            buckets[cl["grade"]]["miss"] += 1
            counts["primary_miss"] += 1

    # Compute rates
    for grade in ("A", "B"):
        total = buckets[grade]["hit"] + buckets[grade]["miss"]
        buckets[grade]["rate"] = (
            round(buckets[grade]["hit"] / total, 4) if total > 0 else 0.0
        )
        buckets[grade]["total"] = total

    total_primary = counts["primary_hit"] + counts["primary_miss"]
    counts["primary_hit_rate"] = (
        round(counts["primary_hit"] / total_primary, 4) if total_primary > 0 else 0.0
    )
    counts["primary_total"] = total_primary

    return {"grade_buckets": buckets, "counts": counts}


def build_source_group_bucket(records: list[dict]) -> dict:
    """Build layered split statistics by source_group (WHITELIST_57 / OUTSIDE_57 / UNKNOWN_LEGACY).

    Only official A/B (not SKIP, not C, not DATA_TIMEOUT, not SCORE_INCOMPLETE)
    enter the validation source.
    """
    groups = {
        "AB_ALL": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "AB_WHITELIST_57": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "AB_OUTSIDE_57": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "AB_UNKNOWN_LEGACY": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "A_ALL": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "A_WHITELIST_57": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "A_OUTSIDE_57": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "B_ALL": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "B_WHITELIST_57": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
        "B_OUTSIDE_57": {"sample_count": 0, "hit_count": 0, "miss_count": 0, "hit_rate": 0.0, "pending_count": 0},
    }

    for rec in records:
        cl = classify_rolling_sample(rec)
        if cl.get("excluded"):
            continue
        if cl.get("bucket") not in ("hit", "miss"):
            if cl.get("bucket") in ("skip", "c_observation"):
                continue
            continue
        if cl.get("grade") not in ("A", "B"):
            continue

        grade = cl["grade"]
        bucket = cl["bucket"]
        source_group = rec.get("source_group")

        # Resolve source_group
        if source_group in ("WHITELIST_57", "OUTSIDE_57"):
            sg = source_group
        else:
            sg = "UNKNOWN_LEGACY"

        is_hit = (bucket == "hit")

        # AB_ALL
        groups["AB_ALL"]["sample_count"] += 1
        if is_hit:
            groups["AB_ALL"]["hit_count"] += 1
        else:
            groups["AB_ALL"]["miss_count"] += 1

        # AB_<source_group>
        sg_ab_key = f"AB_{sg}"
        if sg_ab_key in groups:
            groups[sg_ab_key]["sample_count"] += 1
            if is_hit:
                groups[sg_ab_key]["hit_count"] += 1
            else:
                groups[sg_ab_key]["miss_count"] += 1

        # A/B_ALL
        grade_all_key = f"{grade}_ALL"
        if grade_all_key in groups:
            groups[grade_all_key]["sample_count"] += 1
            if is_hit:
                groups[grade_all_key]["hit_count"] += 1
            else:
                groups[grade_all_key]["miss_count"] += 1

        # A/B_<source_group>
        grade_sg_key = f"{grade}_{sg}"
        if grade_sg_key in groups:
            groups[grade_sg_key]["sample_count"] += 1
            if is_hit:
                groups[grade_sg_key]["hit_count"] += 1
            else:
                groups[grade_sg_key]["miss_count"] += 1

    # Compute hit rates
    for key, stats in groups.items():
        total = stats["hit_count"] + stats["miss_count"]
        stats["hit_rate"] = round(stats["hit_count"] / total, 4) if total > 0 else 0.0

    return {
        "schema_version": "v4_rolling_validation_layered.v1",
        "layered_stats": groups,
    }


def validate_rolling_input(records: list[dict]) -> list[str]:
    """Validate that records have required fields for rolling."""
    errors = []
    required = ["original_grade", "attribution_status"]
    for i, rec in enumerate(records):
        for field in required:
            if field not in rec:
                errors.append(f"Record {i}: missing required field '{field}'")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true", help="Validate input only")
    parser.add_argument("--dry-run", action="store_true", help="Run classification without output")
    parser.add_argument("--records-file", default=None, help="Path to attribution records JSON")
    args = parser.parse_args()

    if args.validate_only:
        print("[VALIDATE-ONLY] Rolling validation module ready.")
        print("[VALIDATE-ONLY] No API, no writes, no side effects.")
        return

    if not args.records_file:
        print("[ERROR] --records-file required (or use --validate-only)")
        sys.exit(1)

    with open(args.records_file, "r") as f:
        records = json.load(f)

    errors = validate_rolling_input(records)
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        sys.exit(1)

    result = build_grade_bucket(records)
    if args.dry_run:
        result["dry_run"] = True
        result["file_written"] = False
        print(f"[DRY-RUN] Rolling validation computed but NOT written.")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
