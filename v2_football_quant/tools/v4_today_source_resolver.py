#!/usr/bin/env python3
"""V4 Today Source Resolver — reads real V4 scan output, never hardcodes.

Permanent time_bins extraction with source priority:
  1. factors.recent_time_bins (primary — real historical distribution data)
  2. factors.time_bins (fallback — only if non-zero and complete)
  3. explicit goal_time_distribution (already present in source)
  4. available=false + source_missing_reason (no data)

Hard rules:
  - factors.time_bins all-zero → MUST NOT override recent_time_bins.
  - Every entry with available=false MUST have source_missing_reason.
  - Never derive time distribution from QQ output text.
"""
import argparse, hashlib, json, os, re, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def _parse_brief_text(text):
    """Parse A/B/C/SKIP from V4 brief text."""
    result = {"total": 0, "A": 0, "B": 0, "C": 0, "SKIP": 0,
              "C_list": [], "SKIP_list": [], "A_list": [], "B_list": []}
    # Count from section headers (precise, won't match "A+B=69" etc.)
    for pat, key in [(r'A级强推荐[：:]\s*(\d+)', "A"),
                     (r'A级上半场强推荐[：:]\s*(\d+)', "A"),
                     (r'A[：:]\s*(\d+)\s*场', "A"),
                     (r'B级达标推荐[：:]\s*(\d+)', "B"),
                     (r'B级上半场达标推荐[：:]\s*(\d+)', "B"),
                     (r'B[：:]\s*(\d+)\s*场', "B"),
                     (r'C级观察[池]?[：:]\s*(\d+)', "C"),
                     (r'C[：:]\s*(\d+)\s*场', "C"),
                     (r'(?:HT_SKIP)?跳过[^\d]*(\d+)', "SKIP"),
                     (r'SKIP[：:]\s*(\d+)', "SKIP")]:
        m = re.search(pat, text)
        if m:
            result[key] = max(result[key], int(m.group(1)))
    # Total from "全量扫描" section
    tm = re.search(r'全量扫描[：:]\s*(\d+)', text)
    if tm:
        result["total"] = int(tm.group(1))
    else:
        result["total"] = sum(result[k] for k in ["A","B","C","SKIP"])
    return result

def extract_goal_time_distribution(match: dict, scout_file_path: str) -> dict:
    """Extract goal_time_distribution from a scout_v4 match record with source priority.

    Priority:
      1. factors.recent_time_bins (primary — real historical data)
      2. factors.time_bins (fallback — only if non-zero and all three fields present)
      3. existing goal_time_distribution in match
      4. available=false with source_missing_reason

    Returns dict with: m0_15, m16_30, m31_45, available, source_file, source_field, source_priority, source_missing_reason
    """
    factors = match.get("factors", {}) or {}
    rtb = factors.get("recent_time_bins", {}) or {}
    tb = factors.get("time_bins", {}) or {}
    existing_gtd = match.get("goal_time_distribution", {}) or {}

    # Priority 1: factors.recent_time_bins
    rtb_vals = {
        "m0_15": rtb.get("0_15") if rtb.get("0_15") is not None else None,
        "m16_30": rtb.get("16_30") if rtb.get("16_30") is not None else None,
        "m31_45": rtb.get("31_45") if rtb.get("31_45") is not None else None,
    }
    rtb_complete = all(v is not None for v in rtb_vals.values())
    rtb_any_nonzero = any(float(v) > 0 for v in rtb_vals.values() if v is not None)

    if rtb_complete and rtb_any_nonzero:
        return {
            "m0_15": round(float(rtb_vals["m0_15"]), 4),
            "m16_30": round(float(rtb_vals["m16_30"]), 4),
            "m31_45": round(float(rtb_vals["m31_45"]), 4),
            "available": True,
            "source_file": scout_file_path,
            "source_field": "factors.recent_time_bins",
            "source_priority": 1,
            "source_missing_reason": None,
        }

    # Priority 2: factors.time_bins (only if non-zero and complete)
    tb_vals = {
        "m0_15": tb.get("0_15") if tb.get("0_15") is not None else None,
        "m16_30": tb.get("16_30") if tb.get("16_30") is not None else None,
        "m31_45": tb.get("31_45") if tb.get("31_45") is not None else None,
    }
    tb_complete = all(v is not None for v in tb_vals.values())
    tb_any_nonzero = any(float(v) > 0 for v in tb_vals.values() if v is not None)
    tb_all_zero = all(float(v) == 0 for v in tb_vals.values() if v is not None)

    if tb_complete and tb_any_nonzero and not tb_all_zero:
        return {
            "m0_15": round(float(tb_vals["m0_15"]), 4),
            "m16_30": round(float(tb_vals["m16_30"]), 4),
            "m31_45": round(float(tb_vals["m31_45"]), 4),
            "available": True,
            "source_file": scout_file_path,
            "source_field": "factors.time_bins",
            "source_priority": 2,
            "source_missing_reason": None,
        }

    # Priority 3: existing goal_time_distribution
    if existing_gtd.get("available"):
        return {
            "m0_15": existing_gtd.get("m0_15"),
            "m16_30": existing_gtd.get("m16_30"),
            "m31_45": existing_gtd.get("m31_45"),
            "available": True,
            "source_file": existing_gtd.get("source_file", scout_file_path),
            "source_field": existing_gtd.get("source_field", "goal_time_distribution"),
            "source_priority": 3,
            "source_missing_reason": None,
        }

    # Priority 4: unavailable — document WHY
    reasons = []
    if not rtb_complete:
        reasons.append("factors.recent_time_bins 不完整或缺失")
    elif not rtb_any_nonzero:
        reasons.append("factors.recent_time_bins 所有字段为0")
    if tb_all_zero:
        reasons.append("factors.time_bins 所有字段为0（未来比赛无历史数据）")
    elif not tb_complete:
        reasons.append("factors.time_bins 不完整")

    return {
        "m0_15": None,
        "m16_30": None,
        "m31_45": None,
        "available": False,
        "source_file": scout_file_path,
        "source_field": None,
        "source_priority": 4,
        "source_missing_reason": "; ".join(reasons) if reasons else "无可用时间段分布数据",
    }


def extract_candidate_entries(scout_data: list, scout_file_path: str) -> list:
    """Extract candidate-level entries from scout_v4 JSON with goal_time_distribution.

    Each entry includes: fixture_id, home, away, league, kickoff_time, match_date,
    market_focus, market_type, ht_score, best_score, best_focus_by_score,
    goal_time_distribution (with source tracing), grade.
    """
    entries = []
    for m in scout_data:
        if not isinstance(m, dict):
            continue
        gtd = extract_goal_time_distribution(m, scout_file_path)
        factors = m.get("factors", {}) or {}
        entry = {
            "fixture_id": m.get("fixture_id"),
            "home": m.get("home"),
            "away": m.get("away"),
            "league": m.get("league"),
            "kickoff_time": m.get("kickoff"),
            "match_date": m.get("match_date") or m.get("date"),
            "market_focus": m.get("market_focus"),
            "market_type": m.get("market_type"),
            "ht_score": factors.get("ht_score"),
            "best_score": m.get("best_score"),
            "best_focus_by_score": m.get("best_focus_by_score"),
            "grade": m.get("grade") or m.get("pre_grade") or m.get("ht_recommendation", ""),
            "goal_time_distribution": gtd,
        }
        entries.append(entry)
    return entries


def resolve(args):
    dt = args.date[:10].replace("/", "-")
    dt_compact = dt.replace("-", "")
    result = {"status": "RUNNING", "date": dt, "source_mode": "SOURCE_MISSING",
              "source_file": None, "source_mtime": None, "source_freshness": "MISSING",
              "total_matches": None, "A_count": None, "B_count": None, "C_count": None,
              "SKIP_count": None, "A_B_formal_conclusions": [],
              "C_observation_list": [], "SKIP_list": [],
              "C_observation_only": True, "SKIP_not_recommendation": True,
              "hardcoded": False, "qq_sent": False, "state_written": False,
              "verified_written": False, "proof_executed": False, "blocker_reason": ""}

    # Priority 1: V4 brief files
    for pattern in [f"v4_openclaw_brief_{dt_compact}.txt",
                    f"v4_openclaw_brief_qq_{dt_compact}.txt",
                    f"v4_openclaw_brief_{dt}.txt"]:
        for root in ["data/daily_reports", "reports", "data"]:
            fp = MODULE / root / pattern
            if fp.is_file():
                result["source_mode"] = "PRIMARY_V4_BRIEF"
                result["source_file"] = str(fp.relative_to(MODULE))
                result["source_mtime"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(fp.stat().st_mtime))
                text = fp.read_text()
                parsed = _parse_brief_text(text)
                result["total_matches"] = parsed["total"]
                result["A_count"] = parsed["A"]
                result["B_count"] = parsed["B"]
                result["C_count"] = parsed["C"]
                result["SKIP_count"] = parsed["SKIP"]
                result["source_freshness"] = "FRESH"
                result["status"] = "DONE"
                return result

    # Priority 2: V4 scan scout JSON
    for pattern in [f"scout_v4_{dt_compact}.json", f"scout_v4_{dt}.json"]:
        for root in ["data/daily_reports", "data"]:
            fp = MODULE / root / pattern
            if fp.is_file():
                result["source_mode"] = "PRIMARY_V4_SCOUT"
                result["source_file"] = str(fp.relative_to(MODULE))
                result["source_mtime"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(fp.stat().st_mtime))
                try:
                    raw_bytes = fp.read_bytes()
                    result["source_hash"] = hashlib.md5(raw_bytes).hexdigest()[:12]
                    data = json.loads(raw_bytes.decode())
                    match_list = data if isinstance(data, list) else data.get("matches", [])
                    # Extract grade counts
                    grades = {}
                    for m in match_list:
                        g = m.get("grade", m.get("pre_grade", m.get("ht_recommendation", "")))
                        grades[g] = grades.get(g, 0) + 1
                    result["A_count"] = grades.get("A", 0)
                    result["B_count"] = grades.get("B", 0)
                    result["C_count"] = grades.get("C", 0)
                    result["SKIP_count"] = grades.get("SKIP", 0) + grades.get("HT_SKIP", 0)
                    result["total_matches"] = sum(grades.values())
                    # Extract per-match candidate entries with goal_time_distribution
                    scout_path_str = str(fp.relative_to(MODULE))
                    candidate_entries = extract_candidate_entries(match_list, scout_path_str)
                    result["candidate_entries"] = candidate_entries
                    result["candidate_entry_count"] = len(candidate_entries)
                    result["time_bins_available_count"] = sum(
                        1 for e in candidate_entries
                        if e.get("goal_time_distribution", {}).get("available", False)
                    )
                    result["source_freshness"] = "FRESH"
                    result["status"] = "DONE"
                    return result
                except:
                    pass

    # Priority 3: V4 attribution archive (derived)
    af = MODULE / "data" / "v4_archive" / f"v4_result_attribution_{dt_compact}.jsonl"
    if af.is_file():
        result["source_mode"] = "V4_ATTRIBUTION_DERIVED"
        result["source_file"] = str(af.relative_to(MODULE))
        result["source_mtime"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(af.stat().st_mtime))
        result["source_freshness"] = "FRESH"
        rows = [json.loads(l) for l in af.read_text().split("\n") if l.strip()]
        grades = {}
        for r in rows:
            g = r.get("pre_grade", "")
            grades[g] = grades.get(g, 0) + 1
        result["A_count"] = grades.get("A", 0)
        result["B_count"] = grades.get("B", 0)
        result["C_count"] = grades.get("C", 0)
        result["SKIP_count"] = grades.get("SKIP", 0) + grades.get("HT_SKIP", 0)
        result["total_matches"] = sum(grades.values())
        result["status"] = "DONE"
        return result

    # No source found
    result["status"] = "DEGRADED"
    result["blocker_reason"] = "V4_TODAY_SOURCE_MISSING"
    result["source_freshness"] = "MISSING"
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--no-state-write", action="store_true")
    p.add_argument("--no-verified-write", action="store_true")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()
    r = resolve(args)
    if args.pretty:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(r, ensure_ascii=False))
    return 0 if r["status"] != "BLOCKER" else 1

if __name__ == "__main__":
    sys.exit(main())
