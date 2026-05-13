"""
V4 HT赛前推荐验证器
===================
用途：
1) 读取当日 scout，按 A/B/C/SKIP 生成HT推荐分层
2) 拉取赛果后验证上半场是否有球（命中）
3) 对比预测时间段（0-15 / 16-30 / 31-45）与实际进球时间段

用法：
  python3 engine/v4_ht_result_validator.py --date 20260513
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils
from engine.v4_match_intelligence import explain_match

REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


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


def _fetch_fixture_first_half_goal_buckets(fixture_id: int) -> list[str]:
    resp = _api_get(f"fixtures/events?fixture={fixture_id}")
    rows = resp.get("response") or []
    buckets: list[str] = []
    for ev in rows:
        et = str(ev.get("type") or "").lower()
        detail = str(ev.get("detail") or "").lower()
        if "goal" not in et and "goal" not in detail and "penalty" not in detail:
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


def run_validation(date_str: str, sleep_ms: int = 120) -> dict:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if not scout:
        return {"error": f"scout文件不存在或为空: {scout_path}"}

    rows = scout if isinstance(scout, list) else scout.get("results", [])
    details = []
    grade_counts = Counter()
    hit_counts = Counter()
    bucket_match_counts = Counter()
    pending = 0

    for rec in rows:
        fid = rec.get("fixture_id")
        intel = explain_match(rec)
        ht_rec = intel.get("ht_recommendation") or {}
        grade = str(ht_rec.get("grade") or "SKIP")
        grade_counts[grade] += 1
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

        if hit is True:
            hit_counts[grade] += 1
        if bucket_hit:
            bucket_match_counts[grade] += 1

        details.append(
            {
                "fixture_id": fid,
                "home": rec.get("home"),
                "away": rec.get("away"),
                "league": rec.get("league"),
                "grade": grade,
                "status": ht_rec.get("status"),
                "predicted_bucket": predicted_bucket,
                "actual_buckets": actual_buckets,
                "bucket_hit": bucket_hit,
                "ht_goals": ht_goals,
                "hit": hit,
                "pending": is_pending,
            }
        )

    per_grade = {}
    for grade, total in grade_counts.items():
        completed = sum(1 for d in details if d["grade"] == grade and not d["pending"])
        hits = hit_counts.get(grade, 0)
        bucket_hits = bucket_match_counts.get(grade, 0)
        per_grade[grade] = {
            "total": total,
            "completed": completed,
            "pending": total - completed,
            "hit": hits,
            "hit_rate_pct": round(hits / completed * 100, 1) if completed else 0.0,
            "bucket_hit": bucket_hits,
            "bucket_hit_rate_pct": round(bucket_hits / completed * 100, 1) if completed else 0.0,
        }

    out = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "total_matches": len(details),
        "pending_matches": pending,
        "grade_counts": dict(grade_counts),
        "per_grade": per_grade,
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
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

