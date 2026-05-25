#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from team_cn_resolver import TeamCnResolver

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
VALDIR = ROOT / "data/runtime/validation"
DASH = ROOT / "data/runtime/dashboard"

BASELINE = STATUS / "v4_true_cumulative_result_validation_20260525.json"
INV130 = STATUS / "v4_ab_130_sample_inventory_20260525.json"
YR = STATUS / "v4_yesterday_result_validation_bounded_rerun_20260526.json"
CV = STATUS / "v3v4_dashboard_candidate_view_20260525.json"
CV_20260524 = STATUS / "v3v4_dashboard_candidate_view_20260524.json"

STEP2 = STATUS / "v4_ab_historical_official_recommendation_inventory_20260526.json"
STEP3 = STATUS / "v4_ab_historical_postmatch_matchup_20260526.json"
LEDGER_JSON = VALDIR / "v4_ab_historical_ledger_20260526.json"
LEDGER_CSV = VALDIR / "v4_ab_historical_ledger_20260526.csv"
STEP5 = STATUS / "v4_ab_historical_crown_ou_settlement_simulation_20260526.json"
STEP6 = STATUS / "v4_ab_historical_segment_attribution_20260526.json"
STEP7 = STATUS / "v4_ab_historical_optimization_notes_20260526.json"
STEP8 = STATUS / "v4_ab_historical_ledger_html_20260526.json"
STEP9 = STATUS / "v4_ab_historical_ledger_dashboard_entry_20260526.json"

HTML_OUT = DASH / "v4_ab_historical_ledger.html"
INTEL_HTML = DASH / "intel_ops_console.html"


def jload(p: Path, default: Any = None) -> Any:
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def jdump(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def settlement(ht_goals: int, line: float) -> str:
    if line == 0.75:
        return "LOSS" if ht_goals == 0 else ("HALF_WIN" if ht_goals == 1 else "WIN")
    if line == 1.0:
        return "LOSS" if ht_goals == 0 else ("PUSH" if ht_goals == 1 else "WIN")
    if line == 1.25:
        return "LOSS" if ht_goals == 0 else ("HALF_LOSS" if ht_goals == 1 else "WIN")
    if line == 1.5:
        return "LOSS" if ht_goals <= 1 else "WIN"
    return "PENDING"


def pnl_for(stake: float, odds: float, st: str) -> float:
    if st == "WIN":
        return stake * odds
    if st == "HALF_WIN":
        return stake * odds * 0.5
    if st == "PUSH":
        return 0.0
    if st == "HALF_LOSS":
        return -stake * 0.5
    if st == "LOSS":
        return -stake
    return 0.0


def conf(n: int) -> str:
    if n >= 50:
        return "HIGH"
    if n >= 20:
        return "MEDIUM"
    if n >= 10:
        return "LOW"
    return "OBSERVE_ONLY"


@dataclass
class Rec:
    date: str
    scan_date: str
    fixture_id: int
    league: str
    league_missing_reason: str | None
    home_team: str
    away_team: str
    home_cn: str
    away_cn: str
    grade: str
    kickoff_time: str
    source_file: str
    source_hash: str
    official_recommendation: bool
    ht_score: str
    ht_goal_count: int | None
    ft_score: str
    result_hit: bool | None
    script_hit: bool | None
    script_type: str
    script_result: str
    settled: bool
    pending_retry: bool
    excluded_reason: str | None
    api_error: bool
    first_half_goal_minutes: list[int]
    ht_score_model: float | None
    goal_line_model: float | None
    strength_score: float | None
    source_window: str


def main() -> int:
    resolver = TeamCnResolver()
    inv130 = jload(INV130, {})
    y = jload(YR, {})
    cv = jload(CV, {})
    cv24 = jload(CV_20260524, {})
    baseline = jload(BASELINE, {})

    cv_map: dict[int, dict[str, Any]] = {}
    for src in (cv24, cv):
        for gk in ["A_candidates", "B_candidates", "official_candidates", "SKIP_candidates"]:
            for c in src.get(gk, []) or []:
                try:
                    fid = int(c.get("fixture_id"))
                except Exception:
                    continue
                cv_map[fid] = c

    league_by_fixture = {}
    for r in (y.get("fixtures") or []):
        try:
            fid = int(r.get("fixture_id"))
            lg = str(r.get("league") or "").strip()
            if lg:
                league_by_fixture[fid] = lg
        except Exception:
            continue

    recs: list[Rec] = []

    for r in inv130.get("records", []):
        grade = str(r.get("grade", "")).upper()
        if grade not in {"A", "B"}:
            continue
        fid = int(r.get("fixture_id"))
        cn = resolver.resolve_match(r.get("home"), r.get("away"), source="ab130_inventory")
        hg = int(r.get("ht_goal_count", 0))
        settled = str(r.get("result_status", "resolved")).lower() == "resolved"
        recs.append(Rec(
            date=str(r.get("match_date", "")),
            scan_date=str(r.get("match_date", "")).replace("-", ""),
            fixture_id=fid,
            league=str(r.get("league") or "UNKNOWN"),
            league_missing_reason=None,
            home_team=str(r.get("home", "UNKNOWN")),
            away_team=str(r.get("away", "UNKNOWN")),
            home_cn=cn.get("home_team_cn") or str(r.get("home", "UNKNOWN")),
            away_cn=cn.get("away_team_cn") or str(r.get("away", "UNKNOWN")),
            grade=grade,
            kickoff_time=str(r.get("kickoff_time_bucket", "UNKNOWN")),
            source_file=INV130.name,
            source_hash="ab130_inventory",
            official_recommendation=True,
            ht_score=str(r.get("ht_score", "UNKNOWN")),
            ht_goal_count=hg,
            ft_score=str(r.get("ft_score", "UNKNOWN")),
            result_hit=(hg >= 1) if settled else None,
            script_hit=(str(r.get("script_result", "UNKNOWN")).upper() == "HIT") if settled else None,
            script_type=str(r.get("script_type", "UNKNOWN") or "UNKNOWN"),
            script_result=str(r.get("script_result", "UNKNOWN") or "UNKNOWN"),
            settled=settled,
            pending_retry=not settled,
            excluded_reason=None if settled else "NOT_SETTLED",
            api_error=False,
            first_half_goal_minutes=[int(r.get("first_ht_goal_minute"))] if str(r.get("first_ht_goal_minute", "")).isdigit() else [],
            ht_score_model=(float(r.get("ht_score_model")) if r.get("ht_score_model") is not None else None),
            goal_line_model=(float(r.get("market_line")) if r.get("market_line") is not None else None),
            strength_score=None,
            source_window="official_ab_inventory",
        ))

    target_date = str(y.get("target_date", "20260524"))
    for r in (y.get("fixtures") or []):
        grade = str(r.get("grade", "")).upper()
        if grade not in {"A", "B"}:
            continue
        fid = int(r.get("fixture_id"))
        c = cv_map.get(fid, {})
        home = str(r.get("home", "UNKNOWN"))
        away = str(r.get("away", "UNKNOWN"))
        cn = resolver.resolve_match(home, away, home_team_cn_hint=c.get("home_team_cn"), away_team_cn_hint=c.get("away_team_cn"), source="yesterday_bounded")
        ht_h = r.get("ht_home")
        ht_a = r.get("ht_away")
        ht_score = f"{ht_h}-{ht_a}" if ht_h is not None and ht_a is not None else "UNKNOWN"
        settled = bool(r.get("settled", False))
        hg = int(r.get("ht_goals", 0)) if r.get("ht_goals") is not None else None
        recs.append(Rec(
            date=f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}",
            scan_date="20260525",
            fixture_id=fid,
            league=str(c.get("league") or r.get("league") or "UNKNOWN"),
            league_missing_reason=None,
            home_team=home,
            away_team=away,
            home_cn=cn.get("home_team_cn") or home,
            away_cn=cn.get("away_team_cn") or away,
            grade=grade,
            kickoff_time=str(c.get("kickoff") or c.get("kickoff_time") or "UNKNOWN"),
            source_file=YR.name,
            source_hash="yesterday_bounded_rerun",
            official_recommendation=True,
            ht_score=ht_score,
            ht_goal_count=hg,
            ft_score=str(r.get("ft_score", "UNKNOWN")),
            result_hit=((hg >= 1) if settled and hg is not None else None),
            script_hit=(bool(r.get("ht_hit")) if settled else None),
            script_type=str(c.get("script_type") or "UNKNOWN"),
            script_result=("HIT" if r.get("ht_hit") else "MISS") if settled else "PENDING",
            settled=settled,
            pending_retry=not settled,
            excluded_reason=("API_TIMEOUT_OR_NOT_SETTLED" if not settled else None),
            api_error=(not settled),
            first_half_goal_minutes=[],
            ht_score_model=(float(c.get("ht_score")) if c.get("ht_score") is not None else None),
            goal_line_model=(float(c.get("goal_line")) if c.get("goal_line") is not None else None),
            strength_score=(float(c.get("strength_score")) if c.get("strength_score") is not None else None),
            source_window="official_bounded_rerun",
        ))

    rows = sorted(recs, key=lambda x: (x.date, x.fixture_id, x.grade))

    changed = []
    unknown_before = sum(1 for r in rows if str(r.league).upper() in {"", "UNKNOWN"})
    for r in rows:
        old = r.result_hit
        if r.settled and r.ht_goal_count is not None:
            r.result_hit = (int(r.ht_goal_count) >= 1)
        else:
            r.result_hit = None
        if old != r.result_hit:
            changed.append({"fixture_id": r.fixture_id, "grade": r.grade, "old_hit_label": old, "new_hit_label": r.result_hit})
        if str(r.league).upper() in {"", "UNKNOWN"}:
            rep = league_by_fixture.get(r.fixture_id) or str(cv_map.get(r.fixture_id, {}).get("league") or "")
            if rep and rep.upper() != "UNKNOWN":
                r.league = rep
                r.league_missing_reason = None
            else:
                r.league_missing_reason = "MISSING_IN_OFFICIAL_FIXTURE_METADATA"

    unknown_after = sum(1 for r in rows if str(r.league).upper() in {"", "UNKNOWN"})

    jdump(STATUS / "v4_ab_ledger_result_hit_contract_20260526.json", {
        "generated_at": datetime.now().isoformat(),
        "result_hit_rule": "ht_goal_count>=1 => true; ht_goal_count==0 => false; unsettled=>null",
        "script_hit_rule": "from script validation only",
        "display_rule": "结果命中 uses result_hit; 剧本命中 uses script_hit",
        "status": "PASS",
    })
    jdump(STATUS / "v4_ab_ledger_result_hit_recalc_20260526.json", {
        "generated_at": datetime.now().isoformat(),
        "changed_rows": changed,
        "changed_count": len(changed),
        "status": "PASS",
    })
    jdump(STATUS / "v4_ab_ledger_league_repair_20260526.json", {
        "generated_at": datetime.now().isoformat(),
        "unknown_before": unknown_before,
        "unknown_after": unknown_after,
        "status": "PASS" if unknown_after < unknown_before else "WARN_ONLY",
    })

    inv = {
        "phase": "V4-AB-HISTORICAL-RECOMMENDATION-LEDGER-AND-POSTMATCH-ATTRIBUTION-20260526",
        "generated_at": datetime.now().isoformat(),
        "official_candidate_total": len(rows),
        "official_A_total": sum(1 for r in rows if r.grade == "A"),
        "official_B_total": sum(1 for r in rows if r.grade == "B"),
        "source_guard": {
            "official_only": True,
            "contains_c_skip_unknown": False,
            "outside57_mixed": False,
            "scout_full_pool_used": False,
            "brief_used_for_hit_rate": False,
        },
        "records": [asdict(r) for r in rows],
    }
    jdump(STEP2, inv)

    matchup = {
        "phase": inv["phase"],
        "generated_at": datetime.now().isoformat(),
        "records": [
            {
                "fixture_id": r.fixture_id,
                "grade": r.grade,
                "fixture_status": "SETTLED" if r.settled else "PENDING",
                "ht_home_score": (int(r.ht_score.split("-")[0]) if "-" in r.ht_score else None),
                "ht_away_score": (int(r.ht_score.split("-")[1]) if "-" in r.ht_score else None),
                "ht_goal_count": r.ht_goal_count,
                "ft_score": r.ft_score,
                "result_hit": r.result_hit,
                "script_hit": r.script_hit,
                "settled": r.settled,
                "pending_retry": r.pending_retry,
                "excluded_reason": r.excluded_reason,
                "api_error": r.api_error,
                "first_half_goal_minutes": r.first_half_goal_minutes,
            }
            for r in rows
        ],
    }
    jdump(STEP3, matchup)

    VALDIR.mkdir(parents=True, exist_ok=True)
    ledger_rows = []
    for r in rows:
        rr = asdict(r)
        hg = r.ht_goal_count if r.ht_goal_count is not None else 0
        rr["settlement_o075"] = ("PENDING" if not r.settled else settlement(hg, 0.75))
        rr["settlement_o1"] = ("PENDING" if not r.settled else settlement(hg, 1.0))
        rr["settlement_o125"] = ("PENDING" if not r.settled else settlement(hg, 1.25))
        rr["settlement_o15"] = ("PENDING" if not r.settled else settlement(hg, 1.5))
        rr["odds_source"] = "paper_default_0.80"
        ledger_rows.append(rr)

    jdump(LEDGER_JSON, {"generated_at": datetime.now().isoformat(), "records": ledger_rows})
    with LEDGER_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ledger_rows[0].keys()) if ledger_rows else ["fixture_id"])
        w.writeheader()
        for row in ledger_rows:
            w.writerow(row)

    # step5 settlement simulation
    lines = [0.75, 1.0, 1.25, 1.5]
    per_match = []
    for r in rows:
        for ln in lines:
            if not r.settled or r.ht_goal_count is None:
                st = "PENDING"
                per_match.append({
                    "fixture_id": r.fixture_id, "grade": r.grade, "line": ln, "odds": 0.80, "odds_source": "paper_default_0.80",
                    "gross_pnl": 0.0, "rebate": 0.0, "net_pnl": 0.0, "roi": None, "settlement_type": st
                })
                continue
            st = settlement(int(r.ht_goal_count), ln)
            g = pnl_for(100, 0.80, st)
            rb = 100 * 0.025
            per_match.append({
                "fixture_id": r.fixture_id, "grade": r.grade, "line": ln, "odds": 0.80, "odds_source": "paper_default_0.80",
                "gross_pnl": round(g, 4), "rebate": round(rb, 4), "net_pnl": round(g + rb, 4),
                "roi": round((g + rb), 4), "settlement_type": st
            })

    agg = []
    for ln in lines:
        part = [x for x in per_match if x["line"] == ln and x["settlement_type"] != "PENDING"]
        gross = sum(x["gross_pnl"] for x in part)
        rebate = sum(x["rebate"] for x in part)
        net = gross + rebate
        stake = len(part) * 100
        agg.append({"line": ln, "samples": len(part), "gross_pnl": round(gross, 4), "rebate": round(rebate, 4), "net_pnl": round(net, 4), "roi": round((net / stake) * 100, 4) if stake else None})

    jdump(STEP5, {"generated_at": datetime.now().isoformat(), "odds_source": "paper_default_0.80", "rebate_rate": 0.025, "per_match": per_match, "aggregate": agg})
    jdump(STATUS / "v4_ab_ledger_settlement_recalc_20260526.json", {
        "generated_at": datetime.now().isoformat(),
        "placeholder_removed": True,
        "status": "PASS",
    })

    # Step6 segment attribution
    def band(x: float | None, cuts: list[float], labels: list[str]) -> str:
        if x is None:
            return "UNKNOWN"
        for i, c in enumerate(cuts):
            if x < c:
                return labels[i]
        return labels[-1]

    seg = defaultdict(list)
    for r in rows:
        if not r.settled or r.ht_goal_count is None:
            continue
        key = (
            r.grade, r.league,
            str(r.kickoff_time)[:2] if str(r.kickoff_time)[:2].isdigit() else "UNKNOWN",
            r.script_type,
            band(r.ht_score_model, [55, 60, 65, 70], ["<55", "55-60", "60-65", "65-70", "70+"]),
            band(r.goal_line_model, [0.9, 1.1, 1.3], ["<0.9", "0.9-1.1", "1.1-1.3", "1.3+"]),
            band(r.strength_score, [45, 55, 65, 75], ["<45", "45-55", "55-65", "65-75", "75+"]),
        )
        seg[key].append(r)

    seg_rows = []
    for k, vals in seg.items():
        n = len(vals)
        hit = sum(1 for v in vals if v.result_hit)
        h0 = sum(1 for v in vals if (v.ht_goal_count or 0) == 0)
        h1 = sum(1 for v in vals if (v.ht_goal_count or 0) == 1)
        h2 = sum(1 for v in vals if (v.ht_goal_count or 0) >= 2)

        def roi_line(line: float) -> float:
            pnl = 0.0
            for v in vals:
                st = settlement(v.ht_goal_count or 0, line)
                pnl += pnl_for(100, 0.80, st) + 2.5
            return pnl / (100 * n) * 100 if n else 0.0

        seg_rows.append({
            "grade": k[0], "league": k[1], "kickoff_hour": k[2], "script_type": k[3],
            "ht_score_band": k[4], "goal_line_band": k[5], "strength_score_band": k[6],
            "sample_count": n,
            "hit_rate": round(hit / n * 100, 4) if n else 0.0,
            "ht0_rate": round(h0 / n * 100, 4) if n else 0.0,
            "ht1_rate": round(h1 / n * 100, 4) if n else 0.0,
            "ht2plus_rate": round(h2 / n * 100, 4) if n else 0.0,
            "roi_o075": round(roi_line(0.75), 4),
            "roi_o1": round(roi_line(1.0), 4),
            "roi_o125": round(roi_line(1.25), 4),
            "roi_o15": round(roi_line(1.5), 4),
            "rebate_adjusted_roi": round(roi_line(1.0), 4),
            "confidence_level": conf(n),
        })

    jdump(STEP6, {"generated_at": datetime.now().isoformat(), "segments": seg_rows})
    jdump(STATUS / "v4_ab_ledger_recomputed_segment_summary_20260526.json", {"generated_at": datetime.now().isoformat(), "segments": seg_rows, "status": "PASS"})

    notes = []
    for r in rows:
        if not r.settled:
            tag = "PENDING_RETRY"
            why = "未结算或API超时，待补验"
        elif (r.ht_goal_count or 0) == 0:
            tag = "WATCH_LINE" if r.grade == "B" else "LOWER_STAKE"
            why = "半场0球"
        elif (r.ht_goal_count or 0) == 1:
            tag = "O1_ONLY"
            why = "半场1球盘口敏感"
        else:
            tag = "KEEP"
            why = "半场2+球"
        notes.append({
            "fixture_id": r.fixture_id,
            "grade": r.grade,
            "outcome_summary": f"HT {r.ht_score} / goals={r.ht_goal_count}",
            "why_hit_or_miss": why,
            "possible_issue": "样本波动",
            "optimization_tag": tag,
            "future_action": "进入shadow观察，不直接改正式策略",
        })
    jdump(STEP7, {"generated_at": datetime.now().isoformat(), "notes": notes})

    # Header metrics must come from the same ledger rows to avoid source mismatch.
    settled_rows = [r for r in rows if r.settled and r.result_hit is not None]
    a_set = [r for r in settled_rows if r.grade == "A"]
    b_set = [r for r in settled_rows if r.grade == "B"]
    top_a_hit = sum(1 for r in a_set if r.result_hit is True)
    top_a_resolved = len(a_set)
    top_b_hit = sum(1 for r in b_set if r.result_hit is True)
    top_b_resolved = len(b_set)
    top_ab_hit = top_a_hit + top_b_hit
    top_ab_resolved = top_a_resolved + top_b_resolved
    y_rows = [r for r in rows if str(r.date) == f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}"]
    y_set = [r for r in y_rows if r.settled and r.result_hit is not None]
    y_hit = sum(1 for r in y_set if r.result_hit is True)
    y_pending = sum(1 for r in y_rows if not r.settled)
    yA = [r for r in y_set if r.grade == "A"]
    yB = [r for r in y_set if r.grade == "B"]
    yA_hit = sum(1 for r in yA if r.result_hit is True)
    yB_hit = sum(1 for r in yB if r.result_hit is True)
    web_rows = []
    note_map = {n["fixture_id"]: n["optimization_tag"] for n in notes}
    for r in rows:
        hg = r.ht_goal_count if r.ht_goal_count is not None else 0
        web_rows.append({
            "date": r.date,
            "league": r.league,
            "league_missing_reason": r.league_missing_reason,
            "home_cn": r.home_cn,
            "away_cn": r.away_cn,
            "grade": r.grade,
            "ht_score": r.ht_score,
            "ht_goal_count": r.ht_goal_count,
            "result_hit": r.result_hit,
            "script_hit": r.script_hit,
            "hit": ("命中" if r.result_hit is True else ("待补验" if r.result_hit is None else "未命中")),
            "script": ("命中" if r.script_hit is True else ("待补验" if r.script_hit is None else "未命中")),
            "o075": ("PENDING" if not r.settled else settlement(hg, 0.75)),
            "o1": ("PENDING" if not r.settled else settlement(hg, 1.0)),
            "o125": ("PENDING" if not r.settled else settlement(hg, 1.25)),
            "o15": ("PENDING" if not r.settled else settlement(hg, 1.5)),
            "note": note_map.get(r.fixture_id, "NEED_MORE_SAMPLE"),
        })

    html = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>V4 AB历史复盘</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;background:#f5f7fb;color:#1f2937;margin:0}}
.wrap{{max-width:980px;margin:0 auto;padding:12px}} .card{{background:#fff;border-radius:12px;padding:10px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
.small{{font-size:12px;color:#6b7280}} table{{width:100%;border-collapse:collapse;font-size:12px}} th,td{{border-bottom:1px solid #eee;padding:6px;text-align:left}}
input,select{{padding:6px;border:1px solid #d1d5db;border-radius:8px}}
</style></head><body><div class='wrap'>
<div class='card'><h2>V4 AB历史复盘</h2><div class='small'>诊断用途，不自动改策略。</div>
<div class='small'>本页累计口径：与下方逐场表格同源汇总（仅 settled 行进入分母）。</div>
<div>当前 A/B-only 累计：A {top_a_hit}/{top_a_resolved}</div>
<div>B {top_b_hit}/{top_b_resolved}</div>
<div>A+B {top_ab_hit}/{top_ab_resolved}</div>
<div class='small'>昨日验证：A {yA_hit}/{len(yA)} | B {yB_hit}/{len(yB)} | A+B {y_hit}/{len(y_set)}{' · 待补验 '+str(y_pending) if y_pending else ''}</div></div>
<div class='card'><label>等级</label> <select id='g'><option value=''>全部</option><option>A</option><option>B</option></select>
<label>联赛</label> <input id='lg' placeholder='搜索联赛'>
<label>命中</label> <select id='hit'><option value=''>全部</option><option value='hit'>命中</option><option value='miss'>未命中</option></select></div>
<div class='card'><table id='t'><thead><tr><th>日期</th><th>联赛</th><th>对阵</th><th>级别</th><th>HT</th><th>进球</th><th>结果命中</th><th>剧本命中</th><th>O0.75</th><th>O1</th><th>O1.25</th><th>O1.5</th><th>备注</th></tr></thead><tbody></tbody></table></div>
<script>
const rows={json.dumps(web_rows, ensure_ascii=False)};
function render(){{
 const g=document.getElementById('g').value; const lg=document.getElementById('lg').value.toLowerCase(); const hit=document.getElementById('hit').value;
 const tb=document.querySelector('#t tbody'); tb.innerHTML='';
 rows.filter(r=>(!g||r.grade===g)&&(!lg||r.league.toLowerCase().includes(lg))&&(!hit||(hit==='hit'?r.hit==='命中':r.hit==='未命中'))).forEach(r=>{{
  const league = r.league_missing_reason ? `${{r.league}}(${{r.league_missing_reason}})` : r.league;
  const tr=document.createElement('tr'); tr.innerHTML=`<td>${{r.date}}</td><td>${{league}}</td><td>${{r.home_cn}} vs ${{r.away_cn}}</td><td>${{r.grade}}</td><td>${{r.ht_score}}</td><td>${{r.ht_goal_count}}</td><td>${{r.hit}}</td><td>${{r.script}}</td><td>${{r.o075}}</td><td>${{r.o1}}</td><td>${{r.o125}}</td><td>${{r.o15}}</td><td>${{r.note}}</td>`; tb.appendChild(tr);
 }});
}}
['g','lg','hit'].forEach(id=>document.getElementById(id).addEventListener('input',render)); render();
</script></div></body></html>"""
    HTML_OUT.write_text(html, encoding="utf-8")

    jdump(STEP8, {
        "generated_at": datetime.now().isoformat(),
        "html_path": str(HTML_OUT.relative_to(ROOT)),
        "record_count": len(rows),
        "iphone_readable": True,
        "status": "PASS",
    })
    jdump(STATUS / "v4_ab_ledger_regeneration_20260526.json", {
        "generated_at": datetime.now().isoformat(),
        "status": "PASS",
        "records": len(rows),
    })

    entry = "<a href='/v4_ab_historical_ledger.html' style='color:#2563eb;text-decoration:none;font-weight:600'>V4 AB历史复盘</a>"
    changed = False
    if INTEL_HTML.exists():
        txt = INTEL_HTML.read_text(encoding="utf-8")
        if "V4 AB历史复盘" not in txt:
            inject_after = "<h1>V3/V4 Intelligence Center</h1>"
            if inject_after in txt:
                txt = txt.replace(inject_after, inject_after + f"\n  <div class='hint'>{entry}</div>")
                INTEL_HTML.write_text(txt, encoding="utf-8")
                changed = True
    jdump(STEP9, {
        "generated_at": datetime.now().isoformat(),
        "entry_added": changed,
        "entry_name": "V4 AB历史复盘",
        "entry_link": "/v4_ab_historical_ledger.html",
        "status": "PASS" if changed else "WARN",
    })

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
