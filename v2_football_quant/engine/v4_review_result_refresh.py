#!/usr/bin/env python3
"""engine/v4_review_result_refresh.py — V4复盘赛果刷新层

在renderer前读取structured review JSON，对有数据缺失的匹配场次
调用APIFOOTBALL刷新HT比分、FT比分、进球分钟。
只刷新赛后结果字段，不改赛前A/B/C/SKIP评级。

输出：
  data/runtime/cache/v4_result_refresh_YYYYMMDD.json  — 缓存（运行时覆盖）
  data/runtime/audit/v4_review_result_refresh_YYYYMMDD.json — 审计记录

用法:
  python3 engine/v4_review_result_refresh.py --date 20260516
"""

import argparse
import json
import os
import ssl
import certifi
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
CACHE_DIR = BASE_DIR / "data" / "runtime" / "cache"
AUDIT_DIR = BASE_DIR / "data" / "runtime" / "audit"
LOCAL_TZ = timezone(timedelta(hours=8))

CACHE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _api_get(endpoint: str, api_key: str) -> dict:
    """Single API call with SSL context."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    url = f"https://v3.football.api-sports.io/{endpoint}"
    req = urllib.request.Request(url, headers={
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    })
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return json.loads(resp.read())


def refresh_fixture(fid: int, api_key: str) -> dict:
    """Refresh a single fixture: get HT/FT scores and goal minutes.
    Returns None on error."""
    try:
        # Get fixture results
        data = _api_get(f"fixtures?id={fid}", api_key)
        rows = data.get('response', [])
        if not rows:
            return {"error": "empty_response", "ht": "DATA_UNAVAILABLE", "ft": "DATA_UNAVAILABLE"}

        r = rows[0]
        score = r.get('score', {})
        ht = score.get('halftime', {})
        ft = score.get('fulltime', {})
        ht_home = ht.get('home')
        ht_away = ht.get('away')
        ft_home = ft.get('home')
        ft_away = ft.get('away')

        if ht_home is None or ht_away is None:
            return {"error": "ht_score_missing", "ht": "DATA_UNAVAILABLE", "ft": "DATA_UNAVAILABLE"}

        ht_str = f"{ht_home}-{ht_away}"
        ft_str = f"{ft_home}-{ft_away}" if ft_home is not None and ft_away is not None else "DATA_UNAVAILABLE"

        # Get events for goal minutes
        time.sleep(0.15)
        ev_data = _api_get(f"fixtures/events?fixture={fid}", api_key)
        ev_rows = ev_data.get('response', [])
        ht_goals = []
        for ev in ev_rows:
            etype = str(ev.get('type', '')).strip().lower()
            detail = str(ev.get('detail', '')).strip().lower()
            elapsed = (ev.get('time') or {}).get('elapsed')
            if etype == 'goal' and elapsed and int(elapsed) <= 45:
                ht_goals.append(int(elapsed))

        return {
            "error": None,
            "ht": ht_str,
            "ft": ft_str,
            "goal_minutes": sorted(ht_goals),
            "ht_goals_total": len(ht_goals),
        }

    except Exception as e:
        return {"error": str(e)[:200], "ht": "DATA_UNAVAILABLE", "ft": "DATA_UNAVAILABLE"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    key = str(args.date).replace("-", "")
    struct_path = REPORT_DIR / f"v4_review_structured_{key}.json"
    if not struct_path.exists():
        print(f"[REFRESH] ERROR: structured file not found: {struct_path}", flush=True)
        return

    api_key = os.environ.get('APIFOOTBALL_KEY') or os.environ.get('OPENCLAW_APIFOOTBALL_KEY')
    if not api_key:
        print("[REFRESH] ERROR: no API key available", flush=True)
        return

    with open(struct_path) as f:
        data = json.load(f)

    matches = data.get("matches", [])
    total = len(matches)
    refreshed = 0
    changed = 0
    still_missing = 0
    errors = 0
    results = []

    print(f"[REFRESH] Loaded {total} matches from structured JSON", flush=True)

    for i, m in enumerate(matches):
        fid = m.get("fixture_id")
        if not fid or not isinstance(fid, int):
            continue

        old_ht = str(m.get("ht_score", ""))
        # Only refresh if data is unavailable or pending
        if old_ht not in ("DATA_UNAVAILABLE", "N/A", "") and "?" not in old_ht:
            continue  # Already has data

        result = refresh_fixture(fid, api_key)
        refreshed += 1

        entry = {
            "fixture_id": fid,
            "home": m.get("home", "?"),
            "away": m.get("away", "?"),
            "bucket": m.get("official_bucket", "?"),
            "old_ht": old_ht,
            "old_ft": str(m.get("ft_score", "")),
            "refreshed_ht": result.get("ht", "DATA_UNAVAILABLE"),
            "refreshed_ft": result.get("ft", "DATA_UNAVAILABLE"),
            "goal_minutes": result.get("goal_minutes", []),
            "error": result.get("error"),
            "changed": False,
            "refreshed_at": datetime.now(LOCAL_TZ).isoformat(),
        }

        if result.get("error"):
            errors += 1
            still_missing += 1
        elif result.get("ht") != "DATA_UNAVAILABLE":
            changed += 1
            entry["changed"] = True
            # Update structured data in-place
            m["ht_score"] = result["ht"]
            m["ft_score"] = result["ft"]
            m["first_half_goal_minutes"] = result.get("goal_minutes", [])
            m["data_source"] = "API_RESULT_REFRESH"
            # Recalculate model_result and diagnosis based on refreshed data
            ht_goals = sum(int(x) for x in result["ht"].split("-") if x.isdigit())
            if ht_goals > 0:
                m["ht_score_value"] = ht_goals
                if m.get("official_bucket") in ("A", "B"):
                    m["model_result"] = f"{m['official_bucket']}_HIT"
                    m["diagnosis"] = "MODEL_VALID"
                elif m.get("official_bucket") == "C":
                    m["model_result"] = "C_HIT"
                    m["diagnosis"] = "MODEL_VALID"
                else:
                    m["model_result"] = "SKIP_BACKFIRE"
                    m["diagnosis"] = "MODEL_TOO_STRICT"
            else:
                m["ht_score_value"] = 0
                m["model_result"] = f"{m['official_bucket']}_MISS"
                m["diagnosis"] = "MODEL_OVERCONFIDENT"
        else:
            still_missing += 1

        results.append(entry)

        if (i + 1) % 10 == 0:
            print(f"[REFRESH] Progress: {i+1}/{total}", flush=True)

        time.sleep(0.12)

    # Compute bucket-goal minutes distribution
    for m in matches:
        goals = m.get("first_half_goal_minutes", [])
        m["goals_0_15"] = sum(1 for g in goals if g <= 15)
        m["goals_16_30"] = sum(1 for g in goals if 16 <= g <= 30)
        m["goals_31_45"] = sum(1 for g in goals if 31 <= g <= 45)
        if goals:
            fg = min(goals)
            m["first_goal_bucket"] = "0_15" if fg <= 15 else "16_30" if fg <= 30 else "31_45"
        else:
            m["first_goal_bucket"] = ""

    # Write updated structured JSON
    struct_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Write audit log
    audit = {
        "date": key,
        "total_matches": total,
        "refreshed": refreshed,
        "changed": changed,
        "still_missing": still_missing,
        "errors": errors,
        "results": results,
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
    }
    audit_path = AUDIT_DIR / f"v4_review_result_refresh_{key}.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2))

    # Write cache
    cache_path = CACHE_DIR / f"v4_result_refresh_{key}.json"
    cache_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2))

    print(f"\n[REFRESH] Done: total={total} refreshed={refreshed} changed={changed} still_missing={still_missing} errors={errors}", flush=True)
    print(f"[REFRESH] Updated structured: {struct_path.name}", flush=True)
    print(f"[REFRESH] Audit: {audit_path.name}", flush=True)


if __name__ == "__main__":
    main()
