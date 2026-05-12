from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.live_capture_profile import load_profile, tier_conf

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
UNIVERSE_DIR = BASE_DIR / "data" / "universe"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _parse_date_key(key: str) -> datetime:
    return datetime.strptime(key, "%Y%m%d")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _load_universe_window(base_key: str, lookahead_days: int) -> list[dict]:
    base_dt = _parse_date_key(base_key)
    rows = []
    for d in range(0, max(0, int(lookahead_days)) + 1):
        key = (base_dt + timedelta(days=d)).strftime("%Y%m%d")
        path = UNIVERSE_DIR / f"fixtures_universe_{key}.jsonl"
        rows.extend(_load_jsonl(path))
    return rows


def _available_universe_keys() -> list[str]:
    keys = []
    for p in UNIVERSE_DIR.glob("fixtures_universe_*.jsonl"):
        name = p.stem  # fixtures_universe_YYYYMMDD
        key = name.split("_")[-1]
        if len(key) == 8 and key.isdigit():
            keys.append(key)
    return sorted(set(keys))


def _load_universe_window_auto(
    base_key: str,
    lookahead_days: int,
    lookback_days: int,
    max_universe_files: int,
) -> tuple[list[dict], list[str], list[str], list[str]]:
    base_dt = _parse_date_key(base_key)
    start_dt = base_dt - timedelta(days=max(0, int(lookback_days)))
    end_dt = base_dt + timedelta(days=max(0, int(lookahead_days)))
    keys = _available_universe_keys()
    expected = []
    cur = start_dt
    while cur <= end_dt:
        expected.append(cur.strftime("%Y%m%d"))
        cur += timedelta(days=1)
    selected = []
    for key in keys:
        try:
            dt = _parse_date_key(key)
        except Exception:
            continue
        if start_dt <= dt <= end_dt:
            selected.append(key)
    if max_universe_files > 0:
        selected = selected[-max_universe_files:]

    rows = []
    for key in selected:
        rows.extend(_load_jsonl(UNIVERSE_DIR / f"fixtures_universe_{key}.jsonl"))
    missing = [k for k in expected if k not in selected]
    return rows, selected, expected, missing


def _dt(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _cov_rank(level: str) -> int:
    lv = str(level or "").upper()
    if lv == "FULL":
        return 4
    if lv == "GOOD":
        return 3
    if lv == "BASIC":
        return 2
    if lv == "UNKNOWN":
        return 1
    return 0


def _has_required_ht_lines(row: dict, required_lines: list[float]) -> bool:
    lines = row.get("ht_ou_lines") or []
    got = set()
    for item in lines:
        v = item.get("line") if isinstance(item, dict) else None
        try:
            got.add(float(v))
        except Exception:
            continue
    return all(x in got for x in required_lines)


def _ht_live_score(row: dict) -> float:
    scores = row.get("market_scores") or {}
    try:
        return float(scores.get("HT_LIVE_OVER") or 0.0)
    except Exception:
        return 0.0


def _tier_cost(profile: dict, tier: str) -> int:
    t = tier_conf(profile, tier)
    if tier == "C_slice":
        points = t.get("capture_minutes", []) or [0, 5, 8, 10, 12, 15, 20, 45]
        endpoints = t.get("endpoints", []) or ["odds_live", "fixture_state", "events"]
        return max(1, len(points) * len(endpoints))
    # 0-20min, include minute 0 => 41 points
    points = 41
    odds = max(1, int(t.get("odds_interval_sec", 30)))
    state = max(1, int(t.get("state_interval_sec", 30)))
    events = max(1, int(t.get("events_interval_sec", 30)))
    stats = max(1, int(t.get("stats_interval_sec", 60)))
    # Approx total calls per match in 0-20 window
    calls = points * ((30.0 / odds) + (30.0 / state) + (30.0 / events) + (30.0 / stats))
    return max(1, int(round(calls)))


def _take_with_budget(rows: list[dict], tier: str, per_match_cost: int, budget_left: int, max_n: int) -> tuple[list[dict], int]:
    picked = []
    n = 0
    for row in rows:
        if n >= max_n:
            break
        if budget_left < per_match_cost:
            break
        picked.append({"tier": tier, "estimated_calls_0_20": per_match_cost, **row})
        budget_left -= per_match_cost
        n += 1
    return picked, budget_left


def _take_remaining_budget(
    rows: list[dict],
    already_ids: set[int],
    tier: str,
    per_match_cost: int,
    budget_left: int,
) -> tuple[list[dict], int]:
    picked = []
    for row in rows:
        fid = int(row.get("fixture_id") or 0)
        if not fid or fid in already_ids:
            continue
        if budget_left < per_match_cost:
            break
        picked.append({"tier": tier, "estimated_calls_0_20": per_match_cost, **row})
        already_ids.add(fid)
        budget_left -= per_match_cost
    return picked, budget_left


def build_tasks(
    date_str: str,
    profile_name: str,
    budget: int,
    rate_limit: int,
    max_a: Optional[int] = None,
    max_b: Optional[int] = None,
    max_c: Optional[int] = None,
    lookahead_days: int = 3,
    lookback_days: int = 0,
    max_universe_files: int = 14,
    min_b: int = 0,
    min_c: int = 0,
) -> dict:
    key = _date_key(date_str)
    profile = load_profile(profile_name)
    scout = _load_json(REPORT_DIR / f"scout_v4_{key}.json", [])
    watch = _load_json(REPORT_DIR / f"live_watchlist_{key}.json", [])
    # Fallback: when live_watchlist is absent, use scout for strict extraction.
    if not isinstance(watch, list) or not watch:
        watch = scout if isinstance(scout, list) else []
    universe, universe_keys, universe_expected_keys, universe_missing_keys = _load_universe_window_auto(
        key,
        lookahead_days=lookahead_days,
        lookback_days=lookback_days,
        max_universe_files=max_universe_files,
    )

    a_rows = []
    a_strict = []
    a_relaxed = []
    strict_from_v1 = 0
    strict_from_v2 = 0
    sched = profile.get("scheduler") or {}
    strict_v2_conf = sched.get("strict_v2") or {}
    strict_v2_enabled = bool(strict_v2_conf.get("enabled", True))
    strict_v2_min_ht = float(strict_v2_conf.get("min_ht_live_score", 55.0))
    strict_v2_cov = {
        str(x).upper() for x in (strict_v2_conf.get("allow_coverage_levels") or ["BASIC", "GOOD", "FULL"])
    }
    strict_v2_lines = [float(x) for x in (strict_v2_conf.get("require_key_lines") or [0.75, 1.0, 1.25])]
    for x in watch:
        cov = str(((x.get("data_coverage") or {}).get("coverage_level") or "")).upper()
        # v1 strict: old definition
        if x.get("market_focus") == "HT_LIVE_OVER" and cov in ("GOOD", "FULL"):
            row = {"a_source": "strict", **x}
            a_rows.append(row)
            a_strict.append(row)
            strict_from_v1 += 1
            continue

        # v2 strict: for capture infrastructure, allow BASIC coverage when
        # HT live score is strong and HT key lines are present.
        ht_score = _ht_live_score(x)
        if strict_v2_enabled and cov in strict_v2_cov and ht_score >= strict_v2_min_ht and _has_required_ht_lines(x, strict_v2_lines):
            row = {
                "a_source": "strict",
                "strict_rule": "v2_ht_score_and_key_lines",
                "strict_ht_score": ht_score,
                **x,
            }
            a_rows.append(row)
            a_strict.append(row)
            strict_from_v2 += 1

    # Relaxed A channel for data collection: keep strict execution logic elsewhere.
    strict_ids = {int(x.get("fixture_id")) for x in a_rows if x.get("fixture_id")}
    for x in scout:
        fid = int(x.get("fixture_id") or 0)
        if not fid or fid in strict_ids:
            continue
        cov = str(((x.get("data_coverage") or {}).get("coverage_level") or "")).upper()
        score = float(x.get("best_score") or 0.0)
        if score < 70:
            continue
        if cov not in ("GOOD", "FULL", "BASIC"):
            continue
        row = {
            "a_source": "relaxed",
            "fixture_id": fid,
            "home": x.get("home"),
            "away": x.get("away"),
            "league": x.get("league"),
            "kickoff": x.get("kickoff"),
            "market_focus": x.get("market_focus"),
            "best_score": score,
            "data_coverage": x.get("data_coverage") or {"coverage_level": cov},
            "relaxed_rule": "best_score>=70_and_coverage_basic_plus",
        }
        a_rows.append(row)
        a_relaxed.append(row)

    a_ids = {int(x.get("fixture_id")) for x in a_rows if x.get("fixture_id")}
    b_rows = []
    c_rows = []

    now = datetime.now().astimezone()
    end_time = now + timedelta(days=max(0, int(lookahead_days)))

    best_by_fixture: dict[int, dict] = {}
    excluded_reason_counts = Counter()
    universe_total = len(universe)
    for x in universe:
        fid = int(x.get("fixture_id") or 0)
        if not fid:
            excluded_reason_counts["missing_fixture_id"] += 1
            continue
        if fid in a_ids:
            excluded_reason_counts["already_in_A"] += 1
            continue
        kickoff = _dt(str(x.get("kickoff_time") or ""))
        if kickoff is not None:
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=now.tzinfo)
            if kickoff < now:
                excluded_reason_counts["kickoff_already_started"] += 1
                continue
            if kickoff > end_time:
                excluded_reason_counts["kickoff_outside_window"] += 1
                continue
        else:
            excluded_reason_counts["missing_kickoff"] += 1
            continue
        cov = str(x.get("api_coverage_level") or "UNKNOWN").upper()
        rec = {
            "fixture_id": fid,
            "league": x.get("league_name"),
            "home": x.get("home_team"),
            "away": x.get("away_team"),
            "kickoff": x.get("kickoff_time"),
            "market_focus": "UNIVERSE_SHADOW",
            "best_score": float(x.get("candidate_score") or 0.0),
            "data_coverage": {"coverage_level": cov, "data_gate_action": "UNIVERSE"},
            "universe_filter_result": x.get("filter_result"),
            "universe_filter_reason": x.get("filter_reason"),
            "is_candidate": bool(x.get("is_candidate")),
        }
        prev = best_by_fixture.get(fid)
        if prev is None:
            best_by_fixture[fid] = rec
            continue
        prev_score = float(prev.get("best_score") or 0.0)
        rec_score = float(rec.get("best_score") or 0.0)
        prev_cov = _cov_rank(((prev.get("data_coverage") or {}).get("coverage_level")))
        rec_cov = _cov_rank(cov)
        if rec_cov > prev_cov or (rec_cov == prev_cov and rec_score > prev_score):
            best_by_fixture[fid] = rec
        excluded_reason_counts["duplicate_fixture_kept_best"] += 1

    eligible_live_total = len(best_by_fixture)
    for rec in best_by_fixture.values():
        cov = str(((rec.get("data_coverage") or {}).get("coverage_level") or "")).upper()
        if cov in ("GOOD", "FULL", "BASIC"):
            b_rows.append(rec)
        else:
            c_rows.append(rec)

    # prioritize by score so sprint mode captures most informative samples first
    a_rows.sort(key=lambda x: float(x.get("best_score") or 0), reverse=True)
    b_rows.sort(
        key=lambda x: (
            _cov_rank(((x.get("data_coverage") or {}).get("coverage_level"))),
            float(x.get("best_score") or 0),
        ),
        reverse=True,
    )
    c_rows.sort(key=lambda x: float(x.get("best_score") or 0), reverse=True)

    day_budget = profile.get("daily_budget") or {}
    reserve = int(day_budget.get("reserve", 10000))
    usable_budget = max(0, int(budget) - reserve)
    eff_max_a = int(max_a if max_a is not None else sched.get("max_a", len(a_rows)))
    eff_max_b = int(max_b if max_b is not None else sched.get("max_b", len(b_rows)))
    eff_max_c = int(max_c if max_c is not None else sched.get("max_c", len(c_rows)))
    a_cost = _tier_cost(profile, "A_candidate")
    b_cost = _tier_cost(profile, "B_shadow")
    c_cost = _tier_cost(profile, "C_slice")

    # budget allocation: A first, then B, then C
    tasks_a, left = _take_with_budget(a_rows, "A_candidate", a_cost, usable_budget, max(0, eff_max_a))
    tasks_b, left = _take_with_budget(b_rows, "B_shadow", b_cost, left, max(0, eff_max_b))
    tasks_c, left = _take_with_budget(c_rows, "C_slice", c_cost, left, max(0, eff_max_c))
    picked_ids = {int(x.get("fixture_id") or 0) for x in (tasks_a + tasks_b + tasks_c)}

    # Guarantee minimum B/C coverage when possible.
    if len(tasks_b) < max(0, min_b):
        need = max(0, min_b) - len(tasks_b)
        extra_b_pool = [x for x in b_rows if int(x.get("fixture_id") or 0) not in picked_ids]
        extra_b, left = _take_with_budget(extra_b_pool, "B_shadow", b_cost, left, need)
        tasks_b.extend(extra_b)
        picked_ids.update(int(x.get("fixture_id") or 0) for x in extra_b)

    if len(tasks_c) < max(0, min_c):
        need = max(0, min_c) - len(tasks_c)
        extra_c_pool = [x for x in c_rows if int(x.get("fixture_id") or 0) not in picked_ids]
        extra_c, left = _take_with_budget(extra_c_pool, "C_slice", c_cost, left, need)
        tasks_c.extend(extra_c)
        picked_ids.update(int(x.get("fixture_id") or 0) for x in extra_c)

    # If budget is still available, spend remainder on B first, then C.
    extra_b_all, left = _take_remaining_budget(b_rows, picked_ids, "B_shadow", b_cost, left)
    extra_c_all, left = _take_remaining_budget(c_rows, picked_ids, "C_slice", c_cost, left)
    tasks_b.extend(extra_b_all)
    tasks_c.extend(extra_c_all)

    tasks = tasks_a + tasks_b + tasks_c

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
            "A_candidate": len(tasks_a),
            "B_shadow": len(tasks_b),
            "C_slice": len(tasks_c),
        },
        "a_channel_breakdown": {
            "strict_candidates": len(a_strict),
            "relaxed_candidates": len(a_relaxed),
            "strict_v1_candidates": strict_from_v1,
            "strict_v2_candidates": strict_from_v2,
        },
        "generated_at": datetime.now().isoformat(),
        "lookahead_days": lookahead_days,
        "lookback_days": lookback_days,
        "universe_total": universe_total,
        "eligible_live_total": eligible_live_total,
        "universe_count": len(universe),
        "universe_files_used": universe_keys,
        "universe_files_expected": universe_expected_keys,
        "universe_files_missing": universe_missing_keys,
        "excluded_reason_counts": dict(excluded_reason_counts),
        "scheduler_limits": {"max_a": eff_max_a, "max_b": eff_max_b, "max_c": eff_max_c},
        "strict_rule_config": {
            "v1": {"market_focus": "HT_LIVE_OVER", "coverage_levels": ["GOOD", "FULL"]},
            "v2": {
                "enabled": strict_v2_enabled,
                "min_ht_live_score": strict_v2_min_ht,
                "allow_coverage_levels": sorted(strict_v2_cov),
                "require_key_lines": strict_v2_lines,
            },
        },
        "minimum_targets": {"min_b": int(min_b), "min_c": int(min_c)},
        "estimated_cost_per_match": {"A_candidate": a_cost, "B_shadow": b_cost, "C_slice": c_cost},
        "budget_planning": {
            "input_budget": int(budget),
            "reserve": reserve,
            "usable_budget": usable_budget,
            "estimated_used": usable_budget - left,
            "estimated_remaining": left,
        },
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
    parser.add_argument("--lookahead-days", type=int, default=2)
    parser.add_argument("--lookback-days", type=int, default=0)
    parser.add_argument("--max-universe-files", type=int, default=14)
    parser.add_argument("--min-b", type=int, default=0)
    parser.add_argument("--min-c", type=int, default=0)
    args = parser.parse_args()

    result = build_tasks(
        args.date,
        args.profile,
        args.budget,
        args.rate_limit,
        max_a=args.max_a,
        max_b=args.max_b,
        max_c=args.max_c,
        lookahead_days=args.lookahead_days,
        lookback_days=args.lookback_days,
        max_universe_files=args.max_universe_files,
        min_b=args.min_b,
        min_c=args.min_c,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
