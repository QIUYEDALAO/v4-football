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
from team_cn_resolver import TeamCnResolver

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

GRADE_HEADER_RE = re.compile(
    r"^[^\n]*?(?P<grade>[AB])级(?:上半场)?(?:强推荐|达标推荐)(?:[：:](?:无|\(无\)))?\s*$",
    re.MULTILINE,
)
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
CN_RESOLVER = TeamCnResolver()


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
        "A": r"A级(?:上半场)?强推荐[：:](?P<n>\d+)场",
        "B": r"B级(?:上半场)?达标推荐[：:](?P<n>\d+)场",
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


def split_grade_blocks(text: str, grade: str) -> list[str]:
    blocks: list[str] = []
    matches = list(GRADE_HEADER_RE.finditer(text))
    for idx, match in enumerate(matches):
        if match.group("grade") != grade:
            continue
        start = match.end()
        next_header = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        next_rule = text.find("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", start)
        end = min([x for x in [next_header, next_rule if next_rule != -1 else None] if x is not None])
        section = text[start:end].strip()
        if section and section not in {"(无)", "无", "：(无)"}:
            blocks.append(section)
    return blocks


def _norm_team(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip()).casefold()


def _find_scout_match(home: str, away: str, scout_by_fixture: dict[int, dict[str, Any]]) -> dict[str, Any]:
    home_key = _norm_team(home)
    away_key = _norm_team(away)
    for row in scout_by_fixture.values():
        row_home = _norm_team(row.get("home") or row.get("home_team"))
        row_away = _norm_team(row.get("away") or row.get("away_team"))
        if row_home == home_key and row_away == away_key:
            return row
    return {}


def parse_ab_block(block: str, grade: str, idx: int, scout_by_fixture: dict[int, dict[str, Any]], brief_path: Path) -> dict[str, Any]:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    title = lines[0].lstrip("- ").strip() if lines else "UNKNOWN"
    compact_parts = [p.strip() for p in title.split("｜")]
    match_title = compact_parts[0] if compact_parts else title
    home, away = [part.strip() for part in match_title.split(" vs ", 1)] if " vs " in match_title else (match_title, "UNKNOWN")
    meta = lines[1] if len(lines) > 1 else ""
    if len(compact_parts) >= 3:
        league = compact_parts[1] or "UNKNOWN"
        kickoff_display = compact_parts[2] or "TBD"
    else:
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
    reason_line = next((ln for ln in lines if ln.startswith("原因：")), "")
    source = scout_by_fixture.get(fixture_id or -1, {})
    if not source:
        source = _find_scout_match(home, away, scout_by_fixture)
        fixture_id = int(source.get("fixture_id")) if source.get("fixture_id") else fixture_id
    resolved = CN_RESOLVER.resolve_match(home, away, source=str(brief_path.relative_to(ROOT)))
    home_cn, away_cn = resolved["home_team_cn"], resolved["away_team_cn"]
    home_en, away_en = resolved["home_team_en"], resolved["away_team_en"]
    return {
        "index": idx,
        "fixture_id": fixture_id,
        "home": home,
        "away": away,
        "home_cn": home_cn,
        "away_cn": away_cn,
        "home_team_cn": home_cn,
        "away_team_cn": away_cn,
        "home_en": home_en,
        "away_en": away_en,
        "home_team_en": home_en,
        "away_team_en": away_en,
        "team_cn_source": resolved.get("team_cn_source"),
        "team_cn_missing": resolved.get("team_cn_missing"),
        "league": league,
        "kickoff_display": kickoff_display,
        "ht_score": int(score_match.group(1)) if score_match else None,
        "ht_rate": score_match.group(2) if score_match else None,
        "expected_goals": f"{score_match.group(3)}球" if score_match else "-",
        "sample_size": int(score_match.group(4)) if score_match else None,
        "script_type": script_line.replace("剧本：", "") if script_line else "待识别",
        "distribution_text": dist_line.replace("分布：", "") if dist_line else (reason_line.replace("原因：", "") if reason_line else "season_aware_rf brief"),
        "risk": risk_line.replace("风险：", "") if risk_line else (reason_line.replace("原因：", "") if reason_line else "-"),
        "grade": grade,
        "recommendation_status": "brief_formal_display_only",
        "source": str(brief_path.relative_to(ROOT)),
        "scout_fixture_found": bool(source),
        "grade_source": "brief_parsed",
    }


def _is_placeholder_candidate(item: dict[str, Any]) -> bool:
    fixture_id = item.get("fixture_id")
    home = str(item.get("home") or "").strip()
    away = str(item.get("away") or "").strip()
    kickoff = str(item.get("kickoff_display") or "").strip()
    dist = str(item.get("distribution_text") or "").strip()
    bad_tokens = {"", "UNKNOWN", "TBD", "：(无)", "(无)", "无"}
    if not fixture_id:
        return True
    if home in bad_tokens or away in bad_tokens:
        return True
    if "UNKNOWN" in home or "UNKNOWN" in away:
        return True
    if "中文名缺失：UNKNOWN" in str(item.get("home_cn") or "") or "中文名缺失：UNKNOWN" in str(item.get("away_cn") or ""):
        return True
    if kickoff in {"", "TBD"}:
        return True
    if dist in {"", "time_bins 待补齐"}:
        return True
    return False


def parse_c_items(text: str, scout_by_fixture: dict[int, dict[str, Any]], brief_path: Path) -> list[dict[str, Any]]:
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
        resolved = CN_RESOLVER.resolve_match(home, away, source=str(brief_path.relative_to(ROOT)))
        home_cn, away_cn = resolved["home_team_cn"], resolved["away_team_cn"]
        home_en, away_en = resolved["home_team_en"], resolved["away_team_en"]
        items.append({
            "index": idx,
            "home": home,
            "away": away,
            "home_cn": home_cn,
            "away_cn": away_cn,
            "home_team_cn": home_cn,
            "away_team_cn": away_cn,
            "home_en": home_en,
            "away_en": away_en,
            "home_team_en": home_en,
            "away_team_en": away_en,
            "team_cn_source": resolved.get("team_cn_source"),
            "team_cn_missing": resolved.get("team_cn_missing"),
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
            "source": str(brief_path.relative_to(ROOT)),
        })
    return items


def build_candidate_view(date: str, text: str, brief_path: Path, scout_path: Path | None) -> dict[str, Any]:
    scan_perf_path = DAILY / f"scan_perf_v4_{date}.json"
    scan_perf = load_json(scan_perf_path) or {}
    scout_obj = load_json(scout_path) if scout_path else []
    if isinstance(scout_obj, list):
        scout = scout_obj
    elif isinstance(scout_obj, dict):
        scout = scout_obj.get("rows") if isinstance(scout_obj.get("rows"), list) else []
    else:
        scout = []
    scout_by_fixture = {int(item.get("fixture_id")): item for item in scout if isinstance(item, dict) and item.get("fixture_id")}
    overview = parse_overview(text)
    a_items_raw = [parse_ab_block(block, "A", i, scout_by_fixture, brief_path) for i, block in enumerate(split_grade_blocks(text, "A"), 1)]
    b_items_raw = [parse_ab_block(block, "B", i, scout_by_fixture, brief_path) for i, block in enumerate(split_grade_blocks(text, "B"), 1)]
    a_items = [x for x in a_items_raw if not _is_placeholder_candidate(x)]
    b_items = [x for x in b_items_raw if not _is_placeholder_candidate(x)]
    parsed_by_fixture = {}
    for x in a_items + b_items:
        fid = x.get("fixture_id")
        if fid:
            parsed_by_fixture[int(fid)] = x

    # Official-grade-first merge:
    # 1) preserve scan official grade from scout;
    # 2) brief/explain only enrich display text; never overwrite A/B/SKIP.
    merged_a: list[dict[str, Any]] = []
    merged_b: list[dict[str, Any]] = []
    for row in scout:
        if not isinstance(row, dict):
            continue
        fid = row.get("fixture_id")
        if not fid:
            continue
        grade = str((row.get("official_grade") or row.get("grade") or "")).upper().strip()
        if grade not in {"A", "B"}:
            continue
        p = parsed_by_fixture.get(int(fid), {})
        home = str(row.get("home") or row.get("home_team") or p.get("home") or "UNKNOWN")
        away = str(row.get("away") or row.get("away_team") or p.get("away") or "UNKNOWN")
        resolved = CN_RESOLVER.resolve_match(home, away, source=str(brief_path.relative_to(ROOT)))
        market_scores = row.get("market_scores") if isinstance(row.get("market_scores"), dict) else {}
        factors = row.get("factors") if isinstance(row.get("factors"), dict) else {}
        explain_missing = not market_scores or not factors
        base = {
            "index": len(merged_a) + 1 if grade == "A" else len(merged_b) + 1,
            "fixture_id": fid,
            "home": home,
            "away": away,
            "home_cn": resolved["home_team_cn"],
            "away_cn": resolved["away_team_cn"],
            "home_team_cn": resolved["home_team_cn"],
            "away_team_cn": resolved["away_team_cn"],
            "home_en": resolved["home_team_en"],
            "away_en": resolved["away_team_en"],
            "home_team_en": resolved["home_team_en"],
            "away_team_en": resolved["away_team_en"],
            "team_cn_source": resolved.get("team_cn_source"),
            "team_cn_missing": resolved.get("team_cn_missing"),
            "league": str(row.get("league") or row.get("league_name") or p.get("league") or "UNKNOWN"),
            "kickoff_display": str(row.get("kickoff") or row.get("kickoff_time") or p.get("kickoff_display") or "TBD"),
            "ht_score": p.get("ht_score"),
            "ht_rate": p.get("ht_rate"),
            "expected_goals": p.get("expected_goals") or "-",
            "sample_size": p.get("sample_size"),
            "script_type": p.get("script_type") or "待识别",
            "distribution_text": p.get("distribution_text") or "time_bins 待补齐",
            "risk": p.get("risk") or "-",
            "grade": grade,
            "official_grade": grade,
            "grade_source": "scout_official",
            "recommendation_status": "scan_official_display",
            "source": str(brief_path.relative_to(ROOT)),
            "scout_fixture_found": True,
            "fallback_recompute": False,
            "market_scores_empty": not market_scores,
            "factors_empty": not factors,
            "explain_factors_missing": explain_missing,
            "official_grade_preserved": True,
        }
        if grade == "A":
            merged_a.append(base)
        else:
            merged_b.append(base)

    # The formal brief supplies display grades only when scout lacks A/B grades.
    scout_has_official_ab = len(merged_a) + len(merged_b) > 0
    if not scout_has_official_ab:
        for x in a_items:
            x["fallback_recompute"] = True
            x["official_grade_preserved"] = False
            x["grade_source"] = "formal_brief_display"
        for x in b_items:
            x["fallback_recompute"] = True
            x["official_grade_preserved"] = False
            x["grade_source"] = "formal_brief_display"
        merged_a = a_items
        merged_b = b_items

    c_items = parse_c_items(text, scout_by_fixture, brief_path)
    scout_grade_counts = {"A": 0, "B": 0, "C": 0, "SKIP": 0}
    for row in scout:
        if isinstance(row, dict):
            g = str((row.get("official_grade") or row.get("grade") or "")).upper().strip()
            if g in scout_grade_counts:
                scout_grade_counts[g] += 1
    final_a = len(merged_a)
    final_b = len(merged_b)
    final_c = int(overview.get("C", len(c_items)) or 0)
    scan_perf_total = scan_perf.get("total_fixtures") if isinstance(scan_perf, dict) else None
    final_total = int(scan_perf_total or overview.get("scan_total", final_a + final_b + final_c) or 0)
    final_skip = max(0, final_total - final_a - final_b - final_c)
    return {
        "schema_version": "v4_official_candidate_view.v1",
        "generated_at": datetime.now(TZ).isoformat(),
        "scan_date": date,
        "source_window": "daily_1200",
        "source_path": str(brief_path.relative_to(ROOT)),
        "source_hash": sha(brief_path),
        "brief_path": str(brief_path.relative_to(ROOT)),
        "brief_sha256": sha(brief_path),
        "scout_path": str(scout_path.relative_to(ROOT)) if scout_path else None,
        "scout_sha256": sha(scout_path),
        "scan_perf_path": str(scan_perf_path.relative_to(ROOT)) if scan_perf_path.exists() else None,
        "scan_perf_sha256": sha(scan_perf_path) if scan_perf_path.exists() else None,
        "scan_perf_total_fixtures": scan_perf_total,
        "scouted_count": scan_perf.get("scouted_count") if isinstance(scan_perf, dict) else None,
        "A_count": final_a,
        "B_count": final_b,
        "C_count": final_c,
        "SKIP_count": final_skip,
        "scan_total": final_total,
        "formal_recommendation_count": final_a + final_b,
        "A_candidates": merged_a,
        "A_candidate": merged_a[0] if merged_a else None,
        "B_candidates": merged_b,
        "C_candidates": c_items,
        "C_observation_only": True,
        "actual_send": False,
        "qq_sent": False,
        "V4_QQ_ENABLED": False,
        "parsed_from_brief": True,
        "fallback_used": not scout_has_official_ab,
        "fallback_reason": None if scout_has_official_ab else "scout_missing_grade_use_formal_brief_display",
        "builder_script": "tools/build_v4_official_candidate_view.py",
        "official_grade_source": "scout_official" if scout_has_official_ab else "brief_fallback",
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
            "schema_version": "v4_official_candidate_view_resolution.v1",
            "phase": "V4-OFFICIAL-CANDIDATE-VIEW",
            "generated_at": datetime.now(TZ).isoformat(),
            "date": date,
            "brief_path": str(brief_path.relative_to(ROOT)),
            "brief_exists": True,
            "brief_sha256": sha(brief_path),
            "brief_size": brief_path.stat().st_size,
            "source_date": date,
            "is_today_brief": date == datetime.now(TZ).strftime("%Y%m%d"),
            "candidate_counts": counts,
            "A": counts["A"],
            "B": counts["B"],
            "C": counts["C"],
            "SKIP": counts["SKIP"],
            "formal_count": view["formal_recommendation_count"],
            "window": "daily_1200",
            "parsed_from_brief": True,
            "fallback_used": bool(view.get("fallback_used")),
            "fallback_reason": view.get("fallback_reason"),
            "candidate_view": view,
            "brief_used_for_hit_rate": False,
            "capture_ran": False,
            "QQ_push": False,
            "cloud_publish": False,
        }
        if write:
            out_view = STATUS / f"v4_official_candidate_view_{date}.json"
            out_view.write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
            missing_rows: list[dict[str, Any]] = []
            for bucket in ("A_candidates", "B_candidates", "C_candidates"):
                rows = view.get(bucket, [])
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if row.get("team_cn_missing"):
                        missing_rows.append({
                            "source": "candidate_view",
                            "date": date,
                            "fixture_id": row.get("fixture_id"),
                            "grade": row.get("grade"),
                            "home_team_en": row.get("home_team_en"),
                            "away_team_en": row.get("away_team_en"),
                            "home_team_cn": row.get("home_team_cn"),
                            "away_team_cn": row.get("away_team_cn"),
                            "team_cn_source": row.get("team_cn_source"),
                        })
            missing_path = STATUS / f"missing_team_cn_{date}.json"
            missing_payload = {"date": date, "missing_count": len(missing_rows), "missing_rows": missing_rows}
            missing_path.write_text(json.dumps(missing_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if write:
        out = STATUS / f"v4_official_candidate_view_resolution_{date}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(TZ).strftime("%Y%m%d"))
    args = parser.parse_args()
    result = resolve(args.date, write=True)
    printable = dict(result)
    printable.pop("candidate_view", None)
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 1 if result.get("blocker") else 0


if __name__ == "__main__":
    raise SystemExit(main())
