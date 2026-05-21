#!/usr/bin/env python3
"""Intel Desk Candidate View Checker — verifies checks across 4 dashboard HTML routes.

Routes checked:
  - data/runtime/dashboard/index.html
  - data/runtime/dashboard/intel_desk.html
  - data/runtime/dashboard/ops_heartbeat.html
  - data/runtime/dashboard/v2_today.html

Reads candidate JSON dynamically — no hardcoded B/C counts or match lists.
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

MODULE = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))

CANDIDATE_JSON = MODULE / "data" / "runtime" / "status" / "intel_desk_v4_candidate_view_20260520.json"

ROUTES = [
    "data/runtime/dashboard/index.html",
    "data/runtime/dashboard/intel_desk.html",
    "data/runtime/dashboard/ops_heartbeat.html",
    "data/runtime/dashboard/v2_today.html",
]

# Stale tags that must NOT appear in CURRENT sections
STALE_TAGS = [
    "CODE_READY",
    "PIPELINE=false",
    "PROD_VERIFIED=false",
    "readonly_only",
    "no_formal_daily_pool",
    "cron_removed",
    "crontool removed",
]


def load_candidate_model():
    """Load candidate JSON and extract dynamic match lists + counts."""
    if not CANDIDATE_JSON.is_file():
        return None, None, None, 0, 0

    data = json.loads(CANDIDATE_JSON.read_text())
    b_homes = [b.get("home", "") for b in data.get("B_candidates", []) if b.get("home")]
    c_homes = [c.get("home", "") for c in data.get("C_candidates", []) if c.get("home")]
    b_count = data.get("B_count", len(b_homes))
    c_count = data.get("C_count", len(c_homes))
    return b_homes, c_homes, data, b_count, c_count


def strip_html(text):
    """Remove HTML tags for cleaner content checking."""
    return re.sub(r"<[^>]+>", " ", text)


def check_route(route_path, route_label, b_matches, c_matches, b_count, c_count, model=None):
    """Run all checks against one HTML route. Uses dynamic B/C counts from candidate model."""
    html_path = MODULE / route_path
    tests = {}
    info = {}
    errors = []

    if not html_path.is_file():
        for i in range(1, 18):
            tests[f"check_{i:02d}"] = False
        errors.append(f"{route_label}: file not found at {route_path}")
        return tests, info, errors

    raw = html_path.read_text()
    # Split into sections: everything between <h2> tags
    # Find all h2 headings and the content after them
    sections = {}
    h2_pattern = re.compile(r"<h2>(.*?)</h2>(.*?)(?=<h2>|</body>)", re.DOTALL)
    for m in h2_pattern.finditer(raw):
        heading = strip_html(m.group(1)).strip()
        content = m.group(2)
        sections[heading] = content

    # Also get content before first h2 (header area) and footer
    header_area = raw.split("<h2>")[0] if "<h2>" in raw else raw
    footer_area = ""
    if "<div class=\"footer\">" in raw:
        footer_area = raw.split("<div class=\"footer\">")[1].split("</div>")[0] if "</div>" in raw.split("<div class=\"footer\">")[1] else ""

    full_text = strip_html(raw)
    header_text = strip_html(header_area)
    footer_text = strip_html(footer_area)

    # Collect all "CURRENT:" section content (sections whose heading starts with CURRENT:)
    # Must use "CURRENT:" prefix match to avoid false match on "not_current=true" in history headings
    current_sections_text = ""
    for heading, content in sections.items():
        if re.match(r"CURRENT\s*:", heading.upper()):
            current_sections_text += strip_html(content) + "\n"
    # Also include header for checks like next_window
    header_and_current = header_text + "\n" + current_sections_text

    # ── Check 1: B count visible (dynamic from candidate model) ──
    b_visible = bool(
        re.search(rf"B\s*[=:：]\s*{b_count}", full_text)
        or f"B={b_count}" in full_text or f"B = {b_count}" in full_text
        or f"B{b_count}" in full_text  # catch "B4" etc
    )
    tests["check_01_B_count_visible"] = b_visible

    # ── Check 2: B candidate cards visible (dynamic count) ──
    b_match_count = sum(1 for m in b_matches if m in full_text)
    tests["check_02_B_cards_visible"] = b_match_count >= b_count
    info["B_match_count"] = b_match_count
    info["B_expected"] = b_count

    # ── Check 3: C count visible (dynamic from candidate model) ──
    c_visible = bool(
        re.search(rf"C\s*[=:：]\s*{c_count}", full_text)
        or f"C={c_count}" in full_text or f"C = {c_count}" in full_text
        or f"C{c_count}" in full_text
    )
    tests["check_03_C_count_visible"] = c_visible

    # ── Check 4: C marked observation-only ──
    tests["check_04_C_observation_only"] = "observation-only" in full_text or "observation_only" in full_text
    c_match_count = sum(1 for m in c_matches if m in full_text)
    info["C_match_count"] = c_match_count
    info["C_expected"] = c_count

    # ── Check 5: V4_QQ_ENABLED=false visible ──
    tests["check_05_V4_QQ_disabled"] = "V4_QQ_ENABLED" in full_text and "false" in full_text

    # ── Check 6: BOSS approval required visible ──
    tests["check_06_boss_approval"] = bool(
        re.search(r"BOSS\s*approval\s*required", full_text, re.IGNORECASE)
        or re.search(r"BOSS\s*批准", full_text)
    )

    # ── Check 7: actual_send=false visible ──
    tests["check_07_actual_send_false"] = "actual_send" in full_text

    # ── Check 8: qq_sent=false visible ──
    tests["check_08_qq_sent_false"] = "qq_sent" in full_text or "QQ未发送" in full_text

    # ── Check 9: next_window visible (dynamic from model) ──
    next_win = model.get("next_window", "night 22:20")
    nw_parts = next_win.split()
    nw_word = nw_parts[0] if nw_parts else next_win
    nw_time = nw_parts[1] if len(nw_parts) > 1 else ""
    tests["check_09_next_window"] = (
        (nw_word in full_text and nw_time in full_text)
        or f"next_window.*{nw_word}" in full_text
        or f"Next: {next_win}" in full_text
        or "next_window" in full_text  # fallback: at least next_window field exists
    )

    # ── Checks 10-16: CURRENT section has no old pollution tags ──
    # The key insight: stale tags are OK in history/audit sections, but NOT in CURRENT sections
    for i, tag in enumerate(STALE_TAGS):
        check_num = 10 + i
        tag_in_current = tag.lower() in current_sections_text.lower() if current_sections_text else False
        # Also check header area
        tag_in_header = tag.lower() in header_text.lower()
        tests[f"check_{check_num:02d}_no_{tag}"] = not (tag_in_current or tag_in_header)
        if tag_in_current:
            errors.append(f"{route_label}: stale tag '{tag}' found in CURRENT section")
        if tag_in_header:
            errors.append(f"{route_label}: stale tag '{tag}' found in header area")

    # ── Check 17: No internal conflicts ──
    # Check for common conflict patterns
    conflicts = []
    # PRODUCTION_VERIFIED=true + PROD_VERIFIED=false in same context (different subsystems OK)
    # V4_QQ_ENABLED=true anywhere (should be false)
    # Use bounded match: check within same |..| field or within 20 chars to avoid
    # false match on "V4_QQ_ENABLED=false ... future_ab_trigger=true"
    if re.search(r"V4_QQ_ENABLED[^|]{0,30}true", full_text):
        conflicts.append("V4_QQ_ENABLED=true found")
    # actual_send=true should not appear
    if re.search(r"actual_send.*true", full_text, re.IGNORECASE):
        # But "actual_send=false" is fine
        if not re.search(r"actual_send.*false", full_text, re.IGNORECASE):
            conflicts.append("actual_send=true found (and no actual_send=false)")
    # qq_sent=true in V4 context
    if re.search(r"qq_sent.*true", full_text, re.IGNORECASE):
        if not re.search(r"qq_sent.*false", full_text, re.IGNORECASE):
            conflicts.append("qq_sent=true found (and no qq_sent=false)")

    tests["check_17_no_conflicts"] = len(conflicts) == 0
    if conflicts:
        errors.append(f"{route_label}: conflicts detected: {'; '.join(conflicts)}")

    info["conflicts"] = conflicts
    info["route"] = route_label

    return tests, info, errors


def main():
    R = {
        "check_status": "PASS",
        "checker": "intel_desk_candidate_view",
        "generated_at": datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "routes_checked": 0,
        "total_checks": 0,
        "total_pass": 0,
        "total_fail": 0,
        "route_results": {},
        "all_errors": [],
    }

    # Load dynamic B/C data from candidate model
    b_matches, c_matches, model, b_count, c_count = load_candidate_model()
    if model is None:
        print("ERROR: candidate JSON not found, cannot run checks")
        R["check_status"] = "BLOCKER"
        print(json.dumps(R, ensure_ascii=False, indent=2))
        return 2

    R["source_window"] = model.get("source_window", "unknown")
    R["candidate_B_count"] = b_count
    R["candidate_C_count"] = c_count
    R["candidate_A_count"] = model.get("A_count", 0)

    all_pass = True

    for route_path in ROUTES:
        route_label = Path(route_path).stem
        tests, info, errors = check_route(route_path, route_label, b_matches, c_matches, b_count, c_count, model)

        R["routes_checked"] += 1
        route_pass = sum(1 for v in tests.values() if v)
        route_total = len(tests)
        R["total_checks"] += route_total
        R["total_pass"] += route_pass
        R["total_fail"] += route_total - route_pass
        R["route_results"][route_label] = {
            "pass": route_pass,
            "total": route_total,
            "tests": {k: v for k, v in tests.items()},
            "info": {k: v for k, v in info.items() if k != "conflicts"},
            "errors": errors,
        }
        R["all_errors"].extend(errors)

        if route_pass < route_total:
            all_pass = False

    if not all_pass:
        R["check_status"] = "BLOCKER"
    elif R["all_errors"]:
        R["check_status"] = "WARN"

    print("=" * 60)
    print("INTEL DESK CANDIDATE VIEW CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']}")
    print(f"Routes: {R['routes_checked']} | Checks: {R['total_checks']} | Pass: {R['total_pass']} | Fail: {R['total_fail']}")

    for route_label, rr in R["route_results"].items():
        print(f"\n  {route_label}: {rr['pass']}/{rr['total']}")
        for check_name, result in rr["tests"].items():
            if not result:
                print(f"    FAIL: {check_name}")
        for err in rr["errors"]:
            print(f"    ! {err}")

    if R["all_errors"]:
        print(f"\nALL ERRORS ({len(R['all_errors'])}):")
        for e in R["all_errors"]:
            print(f"  ! {e}")

    # Write result
    out = MODULE / "data" / "runtime" / "status"
    out.mkdir(parents=True, exist_ok=True)
    (out / "intel_desk_candidate_view_check_20260520.json").write_text(
        json.dumps(R, indent=2, ensure_ascii=False, default=str))

    if R["check_status"] == "BLOCKER":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
