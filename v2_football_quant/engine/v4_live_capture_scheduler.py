from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.live_capture_profile import load_profile

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_tasks(
    date_str: str,
    profile_name: str,
    budget: int,
    rate_limit: int,
    max_a: Optional[int] = None,
    max_b: Optional[int] = None,
    max_c: Optional[int] = None,
) -> dict:
    key = _date_key(date_str)
    profile = load_profile(profile_name)
    scout = _load_json(REPORT_DIR / f"scout_v4_{key}.json", [])
    watch = _load_json(REPORT_DIR / f"live_watchlist_{key}.json", [])

    a_rows = []
    for x in watch:
        cov = str(((x.get("data_coverage") or {}).get("coverage_level") or "")).upper()
        if x.get("market_focus") == "HT_LIVE_OVER" and cov in ("GOOD", "FULL"):
            a_rows.append(x)

    a_ids = {int(x.get("fixture_id")) for x in a_rows if x.get("fixture_id")}
    b_rows = []
    c_rows = []

    for x in scout:
        fid = int(x.get("fixture_id") or 0)
        if not fid or fid in a_ids:
            continue
        cov = str(((x.get("data_coverage") or {}).get("coverage_level") or "")).upper()
        rec = {
            "fixture_id": fid,
            "league": x.get("league"),
            "home": x.get("home"),
            "away": x.get("away"),
            "kickoff": x.get("kickoff"),
            "market_focus": x.get("market_focus"),
            "best_score": x.get("best_score"),
            "data_coverage": x.get("data_coverage"),
        }
        if cov in ("GOOD", "FULL"):
            b_rows.append(rec)
        else:
            c_rows.append(rec)

    # prioritize by score so sprint mode captures most informative samples first
    a_rows.sort(key=lambda x: float(x.get("best_score") or 0), reverse=True)
    b_rows.sort(key=lambda x: float(x.get("best_score") or 0), reverse=True)
    c_rows.sort(key=lambda x: float(x.get("best_score") or 0), reverse=True)

    sched = profile.get("scheduler") or {}
    eff_max_a = int(max_a if max_a is not None else sched.get("max_a", len(a_rows)))
    eff_max_b = int(max_b if max_b is not None else sched.get("max_b", len(b_rows)))
    eff_max_c = int(max_c if max_c is not None else sched.get("max_c", len(c_rows)))
    a_rows = a_rows[:max(0, eff_max_a)]
    b_rows = b_rows[:max(0, eff_max_b)]
    c_rows = c_rows[:max(0, eff_max_c)]

    tasks = []
    for x in a_rows:
        tasks.append({"tier": "A_candidate", **x})
    for x in b_rows:
        tasks.append({"tier": "B_shadow", **x})
    for x in c_rows:
        tasks.append({"tier": "C_slice", **x})

    out = {
        "date": key,
        "profile": profile_name,
        "budget": {
            "hard_limit": budget,
            "soft_limit": int((profile.get("daily_budget") or {}).get("soft_limit", 65000)),
            "reserve": int((profile.get("daily_budget") or {}).get("reserve", 10000)),
        },
        "rate_limit_per_minute": rate_limit,
        "tier_counts": {
            "A_candidate": len(a_rows),
            "B_shadow": len(b_rows),
            "C_slice": len(c_rows),
        },
        "generated_at": datetime.now().isoformat(),
        "scheduler_limits": {"max_a": eff_max_a, "max_b": eff_max_b, "max_c": eff_max_c},
        "tasks": tasks,
    }
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    path = MONITOR_DIR / f"v4_capture_tasks_{key}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["task_file"] = str(path)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--profile", default="ultra")
    parser.add_argument("--budget", type=int, default=75000)
    parser.add_argument("--rate-limit", type=int, default=350)
    parser.add_argument("--max-a", type=int, default=None)
    parser.add_argument("--max-b", type=int, default=None)
    parser.add_argument("--max-c", type=int, default=None)
    args = parser.parse_args()

    result = build_tasks(
        args.date,
        args.profile,
        args.budget,
        args.rate_limit,
        max_a=args.max_a,
        max_b=args.max_b,
        max_c=args.max_c,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
