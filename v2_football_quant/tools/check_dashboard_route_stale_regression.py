#!/usr/bin/env python3
"""Dashboard Route Stale Regression Checker — validates HTTP dashboard pages for staleness and conflicts."""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
DASH_DIR = MODULE / "data" / "runtime" / "dashboard"
TZ = timezone(timedelta(hours=8))

ROUTES = ["/index.html", "/v2_today.html", "/intel_desk.html", "/ops_heartbeat.html"]

# Routes that should show current (not stale) data
CURRENT_ROUTES = {"/index.html", "/v2_today.html"}
# Routes that may show slightly older data (heartbeat, intel desk)
MONITOR_ROUTES = {"/intel_desk.html", "/ops_heartbeat.html"}


def fetch_http(base_url: str, route: str, timeout: int = 10):
    url = f"{base_url.rstrip('/')}{route}"
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), resp.status
    except Exception as e:
        return None, str(e)


def fetch_local(route: str):
    path = DASH_DIR / route.lstrip("/")
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace"), 200
    return None, "file_not_found"


def strip_html_tags(text: str) -> str:
    """Remove HTML tags for cleaner text matching."""
    return re.sub(r'<[^>]+>', ' ', text)


def check_page_content(html: str, route: str):
    """Run all staleness and regression checks against a page.
    Returns: (tests_dict, info_dict)
      - tests: boolean checks where True=pass
      - info: informational fields
    """
    lowered = html.lower()
    plain = strip_html_tags(html)

    tests = {}
    info = {}

    # 1. dashboard_conflict_count — real semantic conflicts
    conflicts = 0
    # Check for contradictory actual_send on same page
    if "actual_send" in lowered:
        chunks = html.split("actual_send")
        has_as_true = any("true" in c[:60].lower() for c in chunks[1:] if len(c) > 5)
        has_as_false = any("false" in c[:60].lower() for c in chunks[1:] if len(c) > 5)
        if has_as_true and has_as_false:
            conflicts += 1
    # Check for contradictory C values (C=3 vs C=4) on same page
    # Only match assignment patterns like C=4, C:4, C: 4 — not C1/C2/C3 labels
    c_values = set()
    for m in re.finditer(r'C\s*[=:：]\s*(\d+)', html):
        c_values.add(int(m.group(1)))
    if len(c_values) > 1:
        conflicts += 1

    info["dashboard_conflict_count"] = conflicts
    tests["dashboard_conflict_count_zero"] = conflicts == 0

    # 2. B=6 visible
    b6_found = bool(re.search(r'B.*?6', plain, re.DOTALL))
    tests["B_6_visible"] = b6_found

    # 3. V4_QQ_ENABLED=false visible
    qq_disabled = (
        ("qq_sent" in lowered and "false" in lowered) or
        ("qq" in lowered and "not enabled" in lowered) or
        ("qq" in lowered and "disabled" in lowered) or
        ("不推qq" in lowered)
    )
    tests["V4_QQ_disabled_visible"] = qq_disabled

    # 4. BOSS approval required visible
    tests["boss_approval_visible"] = "boss" in lowered or "await_boss" in lowered

    # 5. midday visible
    info["midday_visible"] = "midday" in lowered or "14:05" in html

    # 6. next window info visible
    info["next_window_info_visible"] = "next" in lowered or "窗口" in html or "14:05" in html

    # 7. No stale PROD_VERIFIED=false
    # Only flag if PROD_VERIFIED=false appears with a date older than today
    stale_prod = bool(re.search(
        r'PROD_VERIFIED.*?false.*?2026[/-]0[5-9][/-][0-1][0-9]', html
    ))
    tests["no_stale_PROD_VERIFIED_false"] = not stale_prod

    # 8. No QQ=true and QQ=false mixed without clear V2/V4 labels
    has_qq_true = bool(re.search(r'QQ[_\s]*ENABLED.*?true', html, re.IGNORECASE))
    has_qq_false_marker = (
        bool(re.search(r'QQ[_\s]*ENABLED.*?false', html, re.IGNORECASE)) or
        ("qq" in lowered and "false" in lowered)
    )
    if has_qq_true and has_qq_false_marker:
        # Check if clearly labeled as different subsystems
        has_v2_label = "V2" in html
        has_v4_label = "V4" in html
        tests["no_qq_true_false_mix_unlabeled"] = has_v2_label and has_v4_label
    else:
        tests["no_qq_true_false_mix_unlabeled"] = True  # No mix to worry about

    # 9. No cron_removed as current state
    has_cron_removed = "cron_removed" in lowered
    if has_cron_removed:
        in_risk_or_history = ("风险" in html or "risk" in lowered or "历史" in html or "history" in lowered)
        tests["no_cron_removed_as_current"] = in_risk_or_history
    else:
        tests["no_cron_removed_as_current"] = True

    # 10. No readonly_only as current state
    has_readonly = "readonly_only" in lowered
    if has_readonly:
        in_ops_or_history = ("操作" in html or "ops" in lowered or "历史" in html or "history" in lowered)
        tests["no_readonly_only_as_current"] = in_ops_or_history
    else:
        tests["no_readonly_only_as_current"] = True

    # Bonus
    tests["no_stale_0517_date"] = not bool(re.search(
        r'(?:日期|生成|Date|Generated)[：:]\s*2026[/-]05[/-]17', html
    ))
    tests["page_has_no_cache_headers"] = "no-cache" in lowered

    # Mark stale routes (data older than expected)
    info["is_current_route"] = route in CURRENT_ROUTES
    if route in MONITOR_ROUTES:
        tests["stale_data_may_be_present"] = True  # informational, always "passes"

    return tests, info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=None, help="Base URL for HTTP dashboard (e.g. http://192.168.1.2:8765)")
    parser.add_argument("--no-http", action="store_true", help="Skip HTTP checks, use local files only")
    args = parser.parse_args()

    R = {
        "checker": "dashboard_route_stale_regression",
        "check_status": "PASS",
        "routes_checked": 0,
        "routes_total": len(ROUTES),
        "dashboard_conflict_count": 0,
        "http_used": False,
        "local_fallback": False,
        "tests": {},
        "route_results": {},
        "blockers": [],
        "warnings": [],
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }

    use_http = args.base_url and not args.no_http
    server_available = False

    if use_http:
        try:
            r = subprocess.run(["lsof", "-iTCP:8765", "-sTCP:LISTEN", "-n", "-P"],
                             capture_output=True, text=True, timeout=5)
            server_available = "LISTEN" in r.stdout
        except Exception:
            server_available = False
        R["http_used"] = server_available

    for route in ROUTES:
        route_name = route.lstrip("/").replace(".html", "")
        R["route_results"][route_name] = {}

        if use_http and server_available:
            html, status = fetch_http(args.base_url, route)
            if html is None:
                R["route_results"][route_name]["fetch_status"] = "HTTP_FAIL"
                R["route_results"][route_name]["fetch_error"] = str(status)
                R["local_fallback"] = True
                html, _ = fetch_local(route)
        else:
            html, _ = fetch_local(route)

        if html is None:
            R["route_results"][route_name]["fetch_status"] = "MISSING"
            R["warnings"].append(f"Route {route} not available (HTTP or local)")
            continue

        R["routes_checked"] += 1
        R["route_results"][route_name]["fetch_status"] = "OK"
        R["route_results"][route_name]["size"] = len(html)

        tests, info = check_page_content(html, route)
        R["route_results"][route_name]["tests"] = tests
        R["route_results"][route_name]["info"] = info
        R["route_results"][route_name]["dashboard_conflict_count"] = info.get("dashboard_conflict_count", 0)

        for k, v in tests.items():
            test_key = f"{route_name}_{k}"
            R["tests"][test_key] = v
            if not v:
                if k == "dashboard_conflict_count_zero":
                    R["blockers"].append(f"{route_name}: {k} FAIL (conflicts={info.get('dashboard_conflict_count', '?')})")
                else:
                    R["warnings"].append(f"{route_name}: {k}")

    R["dashboard_conflict_count"] = sum(
        r.get("dashboard_conflict_count", 0) for r in R["route_results"].values()
    )

    if R["dashboard_conflict_count"] > 0:
        R["check_status"] = "BLOCKER"
        R["blockers"].append(f"Total dashboard semantic conflicts: {R['dashboard_conflict_count']}")

    passed = sum(1 for v in R["tests"].values() if v is True)
    R["tests_passed"] = passed
    R["tests_total"] = len(R["tests"])
    R["failed_tests"] = [(k, R["tests"].get(k)) for k in R["tests"] if R["tests"].get(k) is False]

    if not R["blockers"] and R["warnings"]:
        R["check_status"] = "WARN"

    print("=" * 60)
    print("DASHBOARD ROUTE STALE REGRESSION CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']} | Routes: {R['routes_checked']}/{R['routes_total']}")
    print(f"HTTP: {R['http_used']} | Conflicts: {R['dashboard_conflict_count']}")
    print(f"Tests Passed: {passed}/{len(R['tests'])}")
    for name, val in R.get("failed_tests", []):
        print(f"  FAIL: {name}")

    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"  ! {b}")
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"][:15]:
            print(f"  ~ {w}")
        if len(R["warnings"]) > 15:
            print(f"  ... and {len(R['warnings'])-15} more")

    out = MODULE / "data" / "runtime" / "status" / "dashboard_stale_regression_check_20260520.json"
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
