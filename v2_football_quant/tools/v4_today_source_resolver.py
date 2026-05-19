#!/usr/bin/env python3
"""V4 Today Source Resolver — reads real V4 scan output, never hardcodes"""
import argparse, json, os, re, sys, time
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
                    data = json.loads(fp.read_text())
                    # Extract grade counts
                    grades = {}
                    for m in (data if isinstance(data, list) else data.get("matches", [])):
                        g = m.get("grade", m.get("pre_grade", m.get("ht_recommendation", "")))
                        grades[g] = grades.get(g, 0) + 1
                    result["A_count"] = grades.get("A", 0)
                    result["B_count"] = grades.get("B", 0)
                    result["C_count"] = grades.get("C", 0)
                    result["SKIP_count"] = grades.get("SKIP", 0) + grades.get("HT_SKIP", 0)
                    result["total_matches"] = sum(grades.values())
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
