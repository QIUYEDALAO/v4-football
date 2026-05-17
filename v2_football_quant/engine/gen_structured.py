#!/usr/bin/env python3
"""engine/gen_structured.py — 从验证文件+API生成 v4_review_structured_YYYYMMDD.json

读取 v4_ht_recommend_validation_YYYYMMDD.json（含全部A/B/C/SKIP场次），
调用API获取HT/FT比分和进球分钟，构建完整的结构化复盘文件。

允许缺失：
- 赛前评分 → 数据缺失
- HT率 → 数据缺失
- 场均HT → 数据缺失
- 剧本 → 剧本未存档
- 天气 → 天气数据缺失
- 赛中快照 → 快照数据缺失
- script_check/risk_review → 剧本未存档/风险数据未存档

用法:
  python3 engine/gen_structured.py --date 20260516
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"


def _safe_int(v, default=0):
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _min_to_bucket(m):
    if m <= 15:
        return "0_15"
    elif m <= 30:
        return "16_30"
    else:
        return "31_45"


def _process_fixture(fid: int, validation_record: dict) -> dict:
    """Process a single fixture via API for scores + events."""
    ht_score = "DATA_UNAVAILABLE"
    ft_score = "DATA_UNAVAILABLE"
    ht_goals = _safe_int(validation_record.get("ht_goals", 0))
    ht_goal_minutes = []
    goals_0_15 = 0
    goals_16_30 = 0
    goals_31_45 = 0
    first_goal_bucket = ""
    data_source = "DATA_UNAVAILABLE"
    home = validation_record.get("home", "?")
    away = validation_record.get("away", "?")
    league = validation_record.get("league", "?")
    grade = validation_record.get("grade", "?")
    kickoff = validation_record.get("kickoff", "DATA_UNAVAILABLE")
    status = validation_record.get("status", "")
    hit = validation_record.get("hit", False)

    # Step 1: Get fixture data (for HT/FT scores)
    try:
        resp = net_utils.api_get(f"fixtures?id={fid}")
        rows = resp.get("response", []) if resp else []
        if rows:
            f_data = rows[0]
            score = f_data.get("score", {})
            ht = score.get("halftime", {})
            ft = score.get("fulltime", {})
            ht_home = ht.get("home", "?")
            ht_away = ht.get("away", "?")
            ft_home = ft.get("home", "?")
            ft_away = ft.get("away", "?")
            if str(ht_home).isdigit() and str(ht_away).isdigit():
                ht_score = f"{ht_home}-{ht_away}"
            if str(ft_home).isdigit() and str(ft_away).isdigit():
                ft_score = f"{ft_home}-{ft_away}"
            data_source = "API_FIXTURES"
            # Update names from API if available
            teams = f_data.get("teams", {})
            if teams:
                home = teams.get("home", {}).get("name", home)
                away = teams.get("away", {}).get("name", away)
            lg = f_data.get("league", {})
            if lg:
                league = lg.get("name", league)
            fix = f_data.get("fixture", {})
            if fix:
                kickoff = fix.get("date", kickoff)
    except Exception:
        pass

    # Step 2: Get events for goal minutes
    try:
        ev_resp = net_utils.api_get(f"fixtures/events?fixture={fid}")
        ev_rows = ev_resp.get("response", []) if ev_resp else []
        for ev in ev_rows:
            etype = str(ev.get("type", "")).strip().lower()
            detail = str(ev.get("detail", "")).strip().lower()
            if etype == "goal" and detail in ("normal goal", "own goal", "penalty"):
                elapsed = (ev.get("time") or {}).get("elapsed")
                if elapsed:
                    m = int(elapsed)
                    if m <= 45:
                        ht_goal_minutes.append(m)
                        bucket = _min_to_bucket(m)
                        if bucket == "0_15":
                            goals_0_15 += 1
                        elif bucket == "16_30":
                            goals_16_30 += 1
                        else:
                            goals_31_45 += 1
        if data_source != "DATA_UNAVAILABLE":
            data_source = "API_HALFTIME_SCORE+API_EVENTS"
    except Exception:
        pass

    if ht_goal_minutes:
        first = min(ht_goal_minutes)
        first_goal_bucket = _min_to_bucket(first)

    # Derive model_result and diagnosis
    if grade in ("A", "B"):
        if ht_goals > 0 or len(ht_goal_minutes) > 0:
            model_result = f"{grade}_HIT"
            diagnosis = "MODEL_VALID"
        else:
            model_result = f"{grade}_MISS"
            diagnosis = "MODEL_OVERCONFIDENT"
    elif grade == "C":
        if ht_goals > 0 or len(ht_goal_minutes) > 0:
            model_result = "C_HIT"
            diagnosis = "MODEL_VALID"
        else:
            model_result = "C_MISS"
            diagnosis = "MODEL_TOO_STRICT"
    else:  # SKIP
        if ht_goals > 0 or len(ht_goal_minutes) > 0:
            model_result = "SKIP_BACKFIRE"
            diagnosis = "MODEL_TOO_STRICT"
        else:
            model_result = "SKIP_CORRECT"
            diagnosis = "MODEL_VALID"

    # Check for noisy wins
    if model_result in ("A_HIT", "B_HIT", "C_HIT") and ht_goal_minutes:
        # Check if all goals were penalties
        pk_only = True
        try:
            ev_resp2 = net_utils.api_get(f"fixtures/events?fixture={fid}")
            ev_rows2 = ev_resp2.get("response", []) if ev_resp2 else []
            for ev in ev_rows2:
                etype = str(ev.get("type", "")).strip().lower()
                detail = str(ev.get("detail", "")).strip().lower()
                elapsed = (ev.get("time") or {}).get("elapsed", 0)
                if etype == "goal" and elapsed <= 45 and detail != "penalty":
                    pk_only = False
                    break
        except Exception:
            pass
        if pk_only:
            diagnosis = "NOISY_WIN"

    match = {
        "fixture_id": fid,
        "home": home,
        "away": away,
        "league": league,
        "kickoff_time": kickoff,
        "official_bucket": grade,
        "ht_score": ht_score,
        "ft_score": ft_score,
        "ht_score_value": ht_goals,
        "avg_ht_goals": "DATA_UNAVAILABLE",
        "ht_goal_rate": "DATA_UNAVAILABLE",
        "h2h_sample": 0,
        "first_half_goal_minutes": sorted(ht_goal_minutes),
        "goals_0_15": goals_0_15,
        "goals_16_30": goals_16_30,
        "goals_31_45": goals_31_45,
        "first_goal_bucket": first_goal_bucket,
        "model_result": model_result,
        "diagnosis": diagnosis,
        "data_source": data_source,
        "weather_context": {
            "weather_source": "DATA_UNAVAILABLE",
            "weather_risk_level": "UNKNOWN",
            "weather_note": "天气数据缺失，不参与归因"
        },
        "market_line": "DATA_UNAVAILABLE",
        "market_odds": "DATA_UNAVAILABLE",
        "script_type": "SCRIPT_NOT_AVAILABLE",
        "script_distribution": {
            "0_15": None,
            "16_30": None,
            "31_45": None
        },
        "script_check": "SCRIPT_NOT_AVAILABLE",
        "script_bias": "SCRIPT_NOT_AVAILABLE",
        "script_note": "赛前剧本数据未存档",
        "risk_review": "风险数据未存档",
        "risk_flags": [],
    }
    return match


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    key = str(args.date).replace("-", "")
    val_path = REPORT_DIR / f"v4_ht_recommend_validation_{key}.json"

    if not val_path.exists():
        print(f"[GEN] ERROR: validation file not found: {val_path}", flush=True)
        sys.exit(1)

    with open(val_path) as f:
        val_data = json.load(f)

    details = val_data.get("details", [])
    grade_counts = val_data.get("grade_counts", val_data.get("funnel", {}))
    total = len(details)

    print(f"[GEN] Validation: {total} fixtures", flush=True)

    # Process all fixtures via API
    matches = []
    for i, d in enumerate(details):
        fid = _safe_int(d.get("fixture_id", 0))
        if not fid:
            print(f"[GEN] WARNING: record {i} has no fixture_id", flush=True)
            continue
        match = _process_fixture(fid, d)
        matches.append(match)
        if (i + 1) % 10 == 0:
            print(f"[GEN] Progress: {i+1}/{total}", flush=True)
        time.sleep(0.12)  # Rate limit ~8 req/s

    print(f"[GEN] Processed {len(matches)}/{total} fixtures", flush=True)

    # ── Compute summaries ──
    a_matches = [m for m in matches if m["official_bucket"] == "A"]
    b_matches = [m for m in matches if m["official_bucket"] == "B"]
    c_matches = [m for m in matches if m["official_bucket"] == "C"]
    s_matches = [m for m in matches if m["official_bucket"] == "SKIP"]

    a_hits = sum(1 for m in a_matches if m["model_result"] in ("A_HIT",))
    b_hits = sum(1 for m in b_matches if m["model_result"] in ("B_HIT",))
    c_hits = sum(1 for m in c_matches if m["model_result"] in ("C_HIT", "NOISY_WIN"))
    c_total = len(c_matches)
    s_backfire = sum(1 for m in s_matches if m["model_result"] == "SKIP_BACKFIRE")
    s_total = len(s_matches)
    s_correct = s_total - s_backfire

    a_rate = f"{a_hits}/{len(a_matches)}" if a_matches else "N/A"
    b_rate = f"{b_hits}/{len(b_matches)}" if b_matches else "N/A"
    c_rate = f"{c_hits}/{c_total}" if c_total > 0 else "N/A"

    # ── Time distribution ──
    all_ht_goal_minutes_sorted = sorted(sum((m["first_half_goal_minutes"] for m in matches), []))
    total_ht_goals = len(all_ht_goal_minutes_sorted)
    g0_15_count = sum(1 for g in all_ht_goal_minutes_sorted if g <= 15)
    g16_30_count = sum(1 for g in all_ht_goal_minutes_sorted if 16 <= g <= 30)
    g31_45_count = sum(1 for g in all_ht_goal_minutes_sorted if 31 <= g <= 45)

    g0_15_minutes = "、".join(f"{g}′" for g in all_ht_goal_minutes_sorted if g <= 15)
    g16_30_minutes = "、".join(f"{g}′" for g in all_ht_goal_minutes_sorted if 16 <= g <= 30)
    g31_45_minutes = "、".join(f"{g}′" for g in all_ht_goal_minutes_sorted if 31 <= g <= 45)

    first_goals = Counter()
    no_goal = 0
    for m in matches:
        fg = m.get("first_goal_bucket", "")
        if fg:
            first_goals[fg] += 1
        else:
            no_goal += 1

    # ── Diagnosis summary ──
    diag_counter = Counter(m["diagnosis"] for m in matches)

    # ── Rolling stats ──
    ab_total = len(a_matches) + len(b_matches)
    ab_hits = a_hits + b_hits
    rolling_7d_ab = f"{ab_hits}/{ab_total}" if ab_total > 0 else "N/A"
    rolling_7d_c = f"{c_hits}/{c_total}" if c_total > 0 else "N/A"
    rolling_7d_skip = f"{s_backfire}/{s_total}" if s_total > 0 else "N/A"

    # ── Diagnosis note ──
    diag_note_parts = []
    if diag_counter.get("MODEL_OVERCONFIDENT", 0) > 0:
        diag_note_parts.append(f"模型过度自信{diag_counter['MODEL_OVERCONFIDENT']}场")
    if diag_counter.get("MODEL_TOO_STRICT", 0) > 0:
        diag_note_parts.append(f"模型过严{diag_counter['MODEL_TOO_STRICT']}场")
    if diag_counter.get("NOISY_WIN", 0) > 0:
        diag_note_parts.append(f"噪音命中{diag_counter['NOISY_WIN']}场")
    diag_note = "；".join(diag_note_parts) if diag_note_parts else "所有样本正常"

    # ── Summary note ──
    summary_note = f"A={a_rate} B={b_rate} C={c_rate} SKIP反杀{s_backfire}/{s_total}"

    # ── Build structured JSON ──
    structured = {
        "review_date": args.date,
        "official_source": f"v4_ht_recommend_validation_{key}.json",
        "official_counts": {
            "A": len(a_matches),
            "B": len(b_matches),
            "C": len(c_matches),
            "SKIP": len(s_matches),
        },
        "matches": matches,
        "summary": {
            "a": {"hit": a_hits, "total": len(a_matches), "rate": a_rate},
            "b": {"hit": b_hits, "total": len(b_matches), "rate": b_rate},
            "c": {"hit": c_hits, "total": len(c_matches), "rate": c_rate if c_total > 0 else "N/A"},
            "skip_correct": s_correct,
            "skip_total": s_total,
            "skip_backfire": s_backfire,
            "skip_backfire_rate": f"{s_backfire}/{s_total}" if s_total > 0 else "N/A",
        },
        "time_distribution": {
            "sample_count": len(matches),
            "ht_goal_total": total_ht_goals,
            "goals_0_15": {"count": g0_15_count, "minutes": g0_15_minutes},
            "goals_16_30": {"count": g16_30_count, "minutes": g16_30_minutes},
            "goals_31_45": {"count": g31_45_count, "minutes": g31_45_minutes},
            "first_goal": {
                "0_15": first_goals.get("0_15", 0),
                "16_30": first_goals.get("16_30", 0),
                "31_45": first_goals.get("31_45", 0),
                "none": no_goal,
            },
        },
        "diagnosis_summary": dict(diag_counter),
        "diagnosis_summary_cn": {
            "labels": ["模型有效", "模型过严", "模型过度自信", "噪音命中", "噪音失败", "数据质量问题", "天气风险"],
            "values": [
                diag_counter.get("MODEL_VALID", 0),
                diag_counter.get("MODEL_TOO_STRICT", 0),
                diag_counter.get("MODEL_OVERCONFIDENT", 0),
                diag_counter.get("NOISY_WIN", 0),
                diag_counter.get("NOISY_LOSS", 0),
                diag_counter.get("DATA_QUALITY_ISSUE", 0),
                diag_counter.get("WEATHER_RISK", 0),
            ],
            "note": diag_note,
        },
        "rolling_stats": {
            "7d_ab": rolling_7d_ab,
            "7d_c": rolling_7d_c,
            "7d_skip_backfire": rolling_7d_skip,
            "7d_script": "样本不足，仅观察",
            "14d_summary": "样本不足，仅观察",
            "30d_summary": "样本不足，仅观察",
            "cumulative": "样本不足，仅观察",
        },
        "rolling_source_files": f"v4_ht_recommend_validation_{key}.json",
        "script_validation": {
            "script_hit": 0,
            "script_partial": 0,
            "script_miss": 0,
            "no_ht_goal": 0,
            "script_na": total,
            "matched_count": 0,
            "earlier_than_expected": 0,
            "later_than_expected": 0,
            "too_strict_script": 0,
            "script_no_data": total,
            "note": f"全部{total}场赛前剧本数据未存档，不参与验证",
        },
        "script_validation_cn": {
            "labels": ["剧本命中", "部分命中", "剧本偏差", "无HT球可验证", "剧本未存档"],
            "values": [0, 0, 0, 0, total],
            "deviation_labels": ["符合", "偏早", "偏晚", "过严", "无数据"],
            "deviation_values": [0, 0, 0, 0, total],
            "note": f"全部{total}场赛前剧本数据未存档，不参与验证",
        },
        "pre_match_signal": {
            "ab_sample_count": ab_total,
            "avg_ht_score": "N/A（数据缺失）",
            "avg_ht_goal_rate": "N/A（数据缺失）",
            "avg_avg_ht_goals": "N/A（数据缺失）",
            "market_support_count": 0,
            "fulltime_stronger_count": 0,
            "risk_validated_count": 0,
            "note": "赛前信号数据未存档",
        },
        "diagnosis_note": diag_note,
        "daily_summary_note": summary_note,
        "recommendation_summary": f"A级{len(a_matches)}场 + B级{len(b_matches)}场" if ab_total > 0 else "今日 V4 无A/B上半场主推荐",
    }

    out_path = REPORT_DIR / f"v4_review_structured_{key}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)

    print(f"[GEN] ✅ Written: {out_path}", flush=True)
    print(f"[GEN] A={a_hits}/{len(a_matches)} B={b_hits}/{len(b_matches)} C={c_hits}/{c_total} SKIP={s_backfire}/{s_total}", flush=True)
    print(f"[GEN] Total matches: {len(matches)} (expected {total})", flush=True)


if __name__ == "__main__":
    main()
