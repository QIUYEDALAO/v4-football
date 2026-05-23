#!/usr/bin/env python3
"""Resolve the daily V4 formal brief into a dashboard candidate view.

The resolver reads the formal brief for display categories only. It does not
recompute grades, hit rates, or strategy decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "data/daily_reports"
STATUS = ROOT / "data/runtime/status"
TEAM_CN_MAP = ROOT / "engine/team_cn_map.json"
TZ = timezone(timedelta(hours=8))

# Display-only supplemental names for current brief entries missing from the map.
SUPPLEMENTAL_CN = {
    "V-varen Nagasaki": "长崎航海",
    "Karviná": "卡尔维纳",
    "Persepam Madura Utd": "马都拉联",
    "PSM Makassar": "望加锡",
    "Kalmar FF": "卡尔马",
    "Degerfors IF": "代格福什",
    "KuPS": "古比斯",
    "Lahti": "拉赫蒂",
    "Lommel United": "洛默尔联",
    "Dinamo Zagreb": "萨格勒布迪纳摩",
    "NK Lokomotiva Zagreb": "萨格勒布火车头",
    "Haras El Hodood": "哈拉斯胡杜德",
    "Petrojet": "佩特罗杰特",
    "Cerro Largo": "塞罗拉戈",
    "Boston River": "波士顿河",
    "Fagiano Okayama": "冈山绿雉",
    "Kashima": "鹿岛鹿角",
    "FC Tokyo": "东京足球会",
    "FC东京": "东京足球会",
    "Mlada Boleslav": "姆拉达博莱斯拉夫",
    "Teplice": "特普利采",
    "Dinamo Makhachkala": "马哈奇卡拉迪纳摩",
    "Ilves": "埃尔维斯",
    "Gnistan": "格尼斯坦",
    "Mirassol": "米拉索尔",
    "Fluminense": "弗鲁米嫩塞",
    "Charlotte": "夏洛特",
    "New England Revolution": "新英格兰革命",
}

GRADE_HEADERS = {
    "A": "🔥 A级上半场强推荐",
    "B": "🟢 B级上半场达标推荐",
}
C_HEADER = "👁️ C级观察池"
SKIP_HEADER = "⚪ 跳过统计"


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_team_map() -> dict[str, str]:
    raw = load_json(TEAM_CN_MAP) or {}
    exact = raw.get("exact") if isinstance(raw, dict) else {}
    result = exact if isinstance(exact, dict) else {}
    result = dict(result)
    result.update(SUPPLEMENTAL_CN)
    return result

TEAM_MAP = load_team_map()


def cn(name: str) -> tuple[str, str | None]:
    name = name.strip()
    mapped = TEAM_MAP.get(name)
    return (mapped or name, name if mapped and mapped != name else None)


def sha(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_overview(text: str) -> dict[str, int]:
    patterns = {
        "A": r"A级强推荐：(?P<n>\d+)场",
        "B": r"B级达标推荐：(?P<n>\d+)场",
        "C": r"C级观察：(?P<n>\d+)场",
        "SKIP": r"HT_SKIP跳过：(?P<n>\d+)场|跳过：(?P<n2>\d+)场",
        "scan_total": r"全量扫描：(?P<n>\d+)场",
    }
    out: dict[str, int] = {}
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            value = m.groupdict().get("n") or m.groupdict().get("n2")
            out[key] = int(value)
    return out


def split_blocks(text: str, header: str) -> list[str]:
    pieces = text.split(header)
    blocks = []
    for piece in pieces[1:]:
        block = piece.split("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", 1)[0]
        if block.strip():
            blocks.append(block.strip())
    return blocks


def parse_ab_block(block: str, grade: str, idx: int, scout_by_fixture: dict[int, dict[str, Any]]) -> dict[str, Any]:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    title = lines[0]
    home, away = [part.strip() for part in title.split(" vs ", 1)] if " vs " in title else (title, "UNKNOWN")
    meta = lines[1] if len(lines) > 1 else ""
    parts = [p.strip() for p in meta.split("·")]
    league = parts[0] if parts else "UNKNOWN"
    kickoff_display = parts[1] if len(parts) > 1 else "TBD"
    fixture_match = re.search(r"#(\d+)", meta)
    fixture_id = int(fixture_match.group(1)) if fixture_match else None
    score_line = next((ln for ln in lines if ln.startswith("HT评分")), "")
    score_match = re.search(r"HT评分\s*(\d+).*?HT有球率\s*([\d.]+%).*?场均HT进球\s*([\d.]+).*?样本\s*(\d+)", score_line)
    script_line = next((ln for ln in lines if ln.startswith("剧本：")), "")
    dist_line = next((ln for ln in lines if ln.startswith("分布：")), "")
    risk_line = next((ln for ln in lines if ln.startswith("风险：")), "")
    source = scout_by_fixture.get(fixture_id or -1, {})
    home_cn, home_en = cn(home)
    away_cn, away_en = cn(away)
    return {
        "index": idx,
        "fixture_id": fixture_id,
        "home": home,
        "away": away,
        "home_cn": home_cn,
        "away_cn": away_cn,
        "home_en": home_en,
        "away_en": away_en,
        "league": league,
        "kickoff_display": kickoff_display,
        "ht_score": int(score_match.group(1)) if score_match else None,
        "ht_rate": score_match.group(2) if score_match else None,
        "expected_goals": f"{score_match.group(3)}球" if score_match else "-",
        "sample_size": int(score_match.group(4)) if score_match else None,
        "script_type": script_line.replace("剧本：", "") if script_line else "待识别",
        "distribution_text": dist_line.replace("分布：", "") if dist_line else "time_bins 待补齐",
        "risk": risk_line.replace("风险：", "") if risk_line else "-",
        "grade": grade,
        "recommendation_status": "brief_formal_display_only",
        "source": "data/daily_reports/v4_openclaw_brief_20260523.txt",
        "scout_fixture_found": bool(source),
    }


def parse_c_items(text: str, scout_by_fixture: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    if C_HEADER not in text:
        return []
    section = text.split(C_HEADER, 1)[1].split("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", 1)[0]
    items = []
    for idx, line in enumerate([ln.strip() for ln in section.splitlines() if " vs " in ln], 1):
        title, _, rest = line.partition(" — ")
        home, away = [part.strip() for part in title.split(" vs ", 1)]
        meta_parts = [p.strip() for p in rest.split("|")]
        left = meta_parts[0] if meta_parts else ""
        league_time = left.split()
        league = league_time[0] if league_time else "UNKNOWN"
        kickoff_display = " ".join(league_time[1:]) if len(league_time) > 1 else "TBD"
        ht = meta_parts[1].replace("HT", "").strip() if len(meta_parts) > 1 else None
        rate = meta_parts[2].strip() if len(meta_parts) > 2 else None
        script = meta_parts[3].strip() if len(meta_parts) > 3 else "待识别"
        home_cn, home_en = cn(home)
        away_cn, away_en = cn(away)
        items.append({
            "index": idx,
            "home": home,
            "away": away,
            "home_cn": home_cn,
            "away_cn": away_cn,
            "home_en": home_en,
            "away_en": away_en,
            "league": league,
            "kickoff_display": kickoff_display,
            "ht_score": int(ht) if ht and ht.isdigit() else ht,
            "ht_rate": rate,
            "expected_goals": "观察",
            "script_type": script,
            "distribution_text": "C观察：time_bins 见技术血缘",
            "risk": "仅观察，不是推荐",
            "grade": "C",
            "recommendation_status": "brief_observation_only",
            "source": "data/daily_reports/v4_openclaw_brief_20260523.txt",
        })
    return items


def build_candidate_view(date: str, text: str, brief_path: Path, scout_path: Path | None) -> dict[str, Any]:
    scout = load_json(scout_path) if scout_path else []
    scout_by_fixture = {int(item.get("fixture_id")): item for item in scout if isinstance(item, dict) and item.get("fixture_id")} if isinstance(scout, list) else {}
    overview = parse_overview(text)
    a_items = [parse_ab_block(block, "A", i, scout_by_fixture) for i, block in enumerate(split_blocks(text, GRADE_HEADERS["A"]), 1)]
    b_items = [parse_ab_block(block, "B", i, scout_by_fixture) for i, block in enumerate(split_blocks(text, GRADE_HEADERS["B"]), 1)]
    c_items = parse_c_items(text, scout_by_fixture)
    return {
        "schema_version": "v3v4_dashboard_brief_candidate_view.v1",
        "generated_at": datetime.now(TZ).isoformat(),
        "scan_date": date,
        "source_window": "daily_1200",
        "source_path": str(brief_path.relative_to(ROOT)),
        "source_hash": sha(brief_path),
        "brief_path": str(brief_path.relative_to(ROOT)),
        "brief_sha256": sha(brief_path),
        "scout_path": str(scout_path.relative_to(ROOT)) if scout_path else None,
        "scout_sha256": sha(scout_path),
        "A_count": overview.get("A", len(a_items)),
        "B_count": overview.get("B", len(b_items)),
        "C_count": overview.get("C", len(c_items)),
        "SKIP_count": overview.get("SKIP", 0),
        "scan_total": overview.get("scan_total", overview.get("A", len(a_items)) + overview.get("B", len(b_items)) + overview.get("C", len(c_items)) + overview.get("SKIP", 0)),
        "formal_recommendation_count": overview.get("A", len(a_items)) + overview.get("B", len(b_items)),
        "A_candidates": a_items,
        "A_candidate": a_items[0] if a_items else None,
        "B_candidates": b_items,
        "C_candidates": c_items,
        "C_observation_only": True,
        "actual_send": False,
        "qq_sent": False,
        "V4_QQ_ENABLED": False,
        "parsed_from_brief": True,
        "fallback_used": False,
        "fallback_reason": None,
        "builder_script": "tools/v3v4_dashboard_brief_resolver.py",
    }


def resolve(date: str, *, write: bool = True) -> dict[str, Any]:
    brief_path = DAILY / f"v4_openclaw_brief_{date}.txt"
    scout_path = DAILY / f"scout_v4_{date}.json"
    brief_exists = brief_path.exists()
    if not brief_exists:
        result = {
            "date": date,
            "brief_path": str(brief_path.relative_to(ROOT)),
            "brief_exists": False,
            "brief_sha256": None,
            "brief_size": 0,
            "source_date": None,
            "is_today_brief": False,
            "candidate_counts": {},
            "A": 0,
            "B": 0,
            "C": 0,
            "SKIP": 0,
            "formal_count": 0,
            "window": "daily_1200",
            "parsed_from_brief": False,
            "fallback_used": False,
            "fallback_reason": "brief_missing",
            "blocker": True,
        }
    else:
        text = brief_path.read_text(encoding="utf-8")
        view = build_candidate_view(date, text, brief_path, scout_path if scout_path.exists() else None)
        counts = {k: view[f"{k}_count"] for k in ["A", "B", "C", "SKIP"]}
        result = {
            "schema_version": "v3v4_dashboard_brief_resolution.v1",
            "phase": "V3V4-DASHBOARD-BRIEF-VALIDATION-AUTO-REFRESH-20260523",
            "generated_at": datetime.now(TZ).isoformat(),
            "date": date,
            "brief_path": str(brief_path.relative_to(ROOT)),
            "brief_exists": True,
            "brief_sha256": sha(brief_path),
            "brief_size": brief_path.stat().st_size,
            "source_date": date,
            "is_today_brief": date == "20260523",
            "candidate_counts": counts,
            "A": counts["A"],
            "B": counts["B"],
            "C": counts["C"],
            "SKIP": counts["SKIP"],
            "formal_count": view["formal_recommendation_count"],
            "window": "daily_1200",
            "parsed_from_brief": True,
            "fallback_used": False,
            "fallback_reason": None,
            "candidate_view": view,
            "brief_used_for_hit_rate": False,
            "capture_ran": False,
            "QQ_push": False,
            "cloud_publish": False,
        }
        if write:
            out_view = STATUS / f"v3v4_dashboard_candidate_view_{date}.json"
            out_view.write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
    if write:
        out = STATUS / f"v3v4_dashboard_brief_resolution_{date}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260523")
    args = parser.parse_args()
    result = resolve(args.date, write=True)
    printable = dict(result)
    printable.pop("candidate_view", None)
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 1 if result.get("blocker") else 0


if __name__ == "__main__":
    raise SystemExit(main())
