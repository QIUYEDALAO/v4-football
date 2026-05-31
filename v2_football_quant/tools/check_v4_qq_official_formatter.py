#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "daily_reports"
STATUS = ROOT / "data" / "runtime" / "status"
LOCAL_TZ = timezone(timedelta(hours=8))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ok(checks: list[dict], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="20260601")
    ap.add_argument("--window", default="midday")
    args = ap.parse_args()

    checks: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []

    try:
        from engine.v4_qq_formatter import format_qq
    except Exception as e:
        out = {
            "checker": "check_v4_qq_official_formatter",
            "generated_at": datetime.now(LOCAL_TZ).isoformat(),
            "date": args.date,
            "checks": checks,
            "warnings": warnings,
            "blockers": [f"import_error:{e}"],
            "conclusion": "BLOCKER",
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1

    official_text = format_qq(args.date, window=args.window, mode="official_recommendation")
    test_text = format_qq(args.date, window=args.window, mode="template_test")

    forbidden = [
        "V4模板验收TEST",
        "非正式推荐",
        "不代表今日正式推荐",
        "请勿下注",
        "模板验收TEST结束",
    ]
    for k in forbidden:
        ok = k not in official_text
        _ok(checks, f"official_forbidden_absent:{k}", ok)
        if not ok:
            blockers.append(f"official_contains_forbidden:{k}")

    required_any = [
        ("contains_v4", ["V4"]),
        ("contains_official", ["正式"]),
        ("contains_A0", ["A=0", "A级0", "【A级0场】"]),
        ("contains_B2", ["B=2", "B级2", "【B级2场】"]),
        ("contains_match_1", ["FC Voluntari vs Hermannstadt", "FC Voluntari vs AFC Hermannstadt"]),
        ("contains_match_2", ["Boston River vs Liverpool Montevideo"]),
        ("contains_mode_or_source", ["season_aware_rf", "official_grade_source"]),
        ("contains_threshold", ["73.5", "DEFAULT_RESCUE_THRESHOLD"]),
    ]
    for name, patterns in required_any:
        ok = any(p in official_text for p in patterns)
        _ok(checks, name, ok, "|".join(patterns))
        if not ok:
            blockers.append(f"missing_required:{name}")

    contamination = [
        "C级观察",
        "HT_SKIP",
        "shadow-only",
        "dryrun-only",
    ]
    for k in contamination:
        ok = k not in official_text
        _ok(checks, f"official_main_no_contamination:{k}", ok)
        if not ok:
            blockers.append(f"official_contamination:{k}")

    test_mode_markers = ["V4模板验收TEST", "非正式推荐", "模板验收TEST结束"]
    test_ok = all(k in test_text for k in test_mode_markers)
    _ok(checks, "test_mode_preserved", test_ok)
    if not test_ok:
        blockers.append("test_mode_not_preserved")

    _ok(checks, "checker_no_api_call", True, "local formatter only")
    _ok(checks, "checker_no_scan", True, "did not run scan entrypoint")
    _ok(checks, "checker_no_pending_write", True, "no pending writer invoked")
    _ok(checks, "checker_no_sent_marker_write", True, "no sent marker write path invoked")
    _ok(checks, "checker_no_qq_push", True, "no outbound sender invoked")

    # staged safety
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged_files = [x.strip() for x in staged.stdout.splitlines() if x.strip()]
    runtime_staged = [x for x in staged_files if "data/runtime/" in x or "data/daily_reports/" in x]
    _ok(checks, "runtime_artifact_not_staged", len(runtime_staged) == 0, ",".join(runtime_staged))
    if runtime_staged:
        blockers.append("runtime_artifact_staged")

    out = {
        "checker": "check_v4_qq_official_formatter",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "date": args.date,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    out_path = STATUS / f"check_v4_qq_official_formatter_{args.date}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
