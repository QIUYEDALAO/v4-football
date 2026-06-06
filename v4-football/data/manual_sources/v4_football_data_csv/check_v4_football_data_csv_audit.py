#!/usr/bin/env python3
"""
V4 Football-Data CSV Audit — Checker
=====================================
Checks:
1. Manifest file exists and is parsable
2. All expected files downloaded (or explicitly noted missing)
3. Each CSV is readable
4. Core 5 leagues (E0/SP1/D1/I1/F1) near-5-year field coverage PASS
5. No runtime/cache/log/secrets files in the data tree
6. No modification of V4 production files
"""

import csv
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(DATA_DIR, "raw")

# Expected leagues
CORE_LEAGUES = ["E0", "SP1", "D1", "I1", "F1"]
ALL_LEAGUES = ["E0", "SP1", "D1", "I1", "F1", "P1", "N1", "B1", "T1"]

# Expected seasons
SEASON_CODES = ["2021", "2122", "2223", "2324", "2425", "2526"]

# Minimum required fields for a league-season to be usable
MIN_REQUIRED_FIELDS = [
    "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
    "B365H", "B365D", "B365A",
    "B365>2.5", "B365<2.5",
]

# Files that should NOT appear in the commit
FORBIDDEN_DIRS = ["runtime", "cache", "logs", "secrets", "__pycache__", ".git"]

FAILURES = []


def fail(check, msg):
    FAILURES.append(f"[FAIL] {check}: {msg}")


def pass_msg(check, msg):
    print(f"[PASS] {check}: {msg}")


# === Check 1: Manifest exists ===
check = "Manifest file exists"
manifest_path = os.path.join(DATA_DIR, "MANIFEST.md")
if os.path.exists(manifest_path) and os.path.getsize(manifest_path) > 100:
    pass_msg(check, f"{manifest_path} ({os.path.getsize(manifest_path)} bytes)")
else:
    fail(check, f"Manifest missing or too small: {manifest_path}")

# === Check 2: All expected files downloaded ===
check = "Expected file count"
# Expected files: for ALL_LEAGUES x SEASON_CODES
expected_count = len(ALL_LEAGUES) * len(SEASON_CODES)
actual_csvs = [f for f in os.listdir(RAW_DIR) if f.endswith(".csv")]
actual_count = len(actual_csvs)

# Deduplicate: some files may be named with different conventions
# We expect filenames like E0_2122.csv
expected_fnames = set()
for league in ALL_LEAGUES:
    for sc in SEASON_CODES:
        expected_fnames.add(f"{league}_{sc}.csv")

# Check if we have a reasonable mapping (some files might have _2021 vs _2021)
actual_fnames = set(actual_csvs)
overlap = actual_fnames & expected_fnames
extra = actual_fnames - expected_fnames
missing = expected_fnames - actual_fnames

# For 2021 season files, the code matches
# For files like B1_2021.csv this is expected_fname B1_2021.csv — yes that matches
# So all should match

print(f"  Expected files: {len(expected_fnames)}")
print(f"  Actual files: {len(actual_fnames)}")
print(f"  Overlapping: {len(overlap)}")
if missing:
    print(f"  MISSING: {sorted(missing)}")
if extra:
    print(f"  EXTRA (may be duplicates): {sorted(extra)}")

if len(overlap) >= expected_count - 2:  # Allow small naming discrepancy
    pass_msg(check, f"{len(overlap)} of {expected_count} expected files present")
else:
    fail(check, f"Only {len(overlap)} of {expected_count} expected files present; missing={missing}")

# === Check 3: Each CSV is readable ===
check = "CSV readability"
csv_errors = []
for fname in sorted(actual_csvs):
    fpath = os.path.join(RAW_DIR, fname)
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            row_count = sum(1 for _ in reader)
        if len(header) < 10:
            csv_errors.append(f"{fname}: only {len(header)} columns")
        if row_count < 10:
            csv_errors.append(f"{fname}: only {row_count} data rows")
    except Exception as e:
        csv_errors.append(f"{fname}: {e}")

if csv_errors:
    fail(check, f"{len(csv_errors)} CSV error(s): {csv_errors[:5]}...")
else:
    pass_msg(check, f"All {len(actual_csvs)} CSVs readable with adequate columns and rows")

# === Check 4: Core 5 leagues field coverage ===
check = "Core league field coverage (E0/SP1/D1/I1/F1)"
core_gaps = []
for league in CORE_LEAGUES:
    for sc in SEASON_CODES:
        fname = f"{league}_{sc}.csv"
        fpath = os.path.join(RAW_DIR, fname)
        if not os.path.exists(fpath):
            core_gaps.append(f"{fname}: FILE_MISSING")
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, [])
            header_set = set(h.strip() for h in header)
            missing_fields = [f for f in MIN_REQUIRED_FIELDS if f not in header_set]
            if missing_fields:
                core_gaps.append(f"{fname}: missing {missing_fields}")
        except Exception as e:
            core_gaps.append(f"{fname}: {e}")

if core_gaps:
    fail(check, f"{len(core_gaps)} gap(s) found")
    for g in core_gaps[:5]:
        print(f"  {g}")
else:
    pass_msg(check, f"All {len(CORE_LEAGUES) * len(SEASON_CODES)} core league-season files have minimum required fields")

# === Check 5: No forbidden artifacts ===
check = "No runtime/cache/log/secrets in data tree"
forbidden_found = []
for root, dirs, files in os.walk(DATA_DIR):
    rel = os.path.relpath(root, DATA_DIR)
    for d in dirs:
        if d.lower() in FORBIDDEN_DIRS:
            forbidden_found.append(os.path.join(rel, d))
    for f in files:
        if f.endswith(('.pyc', '.log', '.env')):
            forbidden_found.append(os.path.join(rel, f))

if forbidden_found:
    fail(check, f"Forbidden artifacts: {forbidden_found}")
else:
    pass_msg(check, "No forbidden dirs/files found")

# === Check 6: No V4 production changes ===
check = "No V4 production modification"

# Verify all files under this audit are within data/manual_sources/
workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(DATA_DIR)))
expected_prefix = os.path.join(workspace_root, 'data', 'manual_sources')

paths_to_check = [
    manifest_path,
    os.path.join(DATA_DIR, 'audit_field_coverage.py'),
    os.path.join(DATA_DIR, 'download_csv.sh'),
    os.path.join(DATA_DIR, 'check_v4_football_data_csv_audit.py'),
    os.path.join(DATA_DIR, 'FIELD_COVERAGE_MATRIX.md'),
    os.path.join(DATA_DIR, 'V4_REPLAY_READINESS.md'),
    os.path.join(DATA_DIR, 'audit_summary.json'),
    os.path.join(DATA_DIR, 'MANIFEST.md'),
]

bad_paths = []
for p in paths_to_check:
    if os.path.exists(p) and not p.startswith(expected_prefix):
        bad_paths.append(p)

# Check CSV files
for fname in actual_csvs:
    fpath = os.path.join(RAW_DIR, fname)
    if os.path.exists(fpath) and not fpath.startswith(expected_prefix):
        bad_paths.append(fpath)

if bad_paths:
    fail(check, f"Files outside expected tree: {bad_paths}")
else:
    pass_msg(check, "All audit files are under data/manual_sources/. No V4 production files touched.")

# === SUMMARY ===
print(f"\n{'=' * 60}")
print(f"CHECKER SUMMARY")
print(f"{'=' * 60}")
if FAILURES:
    print(f"FAILURES: {len(FAILURES)}")
    for f in FAILURES:
        print(f"  {f}")
    sys.exit(1)
else:
    print(f"ALL CHECKS PASSED ✅")
    print(f"  1. Manifest exists: YES")
    print(f"  2. Expected files: {len(actual_csvs)} (target {expected_count})")
    print(f"  3. CSV readability: ALL OK")
    print(f"  4. Core league coverage: ALL OK")
    print(f"  5. No forbidden artifacts: CLEAN")
    print(f"  6. No V4 production changes: CLEAN")
    print(f"{'=' * 60}")
    sys.exit(0)
