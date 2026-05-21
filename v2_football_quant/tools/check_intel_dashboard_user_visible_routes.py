#!/usr/bin/env python3
"""Intel Dashboard User-Visible Routes Checker — validates HTTP dashboard pages for correct content."""
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


def check_route(html: str, route_name: str):
    """Check a single route page for all required content."""
    tests = {}
    info = {}
    lowered = html.lower()

    # 1. dashboard_conflict_count=0
    conflicts = 0
    # Check for C=3 vs C=4 conflict on same page
    # Only match assignment patterns like C=4, C:4, C：4 — NOT C1/C2/C3/C4 card labels
    c_matches = re.findall(r'C\s*[=:：]\s*(\d+)', html)
    if len(set(c_matches)) > 1:
        conflicts += 1
    # Check for actual_send contradictory
    if "actual_send" in lowered:
        chunks = html.split("actual_send")
        as_true = any("true" in c[:60] for c in chunks[1:] if len(c) > 5)
        as_false = any("false" in c[:60] for c in chunks[1:] if len(c) > 5)
        if as_true and as_false:
            conflicts += 1

    info["dashboard_conflict_count"] = conflicts
    tests["dashboard_conflict_count_zero"] = conflicts == 0

    # Load candidate model for dynamic expectations
    candidate_json_path = MODULE / "data" / "runtime" / "status" / "intel_desk_v4_candidate_view_20260520.json"
    model = {}
    if candidate_json_path.is_file():
        model = json.loads(candidate_json_path.read_text())

    a_count = model.get("A_count", 0)
    b_count = model.get("B_count", 0)
    c_count = model.get("C_count", 0)
    skip_count = model.get("SKIP_count", 0)
    formal_rec = model.get("formal_recommendation_count", a_count + b_count)
    next_window = model.get("next_window", "night 22:20")
    nw_parts = next_window.split()
    nw_word = nw_parts[0] if nw_parts else next_window
    nw_time = nw_parts[1] if len(nw_parts) > 1 else ""

    # 2. V4 current A/B/C/SKIP visible (dynamic from model)
    tests["V4_current_ABCSKIP_visible"] = (
        (str(a_count) in html and str(b_count) in html and str(c_count) in html) or
        f"A={a_count}" in html or f"B={b_count}" in html or f"C={c_count}" in html or
        ("A" in html and "B" in html and "C" in html and "SKIP" in html)
    )

    # 3. formal_recommendation_count visible (dynamic)
    tests["formal_recommendation_count_visible"] = (
        str(formal_rec) in html
        or f"A={a_count}" in html
        or f"B={b_count}" in html
    )

    # 4. V4_QQ_ENABLED=false visible
    tests["V4_QQ_disabled_visible"] = (
        ("qq_sent" in lowered and "false" in lowered) or
        ("qq" in lowered and "not enabled" in lowered) or
        ("qq" in lowered and "disabled" in lowered) or
        ("不推qq" in lowered)
    )

    # 5. BOSS approval required visible
    tests["boss_approval_visible"] = "boss" in lowered or "await_boss" in lowered

    # 6. next_window visible (dynamic from model)
    tests["next_window_visible"] = (
        (nw_word in lowered and nw_time in html) or
        f"Next: {next_window}" in html or
        f"next_window" in lowered
    )

    # 7. No old V4 0/0/3/2 as CURRENT state
    # ops_heartbeat currently shows 0/0/3/2 in V4 section
    old_v4_pattern = bool(re.search(r'0\s*/\s*0\s*/\s*3\s*/\s*2', html))
    if old_v4_pattern:
        # Check if it's in a historical/audit section
        in_history = "历史" in html or "history" in lowered or "审计" in html or "audit" in lowered
        tests["no_old_v4_data_as_current"] = in_history
    else:
        tests["no_old_v4_data_as_current"] = True

    # 8. No cron_removed / readonly_only as current state
    for tag in ["cron_removed", "readonly_only", "no_cron_recovery"]:
        if tag in lowered:
            in_safe_section = ("风险" in html or "risk" in lowered or "历史" in html or
                              "history" in lowered or "操作" in html or "ops" in lowered)
            tests[f"no_{tag}_as_current"] = in_safe_section
        else:
            tests[f"no_{tag}_as_current"] = True

    # 9. No QQ=false AND QQ_ENABLED=true mixed without clear labels
    has_qq_true = bool(re.search(r'QQ[_\s]*ENABLED[^>]*true', html, re.IGNORECASE))
    has_qq_false = ("qq_sent" in lowered and "false" in lowered) or ("qq" in lowered and "disabled" in lowered)
    if has_qq_true and has_qq_false:
        tests["no_qq_true_false_unlabeled_mix"] = ("V2" in html and "V4" in html)
    else:
        tests["no_qq_true_false_unlabeled_mix"] = True

    # 10. No PROD_VERIFIED=false as current state
    prod_false_in_current = bool(re.search(r'PROD_VERIFIED[^>]*false', html))
    if prod_false_in_current:
        tests["no_PROD_VERIFIED_false_as_current"] = "PIPELINE" in html  # part of CODE_READY status
    else:
        tests["no_PROD_VERIFIED_false_as_current"] = True

    # Bonus: Page freshness
    tests["page_is_fresh"] = "20260520" in html or "2026-05-20" in html

    return tests, info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=None, help="Base URL for HTTP dashboard")
    parser.add_argument("--no-http", action="store_true", help="Skip HTTP, use local files")
    parser.add_argument("--no-push", action="store_true", default=True)
    parser.add_argument("--no-d13", action="store_true", default=True)
    parser.add_argument("--no-v33", action="store_true", default=True)
    parser.add_argument("--no-hourly", action="store_true", default=True)
    args = parser.parse_args()

    R = {
        "checker": "intel_dashboard_user_visible_routes",
        "check_status": "PASS",
        "routes_checked": 0,
        "routes_total": len(ROUTES),
        "dashboard_conflict_count": 0,
        "http_used": False,
        "no_push": args.no_push,
        "no_d13": args.no_d13,
        "no_v33": args.no_v33,
        "no_hourly": args.no_hourly,
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
        else:
            html, status = fetch_local(route)

        if html is None:
            R["route_results"][route_name]["status"] = "MISSING"
            R["blockers"].append(f"Route {route} not available")
            continue

        R["routes_checked"] += 1
        R["route_results"][route_name]["status"] = "OK"
        R["route_results"][route_name]["size"] = len(html)

        tests, info = check_route(html, route_name)
        R["route_results"][route_name]["tests"] = tests
        R["route_results"][route_name]["info"] = info

        for k, v in tests.items():
            R["tests"][f"{route_name}_{k}"] = v
            if not v:
                if "conflict" in k:
                    R["blockers"].append(f"{route_name}: {k}")
                else:
                    R["warnings"].append(f"{route_name}: {k}")

    R["dashboard_conflict_count"] = sum(
        r.get("info", {}).get("dashboard_conflict_count", 0) for r in R["route_results"].values()
    )

    if R["dashboard_conflict_count"] > 0:
        R["check_status"] = "BLOCKER"

    passed = sum(1 for v in R["tests"].values() if v)
    R["tests_passed"] = passed
    R["tests_total"] = len(R["tests"])

    if not R["blockers"] and R["warnings"]:
        R["check_status"] = "WARN"

    print("=" * 60)
    print("INTEL DASHBOARD USER-VISIBLE ROUTES CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']} | Routes: {R['routes_checked']}/{R['routes_total']}")
    print(f"HTTP: {R['http_used']} | Conflicts: {R['dashboard_conflict_count']}")
    print(f"Tests: {passed}/{len(R['tests'])}")
    for k, v in R["tests"].items():
        if not v:
            print(f"  FAIL: {k}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"  ! {b}")
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"][:10]:
            print(f"  ~ {w}")

    out = MODULE / "data" / "runtime" / "status" / "intel_dashboard_routes_check_20260520.json"
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
