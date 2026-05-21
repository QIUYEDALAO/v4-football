#!/usr/bin/env python3
"""V4 Candidate View Builder — permanent builder for intel_desk_v4_candidate_view JSON.

Uses v4_today_source_resolver to extract goal_time_distribution from scout_v4
with proper source priority (recent_time_bins > time_bins > existing > unavailable).
Applies v4_script_classifier with BOSS-directed formal 9-type taxonomy.

Reads:  data/daily_reports/scout_v4_{date}.json
        data/runtime/status/intel_desk_v4_candidate_view_{date}.json (for grade/window metadata)
Writes: data/runtime/status/intel_desk_v4_candidate_view_{date}.json (enriched)
Calls:  tools/generate_intel_desk_html.py (to regenerate HTML)
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))

# Import project modules
sys.path.insert(0, str(MODULE / "tools"))
from v4_today_source_resolver import extract_goal_time_distribution, extract_candidate_entries
from v4_script_classifier import classify_script, get_display_script


def get_home_away(entry):
    """Extract (home, away) from a candidate entry, handling both 'home'/'away' and 'match' fields."""
    home = entry.get("home")
    away = entry.get("away")
    if not home and not away:
        match = entry.get("match", "")
        parts = match.split(" vs ")
        if len(parts) == 2:
            home, away = parts[0], parts[1]
    return home, away


def match_scout_to_candidate(candidate_entry, scout_map):
    """Find matching scout entry for a candidate by home/away name."""
    home, away = get_home_away(candidate_entry)
    home = (home or "").lower().strip()
    away = (away or "").lower().strip()
    if not home or not away:
        return None
    key = f"{home} vs {away}"
    if key in scout_map:
        return scout_map[key]
    for k, v in scout_map.items():
        if home in k and away in k:
            return v
    return None


def build_candidate_view(date_str=None):
    """Build enriched candidate view JSON with time_bins and script classification."""
    if date_str is None:
        date_str = datetime.now(CN_TZ).strftime("%Y%m%d")

    scout_file = MODULE / "data" / "daily_reports" / f"scout_v4_{date_str}.json"
    cv_file = MODULE / "data" / "runtime" / "status" / f"intel_desk_v4_candidate_view_{date_str}.json"

    if not scout_file.is_file():
        print(f"ERROR: scout file not found: {scout_file}", file=sys.stderr)
        return None
    if not cv_file.is_file():
        print(f"ERROR: candidate view file not found: {cv_file}", file=sys.stderr)
        return None

    scout = json.loads(scout_file.read_bytes())
    cv = json.loads(cv_file.read_bytes())
    scout_path = str(scout_file.relative_to(MODULE))

    # Build scout lookup by home/away
    raw_entries = extract_candidate_entries(
        scout if isinstance(scout, list) else scout.get("matches", []),
        scout_path,
    )
    scout_map = {}
    for e in raw_entries:
        home = (e.get("home") or "").lower().strip()
        away = (e.get("away") or "").lower().strip()
        if home and away:
            scout_map[f"{home} vs {away}"] = e
            # Also index home alone for fuzzy matching
            scout_map[home] = e

    fixed_count = 0

    # Enrich A candidate
    a = cv.get("A_candidate")
    if a:
        sm = match_scout_to_candidate(a, scout_map)
        if sm and sm["goal_time_distribution"]["available"]:
            a["goal_time_distribution"] = sm["goal_time_distribution"]
            display = get_display_script(a)
            a["script_type"] = display["script_type"]
            a["script_reason"] = display["script_reason"]
            a["distribution_text"] = display["distribution_text"]
            a["expected_goals"] = display["expected_goals_display"]
            a["strength_pct"] = display["strength_pct"]
            a_home, a_away = get_home_away(a)
            a["home"] = a_home or a.get("home")
            a["away"] = a_away or a.get("away")
            fixed_count += 1
            print(f"  A: {a_home} vs {a_away} -> {a['script_type']} | {a['distribution_text']}")

    # Enrich B candidates
    for b in cv.get("B_candidates", []):
        sm = match_scout_to_candidate(b, scout_map)
        if sm and sm["goal_time_distribution"]["available"]:
            b["goal_time_distribution"] = sm["goal_time_distribution"]
            display = get_display_script(b)
            b["script_type"] = display["script_type"]
            b["script_reason"] = display["script_reason"]
            b["distribution_text"] = display["distribution_text"]
            b["expected_goals"] = display["expected_goals_display"]
            b["strength_pct"] = display["strength_pct"]
            fixed_count += 1
            print(f"  B{b.get('index')}: {b.get('home')} vs {b.get('away')} -> {b['script_type']} | {b['distribution_text']}")

    # Enrich C candidates
    for c in cv.get("C_candidates", []):
        sm = match_scout_to_candidate(c, scout_map)
        if sm and sm["goal_time_distribution"]["available"]:
            c["goal_time_distribution"] = sm["goal_time_distribution"]
            display = get_display_script(c)
            c["script_type"] = display["script_type"]
            c["script_reason"] = display["script_reason"]
            c["distribution_text"] = display["distribution_text"]
            fixed_count += 1
            print(f"  C{c.get('index')}: {c.get('home')} vs {c.get('away')} -> {c['script_type']} | {c['distribution_text']}")

    if fixed_count == 0:
        print("WARNING: No entries were enriched. Check scout/candidate name matching.")
        return cv

    # Update metadata
    cv["time_bins_source"] = "scout_v4 -> factors.recent_time_bins"
    cv["time_bins_priority"] = "1. recent_time_bins > 2. time_bins(non-zero) > 3. existing > 4. unavailable"
    cv["script_taxonomy_version"] = "1.0.0"
    cv["script_taxonomy_source"] = "data/runtime/status/v4_script_taxonomy_20260520.json"
    cv["builder_script"] = "tools/v4_build_candidate_view.py"
    cv["built_at"] = datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # Write
    cv_json = json.dumps(cv, ensure_ascii=False, indent=2)
    cv_file.write_text(cv_json)
    print(f"\nWrote {fixed_count} enriched entries to {cv_file}")

    return cv


def regenerate_html():
    """Call generate_intel_desk_html.py to regenerate dashboard HTML from updated candidate view."""
    gen_script = MODULE / "tools" / "generate_intel_desk_html.py"
    if not gen_script.is_file():
        print("WARNING: generate_intel_desk_html.py not found, skipping HTML regeneration")
        return False
    print("\n=== Regenerating HTML ===")
    r = subprocess.run(
        ["python3", str(gen_script)],
        capture_output=True, text=True, timeout=30, cwd=str(MODULE),
    )
    print(r.stdout)
    if r.returncode != 0:
        print("STDERR:", r.stderr)
    return r.returncode == 0


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    cv = build_candidate_view(date_str)
    if cv is None:
        sys.exit(1)
    regenerate_html()
    print("\n=== Candidate view build complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
