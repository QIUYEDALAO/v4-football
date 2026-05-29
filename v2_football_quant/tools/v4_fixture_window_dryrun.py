#!/usr/bin/env python3
"""
v4_fixture_window_dryrun.py — 业务日窗口 dry-run 验证
==================================================
只读验证。不写 official 路径。不推 QQ。不触发 validation。
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"

CN_TZ = timezone(timedelta(hours=8))

def run_dryrun():
    from engine import net_utils
    from engine.v4_runner import fetch_today_fixtures

    today = date.today()
    td_str = today.strftime("%Y-%m-%d")
    nd = today + timedelta(days=1)
    nd_str = nd.strftime("%Y-%m-%d")

    print(f"[dryrun] scan_base_date={td_str}")
    print(f"[dryrun] BJ business window: {td_str} 12:00 → {nd_str} 12:00")

    # Fetch with include_outside_57=True (same as V4 lab/production)
    fixtures = fetch_today_fixtures(
        lookahead_hours=None,
        min_hours_to_kickoff=None,
        api_client=net_utils.api_get,
        scan_base_date=today,
        include_outside_57=True,
    )

    # Analyze
    raw_count = len(fixtures)
    window_count = 0
    excluded_next_evening = []
    earliest_kickoff = None
    latest_kickoff = None
    next_day_21_22 = []
    before_12_today = []
    after_12_nextday = []

    for fx in fixtures:
        kcj = fx.get("kickoff_bj", "")
        bws = fx.get("business_window_start_bj", "")
        bwe = fx.get("business_window_end_bj", "")
        fwbw = fx.get("filtered_by_business_window", False)

        if kcj:
            try:
                kdt = datetime.fromisoformat(kcj)
                if earliest_kickoff is None or kdt < earliest_kickoff:
                    earliest_kickoff = kdt
                if latest_kickoff is None or kdt > latest_kickoff:
                    latest_kickoff = kdt

                # Check for specific offenders
                bj_hour = kdt.hour
                if kdt.strftime("%Y-%m-%d") == nd_str and bj_hour >= 12:
                    after_12_nextday.append(fx)
                if kdt.strftime("%Y-%m-%d") == td_str and bj_hour < 12:
                    before_12_today.append(fx)
                if kdt.strftime("%Y-%m-%d") == nd_str and bj_hour in (21, 22):
                    next_day_21_22.append(fx)
            except:
                pass

        if not fwbw:
            window_count += 1

    report = {
        "schema": "v4_fixture_business_window_dryrun.v1",
        "generated_at": datetime.now(CN_TZ).isoformat(),
        "config": {
            "scan_base_date": td_str,
            "business_window_start_bj": f"{td_str} 12:00",
            "business_window_end_bj": f"{nd_str} 12:00",
            "include_outside_57": True,
        },
        "results": {
            "scan_total_raw": raw_count,
            "business_window_passed_count": window_count,
            "excluded_by_business_window": raw_count - window_count,
            "earliest_kickoff_bj": earliest_kickoff.isoformat() if earliest_kickoff else None,
            "latest_kickoff_bj": latest_kickoff.isoformat() if latest_kickoff else None,
        },
        "validation": {
            "next_day_21_22_entries": len(next_day_21_22),
            "next_day_21_22_list": [
                {
                    "fixture_id": fx.get("id"),
                    "home": fx.get("home"),
                    "away": fx.get("away"),
                    "league": fx.get("league_name"),
                    "kickoff_bj": fx.get("kickoff_bj"),
                }
                for fx in next_day_21_22
            ],
            "today_before_12_entries": len(before_12_today),
            "today_before_12_list": [
                {
                    "fixture_id": fx.get("id"),
                    "home": fx.get("home"),
                    "away": fx.get("away"),
                    "kickoff_bj": fx.get("kickoff_bj"),
                }
                for fx in before_12_today[:5]
            ],
            "next_day_12_and_after_entries": len(after_12_nextday),
            "next_day_12_and_after_list": [
                {
                    "fixture_id": fx.get("id"),
                    "home": fx.get("home"),
                    "away": fx.get("away"),
                    "kickoff_bj": fx.get("kickoff_bj"),
                }
                for fx in after_12_nextday[:5]
            ],
        },
        "forbidden": {
            "strategy_thresholds_changed": False,
            "candidate_rating_rules_changed": False,
            "cron_modified": False,
            "validation_recomputed": False,
            "live_bet_records_modified": False,
            "qq_recommendation_pushed": False,
            "candidate_view_generatable": False,
            "scout_brief_generatable": False,
        },
        "conclusion": "PASS" if (len(next_day_21_22) == 0 and len(after_12_nextday) == 0) else "BLOCKED",
    }
    return report

if __name__ == "__main__":
    report = run_dryrun()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    out_path = STATUS_DIR / "v4_fixture_business_window_dryrun_20260530.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten: {out_path}")
    sys.exit(0 if report["conclusion"] == "PASS" else 1)
