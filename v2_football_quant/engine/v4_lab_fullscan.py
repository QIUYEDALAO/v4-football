#!/usr/bin/env python3
"""
v4_lab_fullscan.py — V4 Lab 独立全量扫描系统
============================================
手动运行，独立策略，独立输出。
默认完全隔离，不写任何 official 路径。

用法:
  python3 engine/v4_lab_fullscan.py --date 20260527 --profile config/v4_lab_profiles/default.json
  python3 engine/v4_lab_fullscan.py --date 20260527 --profile default --limit 10 --dry-run
  python3 engine/v4_lab_fullscan.py --resume --run-id lab_default_20260527_001
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

CN_TZ = timezone(timedelta(hours=8))
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
LAB_DIR = BASE_DIR / "data" / "runtime" / "lab" / "v4"
CACHE_DIR = LAB_DIR / "cache"

from engine.v4_lab.profile_loader import load_profile, profile_hash


def build_run_output_dir(date_str: str, run_id: str) -> Path:
    out = LAB_DIR / date_str / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_lab_scan(
    date_str: str,
    profile: dict,
    workers: int = 8,
    api_rpm: int = 290,
    api_rpm_hard_cap: int = 300,
    max_inflight: int = 30,
    api_timeout_sec: int = 12,
    fixture_timeout_sec: int = 35,
    retry_max: int = 2,
    resume: bool = False,
    run_id: str = "",
    limit: int = 0,
    dry_run: bool = False,
) -> dict:
    """Run lab scan using the parallel scanner engine with lab-specific profile."""
    from engine.v4_outside57_scanner import run_outside57_scan

    t0 = time.perf_counter()
    p_hash = profile_hash(profile)
    include_57 = profile.get("include_outside57", True)

    if dry_run:
        fixture_limit = min(limit, 10) if limit > 0 else 5
    else:
        fixture_limit = limit

    summary = run_outside57_scan(
        include_outside_57=include_57,
        workers=workers,
        worker_max=workers,
        api_rpm=api_rpm,
        api_rpm_hard_cap=api_rpm_hard_cap,
        max_inflight=max_inflight,
        api_timeout_sec=api_timeout_sec,
        fixture_timeout_sec=fixture_timeout_sec,
        retry_max=retry_max,
        resume=resume,
        run_id=run_id,
        scan_mode="full",
        scan_date_str=date_str,
    )

    results = summary.get("results", [])
    if fixture_limit > 0:
        results = results[:fixture_limit]

    fc = summary.get("full_coverage", {})
    elapsed = time.perf_counter() - t0

    # Build lab-grade results
    lab_results = []
    for r in results:
        grade = str(r.get("grade", "SKIP")).upper()
        lab_grade = f"LAB_{grade}"
        lab_results.append({
            "lab_only": True,
            "official_candidate": False,
            "not_for_validation": True,
            "not_for_live_bet": True,
            "not_for_qq_recommendation": True,
            "run_id": run_id,
            "profile_id": profile.get("profile_id", "unknown"),
            "profile_hash": p_hash,
            "fixture_id": r.get("fixture_id"),
            "league": r.get("league_name"),
            "home": r.get("home_team"),
            "away": r.get("away_team"),
            "kickoff": r.get("kickoff_time"),
            "lab_grade": lab_grade,
            "lab_score": r.get("candidate_score"),
            "h2h_valid": r.get("h2h_valid"),
            "h2h_reason": str(r.get("h2h_reason", "")),
            "outside57": r.get("outside57", False),
            "recent_form_low_sample": r.get("recent_form_low_sample", False),
            "source_trace": "lab_fullscan_via_outside57_scanner",
            "warnings": [],
        })

    lab_summary = {
        "run_id": run_id,
        "profile_id": profile.get("profile_id", "unknown"),
        "profile_hash": p_hash,
        "date": date_str,
        "generated_at": datetime.now(CN_TZ).isoformat(),
        "input_fixture_count": fc.get("input_fixture_count", 0),
        "processed_fixture_count": len(results),
        "silent_drop_count": fc.get("silent_drop_count", 0),
        "lab_a_count": sum(1 for r in lab_results if r["lab_grade"] == "LAB_A"),
        "lab_b_count": sum(1 for r in lab_results if r["lab_grade"] == "LAB_B"),
        "lab_skip_count": sum(1 for r in lab_results if r["lab_grade"] in ("LAB_SKIP", "SKIP")),
        "done_count": fc.get("done_count", 0),
        "timeout_count": fc.get("timeout_count", 0),
        "failed_count": fc.get("failed_count", 0),
        "total_duration_sec": elapsed,
        "rpm_peak_60s": summary.get("rate_limiter", {}).get("rpm_peak_60s", 0),
        "peak_inflight": summary.get("inflight_limiter", {}).get("peak_inflight_requests", 0),
        "cache_hits": summary.get("cache", {}).get("cache_hits", 0),
        "cache_misses": summary.get("cache", {}).get("cache_misses", 0),
        "dry_run": dry_run,
        "limit": fixture_limit,
        "lab_only": True,
        "production_safe": False,
    }

    return {
        "config": {
            "run_id": run_id,
            "profile_id": profile.get("profile_id"),
            "workers": workers,
            "api_rpm": api_rpm,
            "api_rpm_hard_cap": api_rpm_hard_cap,
            "max_inflight": max_inflight,
            "date": date_str,
        },
        "profile_snapshot": {
            "profile_id": profile.get("profile_id"),
            "profile_name": profile.get("profile_name"),
            "profile_hash": p_hash,
        },
        "summary": lab_summary,
        "results": lab_results,
        "conclusion": "PASS" if lab_summary["silent_drop_count"] == 0 else "WARN",
    }


def write_lab_outputs(out_dir: Path, data: dict, dry_run: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lab_run_config.json").write_text(
        json.dumps(data["config"], ensure_ascii=False, indent=2))
    (out_dir / "lab_profile_snapshot.json").write_text(
        json.dumps(data["profile_snapshot"], ensure_ascii=False, indent=2))
    (out_dir / "lab_scan_results.json").write_text(
        json.dumps(data["results"], ensure_ascii=False, indent=2))
    (out_dir / "lab_summary.json").write_text(
        json.dumps(data["summary"], ensure_ascii=False, indent=2))


def generate_report(data: dict) -> str:
    s = data["summary"]
    top_a = [r for r in data["results"] if r["lab_grade"] == "LAB_A"][:3]
    top_b = [r for r in data["results"] if r["lab_grade"] == "LAB_B"][:5]
    lines = []
    lines.append("# V4 Lab 实验扫描报告")
    lines.append("")
    lines.append("> ⚠️ **这是 V4 Lab 实验扫描结果。**")
    lines.append("> 不是正式推荐。")
    lines.append("> 不进入实盘。")
    lines.append("> 不进入验证累计。")
    lines.append("> 不推 QQ。")
    lines.append("")
    lines.append(f"**run_id**: {s['run_id']}")
    lines.append(f"**date**: {s['date']}")
    lines.append(f"**profile**: {s['profile_id']} ({s['profile_hash']})")
    lines.append(f"**dry_run**: {s['dry_run']}")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| input_fixture_count | {s['input_fixture_count']} |")
    lines.append(f"| processed_fixture_count | {s['processed_fixture_count']} |")
    lines.append(f"| silent_drop_count | {s['silent_drop_count']} |")
    lines.append(f"| LAB_A | {s['lab_a_count']} |")
    lines.append(f"| LAB_B | {s['lab_b_count']} |")
    lines.append(f"| LAB_SKIP | {s['lab_skip_count']} |")
    lines.append(f"| timeout_count | {s['timeout_count']} |")
    lines.append(f"| failed_count | {s['failed_count']} |")
    lines.append(f"| duration | {s['total_duration_sec']:.1f}s |")
    lines.append(f"| rpm_peak_60s | {s['rpm_peak_60s']} |")
    lines.append(f"| peak_inflight | {s['peak_inflight']} |")
    lines.append(f"| cache_hits | {s['cache_hits']} |")
    lines.append("")
    if top_a:
        lines.append("### Top LAB_A")
        for r in top_a:
            lines.append(f"- {r['lab_grade']}: {r['home']} vs {r['away']} ({r['league']})")
    if top_b:
        lines.append("### Top LAB_B")
        for r in top_b:
            lines.append(f"- {r['lab_grade']}: {r['home']} vs {r['away']} ({r['league']})")
    lines.append("")
    lines.append("---")
    lines.append("*Isolation confirmation:*")
    lines.append("- lab_only=true ✅")
    lines.append("- official_candidate=false ✅")
    lines.append("- not_for_validation=true ✅")
    lines.append("- not_for_live_bet=true ✅")
    lines.append("- not_for_qq_recommendation=true ✅")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="V4 Lab 独立全量扫描")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--profile", required=True, help="Profile path or profile_id (e.g. default)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--api-rpm", type=int, default=290)
    parser.add_argument("--api-rpm-hard-cap", type=int, default=300)
    parser.add_argument("--max-inflight", type=int, default=30)
    parser.add_argument("--api-timeout-sec", type=int, default=12)
    parser.add_argument("--fixture-timeout-sec", type=int, default=35)
    parser.add_argument("--retry", type=int, default=2, dest="retry_max")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limit fixtures (0=unlimited)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-official-write", action="store_true", default=True)
    parser.add_argument("--write-official", action="store_true", help="REJECTED — lab never writes official")

    args = parser.parse_args()

    # Hard guard: --write-official is always rejected
    if args.write_official:
        print("[LAB] ERROR: --write-official is not allowed. Lab never writes official output.", flush=True)
        sys.exit(1)

    # Resolve profile
    profile_path = Path(args.profile)
    if not profile_path.exists():
        profile_path = BASE_DIR / "config" / "v4_lab_profiles" / f"{args.profile}.json"
    if not profile_path.exists():
        print(f"[LAB] Profile not found: {args.profile}", flush=True)
        sys.exit(1)

    profile = load_profile(str(profile_path))

    run_id = args.run_id or f"lab_{profile.get('profile_id','unknown')}_{args.date}_{datetime.now(CN_TZ).strftime('%H%M%S')}"

    data = run_lab_scan(
        date_str=args.date,
        profile=profile,
        workers=args.workers,
        api_rpm=args.api_rpm,
        api_rpm_hard_cap=args.api_rpm_hard_cap,
        max_inflight=args.max_inflight,
        api_timeout_sec=args.api_timeout_sec,
        fixture_timeout_sec=args.fixture_timeout_sec,
        retry_max=args.retry_max,
        resume=args.resume,
        run_id=run_id,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    out_dir = build_run_output_dir(args.date, run_id)
    write_lab_outputs(out_dir, data, args.dry_run)

    # Write report
    report = generate_report(data)
    (out_dir / "lab_report.md").write_text(report, encoding="utf-8")

    s = data["summary"]
    print(f"\n[V4 Lab] run_id={run_id}")
    print(f"[V4 Lab] profile={profile.get('profile_id')} hash={data['profile_snapshot']['profile_hash']}")
    print(f"[V4 Lab] fixtures={s['processed_fixture_count']}/{s['input_fixture_count']} drop={s['silent_drop_count']}")
    print(f"[V4 Lab] LAB_A={s['lab_a_count']} LAB_B={s['lab_b_count']} LAB_SKIP={s['lab_skip_count']}")
    print(f"[V4 Lab] duration={s['total_duration_sec']:.1f}s rpm_peak={s['rpm_peak_60s']}")
    print(f"[V4 Lab] output={out_dir}")
    print(f"[V4 Lab] report={out_dir / 'lab_report.md'}")
    print(f"[V4 Lab] conclusion={data['conclusion']}")
    print("[V4 Lab] isolation: lab_only=true official_candidate=false not_for_validation=true ✅")

    return 0 if data["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
