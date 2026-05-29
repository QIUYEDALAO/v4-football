"""
V4 HT赛前推荐验证器
===================
用途：
1) 读取当日 scout，按 A/B/C/SKIP 分层
2) 拉赛果验证 HT 是否有球
3) 验证预测时间段命中（0-15 / 16-30 / 31-45）
4) 输出漏斗指标、单调性、联赛校准、覆盖率健康

用法：
  python3 engine/v4_ht_result_validator.py --date 20260513
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils
from engine.v4_match_intelligence import _load_rules, explain_match

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
LOCAL_TZ = timezone(timedelta(hours=8))


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _target_match_date(date_str: str) -> str:
    return datetime.strptime(_date_key(date_str), "%Y%m%d").date().isoformat()


def _kickoff_date(rec: dict) -> str | None:
    kickoff = str(rec.get("kickoff") or rec.get("kickoff_time") or "").strip()
    if not kickoff:
        return None
    try:
        dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ).date().isoformat()


def _record_match_date(rec: dict) -> str | None:
    raw = rec.get("match_date") or rec.get("date")
    if not raw:
        return None
    text = str(raw)
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    return text[:10]


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _bucket_from_minute(minute: int) -> str:
    if minute <= 15:
        return "0_15"
    if minute <= 30:
        return "16_30"
    return "31_45"


def _pick_predicted_bucket(time_bins: dict) -> str:
    bins = {
        "0_15": float(time_bins.get("0_15") or 0.0),
        "16_30": float(time_bins.get("16_30") or 0.0),
        "31_45": float(time_bins.get("31_45") or 0.0),
    }
    return max(bins, key=bins.get)


def _api_get(endpoint: str) -> dict:
    return net_utils.api_get(endpoint) or {}


def _fetch_fixture_ht_goals(fixture_id: int) -> int | None:
    resp = _api_get(f"fixtures?id={fixture_id}")
    rows = resp.get("response") or []
    if not rows:
        return None
    score = (rows[0].get("score") or {}).get("halftime") or {}
    h = score.get("home")
    a = score.get("away")
    if h is None or a is None:
        return None
    try:
        return int(h or 0) + int(a or 0)
    except Exception:
        return None


def _is_goal_event(ev: dict) -> bool:
    et = str(ev.get("type") or "").strip().lower()
    detail = str(ev.get("detail") or "").strip().lower()
    if et != "goal":
        return False
    # 严格过滤：只认真实进球，不认 missed penalty / var / awarded
    allowed = {"normal goal", "own goal", "penalty"}
    denied_keywords = {"missed", "cancel", "var", "awarded", "disallowed"}
    if detail in allowed:
        return True
    if any(k in detail for k in denied_keywords):
        return False
    # 某些源可能 detail 为空，但 type=Goal 且有 elapsed，保留
    return detail == ""


def _fetch_fixture_first_half_goal_buckets(fixture_id: int) -> list[str]:
    resp = _api_get(f"fixtures/events?fixture={fixture_id}")
    rows = resp.get("response") or []
    buckets: list[str] = []
    for ev in rows:
        if not _is_goal_event(ev):
            continue
        elapsed = (ev.get("time") or {}).get("elapsed")
        if elapsed is None:
            continue
        try:
            minute = int(elapsed)
        except Exception:
            continue
        if minute <= 45:
            buckets.append(_bucket_from_minute(minute))
    return sorted(set(buckets))


def _safe_pct(numer: int, denom: int) -> float:
    return round(numer / denom * 100, 1) if denom else 0.0


def _grade_stats(details: list[dict], grade: str) -> dict:
    subset = [d for d in details if d["grade"] == grade]
    completed = [d for d in subset if not d["pending"]]
    goal_hits = [d for d in completed if d["hit"] is True]
    bucket_hits = [d for d in completed if d["bucket_hit"]]
    return {
        "total": len(subset),
        "completed": len(completed),
        "pending": len(subset) - len(completed),
        "hit": len(goal_hits),
        "hit_rate_pct": _safe_pct(len(goal_hits), len(completed)),
        "bucket_hit": len(bucket_hits),
        "bucket_hit_rate_all_pct": _safe_pct(len(bucket_hits), len(completed)),
        "bucket_hit_rate_when_goal_pct": _safe_pct(len(bucket_hits), len(goal_hits)),
    }


def _monotonic_check(per_grade: dict) -> dict:
    """
    期望：A > B > C > SKIP
    """
    seq = ["A", "B", "C", "SKIP"]
    rates = [float((per_grade.get(g) or {}).get("hit_rate_pct", 0.0)) for g in seq]
    monotonic = all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))
    return {"sequence": seq, "rates": rates, "status": "PASS" if monotonic else "FAIL"}


def _league_calibration(details: list[dict]) -> list[dict]:
    by_league: dict[str, dict] = defaultdict(lambda: {
        "ab_recommended": 0,
        "ab_completed": 0,
        "ab_hit": 0,
        "ab_bucket_hit": 0,
        "ab_goal_hits": 0,
        "skip_total": 0,
        "skip_completed": 0,
        "skip_hit": 0,
    })
    for d in details:
        lg = str(d.get("league") or "-")
        g = d.get("grade")
        pending = bool(d.get("pending"))
        hit = d.get("hit") is True
        bucket_hit = d.get("bucket_hit") is True
        if g in ("A", "B"):
            by_league[lg]["ab_recommended"] += 1
            if not pending:
                by_league[lg]["ab_completed"] += 1
                if hit:
                    by_league[lg]["ab_hit"] += 1
                    by_league[lg]["ab_goal_hits"] += 1
                if bucket_hit:
                    by_league[lg]["ab_bucket_hit"] += 1
        if g == "SKIP":
            by_league[lg]["skip_total"] += 1
            if not pending:
                by_league[lg]["skip_completed"] += 1
                if hit:
                    by_league[lg]["skip_hit"] += 1

    out = []
    for lg, m in by_league.items():
        ab_rate = _safe_pct(m["ab_hit"], m["ab_completed"])
        skip_rate = _safe_pct(m["skip_hit"], m["skip_completed"])
        bucket_when_goal = _safe_pct(m["ab_bucket_hit"], m["ab_goal_hits"])
        if m["ab_completed"] < 20:
            status = "YELLOW"
        elif ab_rate > skip_rate and ab_rate >= 55:
            status = "GREEN"
        elif ab_rate <= skip_rate:
            status = "RED"
        else:
            status = "YELLOW"
        out.append({
            "league": lg,
            "ab_recommended": m["ab_recommended"],
            "ab_completed": m["ab_completed"],
            "ab_hit_rate_pct": ab_rate,
            "skip_completed": m["skip_completed"],
            "skip_hit_rate_pct": skip_rate,
            "ab_bucket_hit_when_goal_pct": bucket_when_goal,
            "status": status,
        })
    out.sort(key=lambda x: (-x["ab_recommended"], x["league"]))
    return out


def _load_no_market_excluded_fixtures() -> set[int]:
    """
    Load all no-market exclusions across all dates and return a deduped set of fixture_ids.
    This ensures no-market fixtures are skipped regardless of date alignment.
    """
    excluded: set[int] = set()
    live_dir = BASE_DIR / "data" / "runtime" / "live_bets"
    if not live_dir.exists():
        return excluded
    for p in sorted(live_dir.glob("v4_no_market_exclusions_*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            fid = rec.get("fixture_id")
            if fid:
                excluded.add(int(fid))
    return excluded


def run_validation(date_str: str, sleep_ms: int = 120) -> dict:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if not scout:
        return {"error": f"scout文件不存在或为空: {scout_path}"}

    rows = scout if isinstance(scout, list) else scout.get("results", [])
    target_match_date = _target_match_date(date_str)
    
    # Load NO_MARKET excluded fixture IDs (across all dates)
    no_market_excluded_fixtures = _load_no_market_excluded_fixtures()
    
    filtered_rows = []
    contaminated_rows = []
    non_target_rows = 0
    c_deprecated_rows = 0
    no_market_skipped_count = 0
    no_market_skipped_ids: list[int] = []
    for rec in rows:
        fid = rec.get("fixture_id")
        record_date = _record_match_date(rec)
        ko_date = _kickoff_date(rec)
        
        # Skip NO_MARKET fixtures before any processing
        if fid and int(fid) in no_market_excluded_fixtures:
            no_market_skipped_count += 1
            no_market_skipped_ids.append(int(fid))
            continue
        
        if ko_date and record_date and record_date != ko_date:
            contaminated_rows.append({
                "fixture_id": fid,
                "date": rec.get("date"),
                "match_date": rec.get("match_date"),
                "kickoff": rec.get("kickoff"),
                "kickoff_date": ko_date,
            })
            continue
        if record_date != target_match_date:
            non_target_rows += 1
            continue
        intel = explain_match(rec)
        ht_rec = intel.get("ht_recommendation") or {}
        grade = str(ht_rec.get("grade") or "SKIP").upper()
        if grade == "C":
            c_deprecated_rows += 1
            continue
        filtered_rows.append(rec)
    
    print(f"[VALIDATION] NO_MARKET skipped: {no_market_skipped_count} fixtures — {no_market_skipped_ids}", flush=True)
    
    rows = filtered_rows
    details = []
    pending = 0

    for rec in rows:
        fid = rec.get("fixture_id")
        intel = explain_match(rec)
        ht_rec = intel.get("ht_recommendation") or {}
        grade = str(ht_rec.get("grade") or "SKIP").upper()
        predicted_bucket = _pick_predicted_bucket(ht_rec.get("time_bins") or {})

        ht_goals = None
        actual_buckets: list[str] = []
        if fid:
            ht_goals = _fetch_fixture_ht_goals(int(fid))
            if ht_goals is not None:
                actual_buckets = _fetch_fixture_first_half_goal_buckets(int(fid))
            time.sleep(max(sleep_ms, 0) / 1000.0)

        is_pending = ht_goals is None
        if is_pending:
            pending += 1
        hit = (ht_goals or 0) > 0 if ht_goals is not None else None
        bucket_hit = predicted_bucket in actual_buckets if actual_buckets else False

        details.append(
            {
                "fixture_id": fid,
                "home": rec.get("home"),
                "away": rec.get("away"),
                "league": rec.get("league"),
                "grade": grade,
                "status": ht_rec.get("status"),
                "rule_version": ht_rec.get("rule_version"),
                "predicted_bucket": predicted_bucket,
                "actual_buckets": actual_buckets,
                "bucket_hit": bucket_hit,
                "ht_goals": ht_goals,
                "hit": hit,
                "pending": is_pending,
            }
        )

    per_grade = {g: _grade_stats(details, g) for g in ("A", "B", "C", "SKIP")}
    completed_all = [d for d in details if not d["pending"]]
    goal_hits_all = [d for d in completed_all if d["hit"] is True]
    bucket_hits_all = [d for d in completed_all if d["bucket_hit"]]
    ab_completed = [d for d in completed_all if d["grade"] in ("A", "B")]
    ab_goal_hits = [d for d in ab_completed if d["hit"] is True]
    ab_bucket_hits = [d for d in ab_completed if d["bucket_hit"]]

    funnel = {
        "total": len(details),
        "completed": len(completed_all),
        "pending": pending,
        "a_plus_b_total": len([d for d in details if d["grade"] in ("A", "B")]),
        "a_plus_b_completed": len(ab_completed),
        "a_plus_b_hit_rate_pct": _safe_pct(len(ab_goal_hits), len(ab_completed)),
        "a_hit_rate_pct": per_grade["A"]["hit_rate_pct"],
        "b_hit_rate_pct": per_grade["B"]["hit_rate_pct"],
        "c_hit_rate_pct": per_grade["C"]["hit_rate_pct"],
        "skip_hit_rate_pct": per_grade["SKIP"]["hit_rate_pct"],
        "skip_backfire_rate_pct": per_grade["SKIP"]["hit_rate_pct"],  # SKIP反杀率
    }

    bucket_quality = {
        "bucket_hit_rate_all_pct": _safe_pct(len(bucket_hits_all), len(completed_all)),
        "bucket_hit_rate_when_goal_pct": _safe_pct(len(bucket_hits_all), len(goal_hits_all)),
        "ab_bucket_hit_rate_all_pct": _safe_pct(len(ab_bucket_hits), len(ab_completed)),
        "ab_bucket_hit_rate_when_goal_pct": _safe_pct(len(ab_bucket_hits), len(ab_goal_hits)),
    }

    monotonic = _monotonic_check(per_grade)
    league_calibration = _league_calibration(details)

    rules = _load_rules()
    ab_ratio = _safe_pct(
        len([d for d in details if d["grade"] in ("A", "B")]),
        len(details),
    )
    ab_min = float(((rules.get("coverage_target") or {}).get("ab_ratio_min_pct")) or 5.0)
    ab_max = float(((rules.get("coverage_target") or {}).get("ab_ratio_max_pct")) or 15.0)
    coverage_health = "OK"
    if ab_ratio < ab_min:
        coverage_health = "LOW"
    elif ab_ratio > ab_max:
        coverage_health = "HIGH"

    grade_counts = Counter(d["grade"] for d in details)
    out = {
        "date": key,
        "date_filter_field": "match_date",
        "target_match_date": target_match_date,
        "input_rows": len(scout if isinstance(scout, list) else scout.get("results", [])),
        "filtered_rows": len(rows),
        "non_target_rows": non_target_rows,
        "contaminated_rows": len(contaminated_rows),
        "contaminated_row_samples": contaminated_rows[:10],
        "c_deprecated_rows_excluded": c_deprecated_rows,
        "c_observation_active": False,
        "c_excluded_from_ab": True,
        "no_market_excluded_count": no_market_skipped_count,
        "no_market_excluded_fixtures": no_market_skipped_ids,
        "generated_at": datetime.now().isoformat(),
        "rule_version": str(rules.get("rule_version") or "-"),
        "total_matches": len(details),
        "pending_matches": pending,
        "grade_counts": dict(grade_counts),
        "funnel": funnel,
        "per_grade": per_grade,
        "monotonicity": monotonic,
        "bucket_quality": bucket_quality,
        "coverage_monitor": {
            "ab_ratio_pct": ab_ratio,
            "target_min_pct": ab_min,
            "target_max_pct": ab_max,
            "health": coverage_health,
        },
        "league_calibration": league_calibration,
        "details": details,
    }
    out_path = REPORT_DIR / f"v4_ht_recommend_validation_{key}.json"
    _save_json(out_path, out)
    out["output_path"] = str(out_path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--sleep-ms", type=int, default=120, help="API调用间隔（毫秒）")
    args = parser.parse_args()
    result = run_validation(args.date, sleep_ms=args.sleep_ms)
    print(json.dumps({k: v for k, v in result.items() if k not in ("details", "league_calibration")}, ensure_ascii=False, indent=2))
    print(json.dumps({"league_calibration_top10": result.get("league_calibration", [])[:10]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
