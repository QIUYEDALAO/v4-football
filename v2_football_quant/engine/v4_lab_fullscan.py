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


def _lab_h2h_check(home_id: int, away_id: int, api_client) -> dict:
    """Lab H2H last3 policy: last 3 valid league H2H matches, all must have FH goals.

    Filters:
    - Post-2020 matches only
    - Exclude cups, friendlies, unknown competitions
    - Take last 3 by timestamp
    - Require all 3 to have FH goals
    Returns dict with full last3 details.
    """
    result = {
        "h2h_ok": False, "total": 0, "ht_goal_count": 0, "ht_goal_rate": 0.0,
        "h2h_policy": "LAB_H2H_LAST3_ALL_FH_GOAL",
        "h2h_last3_count": 0, "h2h_last3_fh_goal_count": 0, "h2h_last3_all_fh_goal": False,
        "h2h_signal": "LOW_SAMPLE", "h2h_valid_matches_used": 0, "h2h_low_sample": True,
    }
    try:
        resp = api_client(f"fixtures/headtohead?h2h={home_id}-{away_id}")
        if not resp or "response" not in resp:
            return result
        matches = resp.get("response", [])
        if not matches:
            return result

        cutoff_2020 = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
        excluded_categories = {"Cup", "Friendly", "Super Cup", "Play-offs"}

        valid_matches = []
        excluded = []
        for m in matches:
            ts = m.get("fixture", {}).get("timestamp", 0)
            if ts < cutoff_2020:
                excluded.append("pre2020")
                continue
            league = m.get("league", {})
            league_name = str(league.get("name", "") or "")
            league_type = str(league.get("type", "") or "")
            # Exclude non-league competitions
            if any(cat.lower() in league_type.lower() for cat in ["cup", "friendly"]):
                excluded.append(f"excluded_type:{league_type}")
                continue
            if not league_name or league_name == "-":
                excluded.append("unknown_competition")
                continue
            # Check HT data exists
            score = m.get("score", {})
            ht = score.get("halftime", {})
            if ht and ht.get("home") is not None and ht.get("away") is not None:
                valid_matches.append(m)
            else:
                excluded.append("no_ht_data")

        # Sort by timestamp desc, take last 3 valid
        valid_matches.sort(key=lambda m: m.get("fixture", {}).get("timestamp", 0), reverse=True)
        last3 = valid_matches[:3]
        count = len(last3)
        fh_goals = 0
        for m in last3:
            score = m.get("score", {})
            ht = score.get("halftime", {})
            try:
                if int(ht["home"]) + int(ht["away"]) > 0:
                    fh_goals += 1
            except (ValueError, TypeError):
                pass

        result["h2h_ok"] = True
        result["total"] = count
        result["ht_goal_count"] = fh_goals
        result["ht_goal_rate"] = round(fh_goals / max(count, 1), 3)
        result["h2h_last3_count"] = count
        result["h2h_last3_fh_goal_count"] = fh_goals
        result["h2h_last3_all_fh_goal"] = (count == 3 and fh_goals == 3)
        result["h2h_valid_matches_used"] = count
        result["h2h_low_sample"] = (count < 3)
        if count < 3:
            result["h2h_signal"] = "LOW_SAMPLE"
        elif fh_goals == 3:
            result["h2h_signal"] = "STRONG"
        else:
            result["h2h_signal"] = "WEAK_OR_FAIL"
        return result
    except Exception:
        return result


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

    # ── Scoring parameter overrides: monkey-patch production constants ──
    # Save originals, apply profile overrides, restore after scan
    import engine.data_sources.h2h_engine as _h2h
    _ORIGINALS = {}
    scoring_overrides = profile.get("scoring_overrides", {})
    if scoring_overrides:
        for key, val in scoring_overrides.items():
            if hasattr(_h2h, key):
                _ORIGINALS[key] = getattr(_h2h, key)
                setattr(_h2h, key, val)
        print(f"[V4 Lab] scoring overrides applied: {len(scoring_overrides)} params", flush=True)
        for k, v in scoring_overrides.items():
            print(f"  {k}: {v}", flush=True)

    # Also override recent form sample size in the function default if profile specifies
    # ── Pyramid bypass: treat outside_57 H2H as same_league_h2h ──
    # This lets the production scoring pipeline see outside_57 H2H data
    if profile.get("h2h_promotion", {}).get("enabled"):
        _ORIGINALS["_select_official_pool"] = _h2h._select_official_pool
        _orig_select = _h2h._select_official_pool
        def _lab_select(classified):
            for c in classified:
                if c.get("category") in ("pyramid_unknown", "excluded_h2h", "pre2020"):
                    c["category"] = "same_league_h2h"
            return _orig_select(classified)
        _h2h._select_official_pool = _lab_select
        # Also patch scanner module's imported reference
        import engine.v4_outside57_scanner as _scanner
        _scanner._select_official_pool = _lab_select
        _ORIGINALS["_restore_scanner"] = lambda: setattr(_scanner, '_select_official_pool', _ORIGINALS['_select_official_pool'])
        print(f"[V4 Lab] pyramid filter bypassed for H2H data", flush=True)

    # ── Scoring parameter overrides ──
    scoring_overrides = profile.get("scoring_overrides", {})
    if scoring_overrides:
        for key, val in scoring_overrides.items():
            if hasattr(_h2h, key):
                _ORIGINALS[key] = getattr(_h2h, key)
                setattr(_h2h, key, val)
        print(f"[V4 Lab] scoring overrides applied: {len(scoring_overrides)} params", flush=True)

    try:
        include_57 = profile.get("include_outside57", True)

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
    finally:
        # Restore original scoring constants and patches
        for key, orig_val in _ORIGINALS.items():
            if key.startswith("_restore_"):
                orig_val()  # Call restore lambda
            else:
                setattr(_h2h, key, orig_val)
        if _ORIGINALS:
            print(f"[V4 Lab] scoring constants restored: {len(_ORIGINALS)} params", flush=True)

    results = summary.get("results", [])
    if fixture_limit > 0:
        results = results[:fixture_limit]

    fc = summary.get("full_coverage", {})
    elapsed = time.perf_counter() - t0

    # ── Determine Lab mode ──
    lab_mode = profile.get("mode", "standard")
    is_prod_clone = (lab_mode == "production_clone_h2h_last3")

    # ── Lab H2H last3 check (independent of production scoring) ──
    from engine.v4_outside57_scanner import Outside57ApiClient, RateLimiter, InFlightLimiter, Outside57Cache
    lab_rl = RateLimiter(rpm_target=60, rpm_hard_cap=80)
    lab_il = InFlightLimiter(max_inflight=4)
    lab_cache = Outside57Cache()
    lab_api = Outside57ApiClient(lab_rl, lab_il, lab_cache, timeout_sec=10, retry_max=1)

    promoted_count = 0
    h2h_check_count = 0
    data_timeout_count = 0
    score_incomplete_count = 0

    lab_results = []
    for r in results:
        grade = str(r.get("grade", "SKIP")).upper()
        lab_grade = f"LAB_{grade}" if grade in ("A", "B", "SKIP") else "LAB_SKIP"
        lab_status = "COMPLETE"
        scoring_complete = True
        incomplete_reason = ""

        # Check production scoring completeness
        prod_grade = r.get("grade", "SKIP")
        h2h_valid = r.get("h2h_valid", False)
        h2h_reason = str(r.get("h2h_reason", "") or "")
        is_timeout = "TIMEOUT" in h2h_reason or "API_ERROR" in h2h_reason or r.get("status") in ("API_ERROR", "TIMEOUT")

        if is_timeout:
            scoring_complete = False
            lab_status = "DATA_TIMEOUT"
            incomplete_reason = "production_scoring_timeout"
            lab_grade = "LAB_SKIP"  # Placeholder for tracking; not counted as SKIP
            data_timeout_count += 1
        elif not prod_grade or prod_grade in ("", "UNKNOWN"):
            scoring_complete = False
            lab_status = "SCORE_INCOMPLETE"
            incomplete_reason = "production_scoring_incomplete"
            score_incomplete_count += 1

        # Lab H2H last3 check for production_clone mode
        h2h_check = {
            "h2h_ok": False, "total": 0, "ht_goal_count": 0, "ht_goal_rate": 0.0,
            "h2h_policy": "", "h2h_last3_count": 0, "h2h_last3_fh_goal_count": 0,
            "h2h_last3_all_fh_goal": False, "h2h_signal": "UNKNOWN",
            "h2h_low_sample": True,
        }
        promoted = False
        _lab_cand_score = None
        _lab_rec_note = ""

        if r.get("fixture_id"):
            fixture_id = r.get("fixture_id")
            home_id = r.get("home_id") or r.get("homeId")
            away_id = r.get("away_id") or r.get("awayId")
            if not home_id or not away_id:
                try:
                    fx_resp = lab_api.call(f"fixtures?id={fixture_id}")
                    if fx_resp and "response" in fx_resp and fx_resp["response"]:
                        teams = fx_resp["response"][0].get("teams", {})
                        home_id = teams.get("home", {}).get("id")
                        away_id = teams.get("away", {}).get("id")
                except Exception:
                    pass
            if home_id and away_id:
                h2h_check_count += 1
                h2h_check = _lab_h2h_check(home_id, away_id, lab_api.call)

        # Apply H2H last3 policy (only if scoring completed)
        if scoring_complete and h2h_check.get("h2h_last3_all_fh_goal"):
            sample_bonus = min(3.0 / 3.0, 1.5)
            _lab_cand_score = round(1.0 * 100 * sample_bonus, 1)
            _lab_rec_note = "H2H近3场全部上半场有球，FLAG"
            lab_grade = "LAB_B"
            promoted = True
            promoted_count += 1

        # Build result entry with all required fields
        lab_entry = {
            "lab_only": True,
            "official_candidate": False,
            "not_for_validation": True,
            "not_for_live_bet": True,
            "not_for_qq_recommendation": True,
            "mode": lab_mode,
            "use_production_scoring_chain": True,
            "run_id": run_id,
            "profile_id": profile.get("profile_id", "unknown"),
            "profile_hash": p_hash,
            "fixture_id": r.get("fixture_id"),
            "league": r.get("league_name"),
            "home": r.get("home_team"),
            "away": r.get("away_team"),
            "kickoff": r.get("kickoff_time"),
            "lab_grade": lab_grade,
            "lab_status": lab_status,
            "scoring_complete": scoring_complete,
            "incomplete_reason": incomplete_reason,
            "lab_score": _lab_cand_score if promoted else r.get("candidate_score"),
            "lab_rec_note": _lab_rec_note,
            "h2h_policy": h2h_check.get("h2h_policy", ""),
            "h2h_last3_count": h2h_check.get("h2h_last3_count", 0),
            "h2h_last3_fh_goal_count": h2h_check.get("h2h_last3_fh_goal_count", 0),
            "h2h_last3_all_fh_goal": h2h_check.get("h2h_last3_all_fh_goal", False),
            "h2h_signal": h2h_check.get("h2h_signal", "UNKNOWN"),
            "h2h_valid_matches_used": h2h_check.get("h2h_valid_matches_used", 0),
            "h2h_low_sample": h2h_check.get("h2h_low_sample", True),
            "events_complete": scoring_complete,
            "time_bins_complete": scoring_complete,
            "late_fh_pressure_complete": scoring_complete,
            "ht_score_complete": scoring_complete,
            "lab_promoted": promoted,
            "outside57": r.get("outside57", False),
            "recent_form_low_sample": r.get("recent_form_low_sample", False),
            "source_trace": "lab_prod_clone_h2h_last3",
            "warnings": [] if is_timeout else [],
        }
        lab_results.append(lab_entry)

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
        "data_timeout_count": data_timeout_count,
        "score_incomplete_count": score_incomplete_count,
        "lab_h2h_promoted": promoted_count,
        "lab_h2h_checked": h2h_check_count,
        "h2h_last3_all_fh_goal_count": sum(1 for r in lab_results if r.get("h2h_last3_all_fh_goal")),
        "h2h_low_sample_count": sum(1 for r in lab_results if r.get("h2h_low_sample")),
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
        "config": {"run_id": run_id, "profile_id": profile.get("profile_id"), "workers": workers,
                    "api_rpm": api_rpm, "api_rpm_hard_cap": api_rpm_hard_cap, "max_inflight": max_inflight, "date": date_str},
        "profile_snapshot": {"profile_id": profile.get("profile_id"), "profile_name": profile.get("profile_name"), "profile_hash": p_hash},
        "summary": lab_summary,
        "results": lab_results,
        "conclusion": "PASS" if lab_summary["silent_drop_count"] == 0 else "WARN",
    }


def write_lab_outputs(out_dir: Path, data: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lab_run_config.json").write_text(json.dumps(data["config"], ensure_ascii=False, indent=2))
    (out_dir / "lab_profile_snapshot.json").write_text(json.dumps(data["profile_snapshot"], ensure_ascii=False, indent=2))
    (out_dir / "lab_scan_results.json").write_text(json.dumps(data["results"], ensure_ascii=False, indent=2))
    (out_dir / "lab_summary.json").write_text(json.dumps(data["summary"], ensure_ascii=False, indent=2))


def generate_report(data: dict) -> str:
    s = data["summary"]
    top_b = [r for r in data["results"] if r["lab_grade"] == "LAB_B"][:10]
    promoted = [r for r in data["results"] if r.get("lab_promoted")][:10]
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
    lines.append(f"**mode**: {s.get('profile_id', 'standard')}")
    lines.append(f"**dry_run**: {s['dry_run']}")
    lines.append("")
    lines.append("> 这是完整复刻正式 V4 评分链的 Lab 实验结果。")
    lines.append("> 唯一差异是 H2H 参考口径：最近3场有效 H2H 必须全部上半场有球。")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    for k in ["input_fixture_count", "processed_fixture_count", "silent_drop_count",
               "lab_a_count", "lab_b_count", "lab_skip_count",
               "data_timeout_count", "score_incomplete_count",
               "h2h_last3_all_fh_goal_count", "h2h_low_sample_count",
               "lab_h2h_promoted", "lab_h2h_checked",
               "done_count", "timeout_count", "failed_count",
               "total_duration_sec", "rpm_peak_60s", "peak_inflight", "cache_hits"]:
        v = s.get(k, "?")
        if k == "total_duration_sec":
            lines.append(f"| duration | {v:.1f}s |")
        else:
            lines.append(f"| {k} | {v} |")
    lines.append("")
    if top_b:
        lines.append("### LAB_B Candidates")
        for r in top_b:
            flag = "✅ H2H" if r.get("lab_promoted") else ""
            score = r.get("lab_score", "")
            note = r.get("lab_rec_note", "")
            lines.append(f"- [{score}] {r['home']} vs {r['away']} ({r['league']}) {note} {flag}")
    if promoted:
        lines.append("")
        lines.append("### H2H Promotion Details")
        for r in promoted:
            lines.append(f"- {r['home']} vs {r['away']} ({r['league']}): {r['lab_h2h_ht_goal_count']}/{r['lab_h2h_total']} HT goals, score={r.get('lab_score','?')}")
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
    parser.add_argument("--write-official", action="store_true", help="REJECTED - lab never writes official")
    args = parser.parse_args()

    if args.write_official:
        print("[LAB] ERROR: --write-official is not allowed. Lab never writes official output.", flush=True)
        sys.exit(1)

    profile_path = Path(args.profile)
    if not profile_path.exists():
        profile_path = BASE_DIR / "config" / "v4_lab_profiles" / f"{args.profile}.json"
    if not profile_path.exists():
        print(f"[LAB] Profile not found: {args.profile}", flush=True)
        sys.exit(1)
    profile = load_profile(str(profile_path))

    run_id = args.run_id or f"lab_{profile.get('profile_id','unknown')}_{args.date}_{datetime.now(CN_TZ).strftime('%H%M%S')}"

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
    print(f"\n[V4 Lab] run_id={run_id}")
    print(f"[V4 Lab] profile={profile.get('profile_id')} hash={data['profile_snapshot']['profile_hash']}")
    print(f"[V4 Lab] fixtures={s['processed_fixture_count']}/{s['input_fixture_count']} drop={s['silent_drop_count']}")
    print(f"[V4 Lab] LAB_A={s['lab_a_count']} LAB_B={s['lab_b_count']} LAB_SKIP={s['lab_skip_count']}")
    print(f"[V4 Lab] H2H checked={s['lab_h2h_checked']} promoted={s['lab_h2h_promoted']}")
    print(f"[V4 Lab] data_timeout={s['data_timeout_count']} score_incomplete={s['score_incomplete_count']}")
    print(f"[V4 Lab] h2h_last3_all_fh_goal={s['h2h_last3_all_fh_goal_count']}")
    print(f"[V4 Lab] duration={s['total_duration_sec']:.1f}s rpm_peak={s['rpm_peak_60s']}")
    print(f"[V4 Lab] output={out_dir}")
    print(f"[V4 Lab] isolation: lab_only=true official_candidate=false not_for_validation=true")

    return 0 if data["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
