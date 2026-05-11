"""
中文队名缺失收集器
==================
扫描 V4 日报，把 fuzzy_match 后仍然等于原文的球队写入 team_cn_map.json 的 unknown。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.team_cn_map import MAP_PATH, TEAM_CN_MAP, fuzzy_match

REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _is_unknown(name: str) -> bool:
    if not name:
        return False
    return fuzzy_match(name) == name and name not in TEAM_CN_MAP


def collect_missing(date_str: str | None = None) -> dict:
    files = []
    if date_str:
        key = _date_key(date_str)
        files.extend([
            REPORT_DIR / f"scout_v4_{key}.json",
            REPORT_DIR / f"live_watchlist_{key}.json",
        ])
    else:
        files.extend(sorted(REPORT_DIR.glob("scout_v4_*.json")))
        files.extend(sorted(REPORT_DIR.glob("live_watchlist_*.json")))

    found = {}
    for path in files:
        rows = _load_json(path, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            for field in ("home", "away"):
                name = row.get(field)
                if _is_unknown(name):
                    found.setdefault(name, {"name": name, "count": 0, "sources": set()})
                    found[name]["count"] += 1
                    found[name]["sources"].add(path.name)

    unknown = [
        {"name": v["name"], "count": v["count"], "sources": sorted(v["sources"])}
        for v in found.values()
    ]
    unknown.sort(key=lambda x: (-x["count"], x["name"]))
    return {
        "generated_at": datetime.now().isoformat(),
        "missing_count": len(unknown),
        "unknown": unknown,
    }


def save_missing(date_str: str | None = None) -> dict:
    result = collect_missing(date_str)
    path = Path(MAP_PATH)
    existing = _load_json(path, {"exact": TEAM_CN_MAP, "unknown": []})
    old = {x.get("name"): x for x in existing.get("unknown", []) if isinstance(x, dict)}
    for item in result["unknown"]:
        old[item["name"]] = item
    existing["exact"] = existing.get("exact") or TEAM_CN_MAP
    existing["unknown"] = sorted(old.values(), key=lambda x: (-int(x.get("count", 0)), x.get("name", "")))
    existing["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(path), **result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYYMMDD 或 YYYY-MM-DD；为空则扫描全部 V4 日报")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    result = save_missing(args.date) if args.save else collect_missing(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
