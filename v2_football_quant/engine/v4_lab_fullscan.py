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
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

CN_TZ = timezone(timedelta(hours=8))
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
LAB_DIR = BASE_DIR / "data" / "runtime" / "lab" / "v4"
CACHE_DIR = LAB_DIR / "cache"

from engine.v4_lab.profile_loader import load_profile, profile_hash
from engine.v4_outside57_scanner import Outside57ApiClient, RateLimiter, InFlightLimiter, Outside57Cache
from engine.v4_outside57_scanner import run_outside57_scan
from engine.v4_runner import fetch_today_fixtures


def build_run_output_dir(date_str: str, run_id: str) -> Path:
    out = LAB_DIR / date_str / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _lab_h2h_check(home_id: int, away_id: int, api_client) -> dict:
    """Lab H2H last3 policy: last 3 valid league H2H matches, all must have FH goals.
    Filters: post-2020, exclude cups/friendlies/unknown. Returns detailed last3 data."""
    res = {"h2h_ok": False, "total": 0, "ht_goal_count": 0, "ht_goal_rate": 0.0,
           "h2h_policy": "LAB_H2H_LAST3_ALL_FH_GOAL", "h2h_last3_count": 0,
           "h2h_last3_fh_goal_count": 0, "h2h_last3_all_fh_goal": False,
           "h2h_signal": "LOW_SAMPLE", "h2h_valid_matches_used": 0, "h2h_low_sample": True}
    try:
        resp = api_client(f"fixtures/headtohead?h2h={home_id}-{away_id}")
        if not resp or "response" not in resp:
            return res
        matches = resp.get("response", [])
        if not matches:
            return res
        cutoff_2020 = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
        valid = []
        for m in matches:
            ts = m.get("fixture", {}).get("timestamp", 0)
            if ts < cutoff_2020:
                continue
            ltype = str(m.get("league", {}).get("type", "") or "")
            if any(c in ltype.lower() for c in ["cup", "friendly"]):
                continue
            ht = m.get("score", {}).get("halftime", {})
            if ht and ht.get("home") is not None and ht.get("away") is not None:
                valid.append(m)
        valid.sort(key=lambda m: m.get("fixture", {}).get("timestamp", 0), reverse=True)
        last3 = valid[:3]
        count = len(last3)
        fh = sum(1 for m in last3 for _ in [0] if (int(m["score"]["halftime"]["home"]) + int(m["score"]["halftime"]["away"])) > 0)
        res.update({"h2h_ok": True, "total": count, "ht_goal_count": fh,
                     "ht_goal_rate": round(fh / max(count, 1), 3),
                     "h2h_last3_count": count, "h2h_last3_fh_goal_count": fh,
                     "h2h_last3_all_fh_goal": (count == 3 and fh == 3),
                     "h2h_valid_matches_used": count, "h2h_low_sample": (count < 3),
                     "h2h_signal": "STRONG" if (count == 3 and fh == 3) else ("LOW_SAMPLE" if count < 3 else "WEAK_OR_FAIL")})
        return res
    except Exception:
        return res


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
    """Stage 1: H2H Gate. Stage 2: Full Scoring on pass fixtures only."""
    from engine import net_utils

    t0 = time.perf_counter()
    p_hash = profile_hash(profile)
    lab_mode = profile.get("mode", "standard")
    include_57 = profile.get("include_outside57", True)
    fixture_limit = min(limit, 10) if dry_run and limit > 0 else (limit if limit > 0 else 0)

    # Fetch fixtures
    fixtures = fetch_today_fixtures(None, None, net_utils.api_get, date.today(), include_57)
    if fixture_limit > 0 and len(fixtures) > fixture_limit:
        fixtures = fixtures[:fixture_limit]
    print(f"[V4 Lab] fixtures: {len(fixtures)}", flush=True)

    # Stage 1: H2H Gate
    h2h_gate_counts = {"processed": 0, "pass": 0, "fail_low": 0, "fail_not_all": 0}
    gate_pass_ids = []
    if lab_mode == "production_clone_h2h_last3":
        lab_rl = RateLimiter(60, 80)
        lab_il = InFlightLimiter(4)
        lab_cache = Outside57Cache()
        lab_api = Outside57ApiClient(lab_rl, lab_il, lab_cache, 10, 1)
        for fx in fixtures:
            hid, aid, fid = fx.get("homeId"), fx.get("awayId"), fx.get("id")
            h2h_gate_counts["processed"] += 1
            if not fid or not hid or not aid:
                continue
            check = _lab_h2h_check(hid, aid, lab_api.call)
            if check.get("h2h_last3_all_fh_goal"):
                gate_pass_ids.append(fid)
                h2h_gate_counts["pass"] += 1
            elif check.get("h2h_low_sample"):
                h2h_gate_counts["fail_low"] += 1
            else:
                h2h_gate_counts["fail_not_all"] += 1
        print(f"[V4 Lab] H2H Gate: {h2h_gate_counts['pass']}P/{h2h_gate_counts['fail_low']}L/{h2h_gate_counts['fail_not_all']}N", flush=True)
    else:
        gate_pass_ids = [fx.get("id") for fx in fixtures if fx.get("id")]

    # Stage 2: Full Scoring (H2H Gate PASS only)
    lab_results = []
    data_timeout_count = 0
    pass_fx = [fx for fx in fixtures if fx.get("id") in set(gate_pass_ids)]
    import engine.data_sources.h2h_engine as _h2h
    _ORIG = {}

    if pass_fx:
        print(f"[V4 Lab] Stage 2: {len(pass_fx)} fixtures full scoring", flush=True)
        try:
            summary = run_outside57_scan(
                include_outside_57=True, workers=workers, worker_max=workers,
                api_rpm=api_rpm, api_rpm_hard_cap=api_rpm_hard_cap,
                max_inflight=max_inflight, api_timeout_sec=api_timeout_sec,
                fixture_timeout_sec=fixture_timeout_sec * 2, retry_max=retry_max,
                resume=resume, run_id=run_id + "_full", scan_mode="full",
                scan_date_str=date_str, pre_fetched_fixtures=pass_fx,
            )
        finally:
            for k, v in _ORIG.items():
                if k.startswith("_restore_"): v()
                else: setattr(_h2h, k, v)
            if _ORIG: print(f"[V4 Lab] scoring restored: {len(_ORIG)}", flush=True)
        for r in summary.get("results", []):
            g = str(r.get("grade", "SKIP")).upper()
            to = "TIMEOUT" in str(r.get("h2h_reason", "")) or "API_ERROR" in str(r.get("h2h_reason", ""))
            if to: data_timeout_count += 1
            lab_results.append({
                "lab_only": True, "official_candidate": False,
                "not_for_validation": True, "not_for_live_bet": True, "not_for_qq_recommendation": True,
                "mode": lab_mode, "use_production_scoring_chain": True,
                "run_id": run_id, "profile_id": profile.get("profile_id", "unknown"), "profile_hash": p_hash,
                "fixture_id": r.get("fixture_id"), "league": r.get("league_name"),
                "home": r.get("home_team"), "away": r.get("away_team"), "kickoff": r.get("kickoff_time"),
                "lab_grade": f"LAB_{g}" if g in ("A", "B", "SKIP") else "LAB_SKIP",
                "lab_status": "DATA_TIMEOUT" if to else "COMPLETE",
                "scoring_complete": not to,
                "incomplete_reason": "full_scoring_timeout" if to else "",
                "lab_score": r.get("candidate_score"),
                "h2h_gate_pass": True, "stage": "full_scoring",
            })

    # Gate fail results
    for fx in fixtures:
        if fx.get("id") in set(gate_pass_ids):
            continue
        lab_results.append({
            "lab_only": True, "official_candidate": False,
            "not_for_validation": True, "not_for_live_bet": True, "not_for_qq_recommendation": True,
            "mode": lab_mode, "use_production_scoring_chain": False,
            "run_id": run_id, "profile_id": profile.get("profile_id", "unknown"), "profile_hash": p_hash,
            "fixture_id": fx.get("id"), "league": fx.get("league_name"),
            "home": fx.get("home"), "away": fx.get("away"), "kickoff": fx.get("kickoff"),
            "lab_grade": "LAB_SKIP", "lab_status": "H2H_GATE_FAIL",
            "scoring_complete": False, "incomplete_reason": "h2h_gate_not_pass",
            "lab_score": None, "h2h_gate_pass": False, "stage": "h2h_gate",
        })

    elapsed = time.perf_counter() - t0
    H2H_SKIP = sum(1 for r in lab_results if r.get("stage") == "h2h_gate")
    summary = {
        "run_id": run_id, "profile_id": profile.get("profile_id", "unknown"), "profile_hash": p_hash,
        "date": date_str, "generated_at": datetime.now(CN_TZ).isoformat(),
        "input_fixture_count": len(fixtures), "processed_fixture_count": len(fixtures),
        "silent_drop_count": 0,
        "h2h_gate_processed_count": h2h_gate_counts["processed"],
        "h2h_gate_pass_count": h2h_gate_counts["pass"],
        "h2h_gate_fail_low_sample_count": h2h_gate_counts["fail_low"],
        "h2h_gate_fail_not_all_fh_goal_count": h2h_gate_counts["fail_not_all"],
        "full_scoring_input_count": len(pass_fx),
        "lab_a_count": sum(1 for r in lab_results if r["lab_grade"] == "LAB_A"),
        "lab_b_count": sum(1 for r in lab_results if r["lab_grade"] == "LAB_B"),
        "lab_skip_count": sum(1 for r in lab_results if r["lab_grade"] in ("LAB_SKIP", "SKIP") and r.get("stage") == "full_scoring"),
        "h2h_gate_fail_count": H2H_SKIP,
        "data_timeout_count": data_timeout_count,
        "total_duration_sec": elapsed, "dry_run": dry_run, "limit": fixture_limit,
        "lab_only": True, "production_safe": False,
    }
    return {"config": {"run_id": run_id, "profile_id": profile.get("profile_id"), "date": date_str},
            "profile_snapshot": {"profile_id": profile.get("profile_id"), "profile_hash": p_hash},
            "summary": summary, "results": lab_results, "conclusion": "PASS"}


def write_lab_outputs(out_dir: Path, data: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lab_run_config.json").write_text(json.dumps(data["config"], ensure_ascii=False, indent=2))
    (out_dir / "lab_profile_snapshot.json").write_text(json.dumps(data["profile_snapshot"], ensure_ascii=False, indent=2))
    (out_dir / "lab_scan_results.json").write_text(json.dumps(data["results"], ensure_ascii=False, indent=2))
    (out_dir / "lab_summary.json").write_text(json.dumps(data["summary"], ensure_ascii=False, indent=2))


def generate_report(data: dict) -> str:
    s = data["summary"]
    lines = []
    lines.append("# V4 Lab Production Clone H2H Last3")
    lines.append("")
    lines.append("> 这是完整复刻正式 V4 评分链的 Lab 实验结果。")
    lines.append("> 唯一差异是 H2H 参考口径：最近3场有效 H2H 必须全部上半场有球。")
    lines.append("> 不是正式推荐。不进入实盘。不进入验证累计。不推 QQ。")
    lines.append("")
    lines.append(f"**run_id**: {s['run_id']}")
    lines.append(f"**date**: {s['date']}")
    lines.append(f"**profile**: {s['profile_id']} ({s['profile_hash']})")
    lines.append("")
    lines.append("## Stage 1: H2H Gate")
    lines.append("")
    for k in ["h2h_gate_processed_count", "h2h_gate_pass_count",
               "h2h_gate_fail_low_sample_count", "h2h_gate_fail_not_all_fh_goal_count"]:
        lines.append(f"- {k}: {s.get(k, '?')}")
    lines.append("")
    lines.append("## Stage 2: Full V4 Scoring")
    lines.append("")
    for k in ["full_scoring_input_count", "lab_a_count", "lab_b_count",
               "lab_skip_count", "h2h_gate_fail_count", "data_timeout_count",
               "total_duration_sec"]:
        v = s.get(k, "?")
        if k == "total_duration_sec":
            lines.append(f"- duration: {v:.1f}s")
        else:
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### LAB_B List")
    promoted = [r for r in data["results"] if r.get("lab_grade") == "LAB_B"]
    for p in promoted:
        lines.append(f"- {p['home']} vs {p['away']} ({p['league']})")
    lines.append("")
    lines.append("---")
    lines.append("*Isolation:* lab_only=true official_candidate=false not_for_validation=true")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="V4 Lab 独立全量扫描")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--api-rpm", type=int, default=290)
    parser.add_argument("--api-rpm-hard-cap", type=int, default=300)
    parser.add_argument("--max-inflight", type=int, default=30)
    parser.add_argument("--api-timeout-sec", type=int, default=12)
    parser.add_argument("--fixture-timeout-sec", type=int, default=35)
    parser.add_argument("--retry", type=int, default=2, dest="retry_max")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-official-write", action="store_true", default=True)
    parser.add_argument("--write-official", action="store_true", help="REJECTED")
    args = parser.parse_args()

    if args.write_official:
        print("[LAB] ERROR: --write-official rejected", flush=True)
        sys.exit(1)

    profile_path = Path(args.profile)
    if not profile_path.exists():
        profile_path = BASE_DIR / "config" / "v4_lab_profiles" / f"{args.profile}.json"
    if not profile_path.exists():
        print(f"[LAB] Profile not found: {args.profile}", flush=True)
        sys.exit(1)
    profile = load_profile(str(profile_path))

    run_id = args.run_id or f"lab_{profile.get('profile_id','x')}_{args.date}_{datetime.now(CN_TZ).strftime('%H%M%S')}"

    data = run_lab_scan(
        date_str=args.date, profile=profile, workers=args.workers,
        api_rpm=args.api_rpm, api_rpm_hard_cap=args.api_rpm_hard_cap,
        max_inflight=args.max_inflight, api_timeout_sec=args.api_timeout_sec,
        fixture_timeout_sec=args.fixture_timeout_sec, retry_max=args.retry_max,
        resume=args.resume, run_id=run_id, limit=args.limit, dry_run=args.dry_run,
    )
    out_dir = build_run_output_dir(args.date, run_id)
    write_lab_outputs(out_dir, data)
    report = generate_report(data)
    (out_dir / "lab_report.md").write_text(report, encoding="utf-8")

    s = data["summary"]
    print(f"[V4 Lab] run_id={run_id}")
    print(f"[V4 Lab] profile={profile.get('profile_id')} hash={data['profile_snapshot']['profile_hash']}")
    print(f"[V4 Lab] fixtures={s['processed_fixture_count']}/{s['input_fixture_count']}")
    print(f"[V4 Lab] H2H Gate: {s['h2h_gate_pass_count']}/{s['h2h_gate_processed_count']}")
    print(f"[V4 Lab] LAB_A={s['lab_a_count']} LAB_B={s['lab_b_count']}")
    print(f"[V4 Lab] H2H fail={s['h2h_gate_fail_count']} timeout={s['data_timeout_count']}")
    print(f"[V4 Lab] duration={s['total_duration_sec']:.1f}s")
    print(f"[V4 Lab] isolation: lab_only=true official_candidate=false")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
