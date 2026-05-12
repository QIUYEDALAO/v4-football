from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"

from engine.team_cn_map import MAP_PATH, TEAM_CN_MAP, strict_match


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _session_date(now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now()
    if now.hour < 6:
        now = now - timedelta(days=1)
    return now.strftime("%Y%m%d")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _is_unmapped_team(name: str) -> bool:
    n = str(name or "").strip()
    if not n:
        return False
    # already Chinese label, not candidate for EN->CN mapping
    if _has_cjk(n):
        return False
    # already mapped directly
    if n in TEAM_CN_MAP:
        return False
    # strict map can resolve aliases/case/normalized names
    if strict_match(n) != n:
        return False
    return True


def _collect_names_from_file(path: Path) -> list[tuple[str, str]]:
    rows = _load_json(path, [])
    out: list[tuple[str, str]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in ("home", "away", "home_team", "away_team", "homeEn", "awayEn"):
            n = row.get(field)
            if isinstance(n, str) and n.strip():
                out.append((n.strip(), path.name))
    return out


def _collect_names_from_tasks(path: Path) -> list[tuple[str, str]]:
    obj = _load_json(path, {})
    out: list[tuple[str, str]] = []
    tasks = obj.get("tasks", []) if isinstance(obj, dict) else []
    if not isinstance(tasks, list):
        return out
    for row in tasks:
        if not isinstance(row, dict):
            continue
        for field in ("home", "away", "home_team", "away_team"):
            n = row.get(field)
            if isinstance(n, str) and n.strip():
                out.append((n.strip(), path.name))
    return out


def _collect_names_from_jsonl(path: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    rows = _read_jsonl(path)
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in ("home_team", "away_team", "home", "away"):
            n = row.get(field)
            if isinstance(n, str) and n.strip():
                out.append((n.strip(), path.name))
    return out


def build_daily_unmapped_report(date_str: str) -> dict:
    key = _date_key(date_str)
    day_snap_dir = SNAP_DIR / key
    inputs = [
        REPORT_DIR / f"scout_v4_{key}.json",
        REPORT_DIR / f"live_watchlist_{key}.json",
        MONITOR_DIR / f"v4_capture_tasks_{key}.json",
        day_snap_dir / "live_odds_raw.jsonl",
        day_snap_dir / "live_odds_normalized.jsonl",
    ]

    found: dict[str, dict] = {}

    def add_name(name: str, source: str) -> None:
        if not _is_unmapped_team(name):
            return
        rec = found.setdefault(name, {"name": name, "count": 0, "sources": set()})
        rec["count"] += 1
        rec["sources"].add(source)

    for path in inputs:
        if not path.exists():
            continue
        if path.suffix == ".jsonl":
            pairs = _collect_names_from_jsonl(path)
        elif path.name.startswith("v4_capture_tasks_"):
            pairs = _collect_names_from_tasks(path)
        else:
            pairs = _collect_names_from_file(path)
        for name, source in pairs:
            add_name(name, source)

    items = [
        {"name": v["name"], "count": int(v["count"]), "sources": sorted(v["sources"])}
        for v in found.values()
    ]
    items.sort(key=lambda x: (-x["count"], x["name"]))

    report = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "unmapped_count": len(items),
        "unmapped_teams": items,
        "input_files": [str(p) for p in inputs if p.exists()],
    }
    return report


def update_pending_map(report: dict) -> dict:
    map_path = Path(MAP_PATH)
    existing = _load_json(map_path, {"exact": TEAM_CN_MAP, "unknown": []})
    old = {}
    for item in existing.get("unknown", []) if isinstance(existing, dict) else []:
        if isinstance(item, dict) and item.get("name"):
            old[str(item["name"])] = dict(item)

    for item in report.get("unmapped_teams", []):
        name = str(item.get("name") or "")
        if not name:
            continue
        prev = old.get(name, {})
        prev_count = int(prev.get("count", 0) or 0)
        new_count = int(item.get("count", 0) or 0)
        old[name] = {
            "name": name,
            "count": max(prev_count, new_count),
            "sources": sorted(set((prev.get("sources") or []) + (item.get("sources") or []))),
            "last_seen_date": report.get("date"),
        }

    merged_unknown = sorted(old.values(), key=lambda x: (-int(x.get("count", 0)), x.get("name", "")))
    out_obj = {
        "exact": (existing.get("exact") if isinstance(existing, dict) else None) or TEAM_CN_MAP,
        "unknown": merged_unknown,
        "updated_at": datetime.now().isoformat(),
        "note": "unknown 为待人工补充的英文队名；请把确认后的映射补到 exact。",
    }
    map_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"map_path": str(map_path), "unknown_count": len(merged_unknown)}


def run(date_str: str, update_map: bool = True) -> dict:
    key = _date_key(date_str)
    report = build_daily_unmapped_report(key)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / f"team_cn_unmapped_{key}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        **report,
        "report_path": str(out_path),
    }
    if update_map:
        result["map_update"] = update_pending_map(report)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=_session_date(), help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--no-update-map", action="store_true", help="仅生成日报，不写回 team_cn_map.json")
    args = parser.parse_args()
    result = run(args.date, update_map=not args.no_update_map)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
