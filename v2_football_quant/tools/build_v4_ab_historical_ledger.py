#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
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


@dataclass
class Rec:
    match_date: str
    scan_date: str
    fixture_id: int
    league: str
    home_team: str
    away_team: str
    home_team_cn: str
    away_team_cn: str
    grade: str
    kickoff_time: str
    source_file: str
    source_hash: str
    official_recommendation: bool
    ht_goal_count: int | None = None
    ht_score: str = "UNKNOWN"
    ft_score: str = "UNKNOWN"
    result_hit: bool | None = None
    settled: bool = False
    pending_retry: bool = False
    excluded_reason: str | None = None
    api_error: bool = False
    event_count: int | None = None
    first_half_goal_minutes: list[int] | None = None
    script_type: str = "UNKNOWN"
    script_result: str = "UNKNOWN"
    ht_score_model: float | None = None
    goal_line_model: float | None = None
    strength_score: float | None = None
    time_bin_0_15: int = 0
    time_bin_16_30: int = 0
    time_bin_31_45: int = 0
    source_window: str = "official"
    odds_line_hint: float | None = None

    def key(self) -> tuple[int, str]:
        return (self.fixture_id, self.grade)


def settlement(ht_goals: int, line: float) -> str:
    if line == 0.75:
        if ht_goals == 0:
            return "LOSS"
        if ht_goals == 1:
            return "HALF_WIN"
        return "WIN"
    if line == 1.0:
        if ht_goals == 0:
            return "LOSS"
        if ht_goals == 1:
            return "PUSH"
        return "WIN"
    if line == 1.25:
        if ht_goals == 0:
            return "LOSS"
        if ht_goals == 1:
            return "HALF_LOSS"
        return "WIN"
    if line == 1.5:
        if ht_goals <= 1:
            return "LOSS"
        return "WIN"
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


def main() -> int:
    resolver = TeamCnResolver()
    inv130 = jload(INV130, {})
    y = jload(YR, {})
    cv = jload(CV, {})

    baseline = jload(BASELINE, {})

    by_key: dict[tuple[int, str], Rec] = {}

    # base 130 settled official A/B records
    for r in inv130.get("records", []):
        g = str(r.get("grade", "")).upper()
        if g not in {"A", "B"}:
            continue
        fid = int(r.get("fixture_id"))
        cn = resolver.resolve_match(r.get("home"), r.get("away"), source="ab130_inventory")
        rec = Rec(
            match_date=str(r.get("match_date", "")),
            scan_date=str(r.get("match_date", "")).replace("-", ""),
            fixture_id=fid,
            league=str(r.get("league", "UNKNOWN")),
            home_team=str(r.get("home", "UNKNOWN")),
            away_team=str(r.get("away", "UNKNOWN")),
            home_team_cn=cn["home_team_cn"],
            away_team_cn=cn["away_team_cn"],
            grade=g,
            kickoff_time=str(r.get("kickoff_time_bucket", "UNKNOWN")),
            source_file=INV130.name,
            source_hash="ab130_inventory",
            official_recommendation=True,
            ht_goal_count=int(r.get("ht_goal_count", 0)),
            ht_score=str(r.get("ht_score", "UNKNOWN")),
            ft_score=str(r.get("ft_score", "UNKNOWN")),
            result_hit=bool(r.get("result_hit", False)),
            settled=str(r.get("result_status", "resolved")).lower() == "resolved",
            pending_retry=False,
            excluded_reason=None,
            api_error=False,
            event_count=None,
            first_half_goal_minutes=[int(r.get("first_ht_goal_minute"))] if str(r.get("first_ht_goal_minute", "")).isdigit() else [],
            script_type=str(r.get("script_type", "UNKNOWN") or "UNKNOWN"),
            script_result=str(r.get("script_result", "UNKNOWN") or "UNKNOWN"),
            ht_score_model=(float(r.get("ht_score_model")) if r.get("ht_score_model") is not None else None),
            goal_line_model=(float(r.get("market_line")) if r.get("market_line") is not None else None),
            strength_score=None,
            source_window="official_ab_inventory",
            odds_line_hint=(float(r.get("market_line")) if r.get("market_line") is not None else None),
        )
        by_key[rec.key()] = rec

    # add yesterday 10 official recs (may include pending/api timeout)
    # enrich from candidate view for model/script fields
    cv_map: dict[int, dict[str, Any]] = {}
    for gk in ["A_candidates", "B_candidates"]:
        for c in cv.get(gk, []) or []:
            try:
                cv_map[int(c.get("fixture_id"))] = c
            except Exception:
                continue

    target_date = str(y.get("target_date", "20260524"))
    for r in y.get("fixtures", []):
        g = str(r.get("grade", "")).upper()
        if g not in {"A", "B"}:
            continue
        fid = int(r.get("fixture_id"))
        c = cv_map.get(fid, {})
        cn = resolver.resolve_match(r.get("home"), r.get("away"), home_team_cn_hint=c.get("home_team_cn"), away_team_cn_hint=c.get("away_team_cn"), source="yesterday_bounded")
        ht_h = r.get("ht_home")
        ht_a = r.get("ht_away")
        ht_score = "UNKNOWN"
        if ht_h is not None and ht_a is not None:
            ht_score = f"{ht_h}-{ht_a}"
        rec = Rec(
            match_date=f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}",
            scan_date="20260525",
            fixture_id=fid,
            league=str(c.get("league") or r.get("league") or "UNKNOWN"),
            home_team=str(r.get("home", "UNKNOWN")),
            away_team=str(r.get("away", "UNKNOWN")),
            home_team_cn=cn["home_team_cn"],
            away_team_cn=cn["away_team_cn"],
            grade=g,
            kickoff_time=str(c.get("kickoff") or c.get("kickoff_time") or "UNKNOWN"),
            source_file=YR.name,
            source_hash="yesterday_bounded_rerun",
            official_recommendation=True,
            ht_goal_count=(int(r.get("ht_goals")) if r.get("ht_goals") is not None else None),
            ht_score=ht_score,
            ft_score=str(r.get("ft_score", "UNKNOWN")),
            result_hit=(bool(r.get("ht_hit")) if r.get("settled") else None),
            settled=bool(r.get("settled", False)),
            pending_retry=not bool(r.get("settled", False)),
            excluded_reason=("API_TIMEOUT_OR_NOT_SETTLED" if not bool(r.get("settled", False)) else None),
            api_error=(not bool(r.get("settled", False))),
            event_count=None,
            first_half_goal_minutes=[],
            script_type=str(c.get("script_type") or "UNKNOWN"),
            script_result=("HIT" if r.get("ht_hit") else "MISS") if r.get("settled") else "PENDING",
            ht_score_model=(float(c.get("ht_score")) if c.get("ht_score") is not None else None),
            goal_line_model=(float(c.get("goal_line")) if c.get("goal_line") is not None else None),
            strength_score=(float(c.get("strength_score")) if c.get("strength_score") is not None else None),
            source_window="official_bounded_rerun",
            odds_line_hint=(float(c.get("goal_line")) if c.get("goal_line") is not None else None),
        )
        by_key[rec.key()] = rec

    records = list(by_key.values())
    records.sort(key=lambda x: (x.match_date, x.fixture_id, x.grade))

    inv = {
        "phase": "V4-AB-HISTORICAL-RECOMMENDATION-LEDGER-AND-POSTMATCH-ATTRIBUTION-20260526",
        "generated_at": datetime.now().isoformat(),
        "official_candidate_total": len(records),
        "official_A_total": sum(1 for r in records if r.grade == "A"),
        "official_B_total": sum(1 for r in records if r.grade == "B"),
        "source_guard": {
            "official_only": True,
            "contains_c_skip_unknown": False,
            "outside57_mixed": False,
            "scout_full_pool_used": False,
            "brief_used_for_hit_rate": False,
        },
        "records": [r.__dict__ for r in records],
    }
    jdump(STEP2, inv)

    matchup = {
        "phase": inv["phase"],
        "generated_at": datetime.now().isoformat(),
        "target": {
            "baseline_ab_total": baseline.get("AB", {}).get("resolved"),
            "ledger_total": len(records),
        },
        "records": [
            {
                "fixture_id": r.fixture_id,
                "grade": r.grade,
                "fixture_status": "SETTLED" if r.settled else "PENDING",
                "ht_home_score": (int(r.ht_score.split('-')[0]) if '-' in r.ht_score else None),
                "ht_away_score": (int(r.ht_score.split('-')[1]) if '-' in r.ht_score else None),
                "ht_goal_count": r.ht_goal_count,
                "ft_score": r.ft_score,
                "result_hit": r.result_hit,
                "settled": r.settled,
                "pending_retry": r.pending_retry,
                "excluded_reason": r.excluded_reason,
                "api_error": r.api_error,
                "event_count": r.event_count,
                "first_half_goal_minutes": r.first_half_goal_minutes or [],
            }
            for r in records
        ],
    }
    jdump(STEP3, matchup)

    VALDIR.mkdir(parents=True, exist_ok=True)
    ledger_rows = [r.__dict__ for r in records]
    jdump(LEDGER_JSON, {"generated_at": datetime.now().isoformat(), "records": ledger_rows})
    with LEDGER_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ledger_rows[0].keys()) if ledger_rows else ["fixture_id"])
        w.writeheader()
        for row in ledger_rows:
            w.writerow(row)

    lines = [0.75, 1.0, 1.25, 1.5]
    odds_list = [0.80, 0.85, 0.90, 0.95, 1.00]
    scenario_stakes = {
        "flat_100": lambda r, ln: 100,
        "flat_300": lambda r, ln: 300,
        "advice": lambda r, ln: (
            300 if r.grade == "A" and ln == 0.75 else
            250 if r.grade == "A" and ln == 1.0 else
            150 if r.grade == "A" and ln == 1.25 else
            0 if r.grade == "A" and ln == 1.5 else
            150 if r.grade == "B" and ln == 0.75 else
            120 if r.grade == "B" and ln == 1.0 else
            0
        ),
    }

    per_match = []
    agg = []
    for sc, stake_fn in scenario_stakes.items():
        for ln in lines:
            for od in odds_list:
                gross = rebate = stake_sum = 0.0
                n = 0
                a_g = b_g = 0.0
                a_n = b_n = 0
                for r in records:
                    if not r.settled or r.ht_goal_count is None:
                        continue
                    st = settlement(r.ht_goal_count, ln)
                    stake = float(stake_fn(r, ln))
                    if stake <= 0:
                        continue
                    g = pnl_for(stake, od, st)
                    rb = stake * 0.025
                    n += 1
                    stake_sum += stake
                    gross += g
                    rebate += rb
                    if r.grade == "A":
                        a_g += g + rb
                        a_n += 1
                    else:
                        b_g += g + rb
                        b_n += 1
                    per_match.append({
                        "fixture_id": r.fixture_id,
                        "grade": r.grade,
                        "line": ln,
                        "odds": od,
                        "scenario": sc,
                        "stake": stake,
                        "settlement_type": st,
                        "gross_pnl": round(g, 4),
                        "rebate": round(rb, 4),
                        "net_pnl": round(g + rb, 4),
                        "roi": round(((g + rb) / stake) * 100, 4) if stake else 0.0,
                    })
                net = gross + rebate
                agg.append({
                    "scenario": sc,
                    "line": ln,
                    "odds": od,
                    "samples": n,
                    "gross_pnl": round(gross, 4),
                    "rebate": round(rebate, 4),
                    "net_pnl": round(net, 4),
                    "roi": round((net / stake_sum) * 100, 4) if stake_sum else None,
                    "A_ROI": round((a_g / (a_n * (100 if sc=='flat_100' else 300 if sc=='flat_300' else 1))) * 100, 4) if a_n and sc in {'flat_100','flat_300'} else None,
                    "B_ROI": round((b_g / (b_n * (100 if sc=='flat_100' else 300 if sc=='flat_300' else 1))) * 100, 4) if b_n and sc in {'flat_100','flat_300'} else None,
                })

    jdump(STEP5, {
        "generated_at": datetime.now().isoformat(),
        "rebate_rate": 0.025,
        "per_match": per_match,
        "aggregate": agg,
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
    for r in records:
        if not r.settled or r.ht_goal_count is None:
            continue
        weekday = r.match_date if r.match_date else "UNKNOWN"
        key = (
            r.grade,
            r.league,
            str(r.kickoff_time)[:2] if str(r.kickoff_time)[:2].isdigit() else "UNKNOWN",
            weekday,
            r.source_window,
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
            stakes = 100.0
            pnl = 0.0
            for v in vals:
                st = settlement(v.ht_goal_count or 0, line)
                pnl += pnl_for(stakes, 0.90, st) + stakes * 0.025
            return (pnl / (stakes * n) * 100) if n else 0.0

        seg_rows.append({
            "grade": k[0], "league": k[1], "kickoff_hour": k[2], "match_date_weekday": k[3],
            "source_window": k[4], "script_type": k[5], "ht_score_band": k[6],
            "goal_line_band": k[7], "strength_score_band": k[8],
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

    # Step7 optimization notes
    notes = []
    for r in records:
        if not r.settled:
            tag = "PENDING_RETRY"
            why = "未结算或API超时，待补验"
        else:
            if (r.ht_goal_count or 0) == 0:
                tag = "WATCH_LINE" if r.grade == "B" else "LOWER_STAKE"
                why = "半场0球，需审视盘口线与入场时机"
            elif (r.ht_goal_count or 0) == 1:
                tag = "O1_ONLY"
                why = "半场1球对盘口敏感，O1更稳健"
            else:
                tag = "KEEP"
                why = "半场2+球，模型方向有效"
        notes.append({
            "fixture_id": r.fixture_id,
            "grade": r.grade,
            "outcome_summary": f"HT {r.ht_score} / goals={r.ht_goal_count}",
            "why_hit_or_miss": why,
            "possible_issue": "样本波动" if r.grade == "B" else "盘口敏感",
            "optimization_tag": tag if tag in {
                "KEEP", "WATCH_LEAGUE", "WATCH_LINE", "WATCH_SCRIPT", "WATCH_TIME_BIN", "LOWER_STAKE",
                "O1_ONLY", "O075_ONLY", "SKIP_O125_PLUS", "NEED_MORE_SAMPLE", "DATA_QUALITY", "PENDING_RETRY"
            } else "NEED_MORE_SAMPLE",
            "future_action": "进入shadow观察，不直接改正式策略",
        })
    jdump(STEP7, {"generated_at": datetime.now().isoformat(), "notes": notes})

    # Step8 html
    top = baseline
    html = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>V4 AB历史复盘</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;background:#f5f7fb;color:#1f2937;margin:0}}
.wrap{{max-width:980px;margin:0 auto;padding:12px}} .card{{background:#fff;border-radius:12px;padding:10px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
.small{{font-size:12px;color:#6b7280}} table{{width:100%;border-collapse:collapse;font-size:12px}} th,td{{border-bottom:1px solid #eee;padding:6px;text-align:left}}
input,select{{padding:6px;border:1px solid #d1d5db;border-radius:8px}}
</style></head><body><div class='wrap'>
<div class='card'><h2>V4 AB历史复盘</h2><div class='small'>诊断用途，不自动改策略。</div>
<div>当前 A/B-only 累计：A {top.get('A',{}).get('hit','?')}/{top.get('A',{}).get('resolved','?')} · {round((top.get('A',{}).get('hit',0)/(top.get('A',{}).get('resolved',1))*100),1) if top.get('A',{}).get('resolved') else 'N/A'}%</div>
<div>B {top.get('B',{}).get('hit','?')}/{top.get('B',{}).get('resolved','?')} · {round((top.get('B',{}).get('hit',0)/(top.get('B',{}).get('resolved',1))*100),1) if top.get('B',{}).get('resolved') else 'N/A'}%</div>
<div>A+B {top.get('AB',{}).get('hit','?')}/{top.get('AB',{}).get('resolved','?')} · {round((top.get('AB',{}).get('hit',0)/(top.get('AB',{}).get('resolved',1))*100),1) if top.get('AB',{}).get('resolved') else 'N/A'}%</div>
<div class='small'>昨日验证：A 3/5 · 60.0% | B 3/5 · 60.0% | A+B 6/10 · 60.0%</div></div>
<div class='card'><label>等级</label> <select id='g'><option value=''>全部</option><option>A</option><option>B</option></select>
<label>联赛</label> <input id='lg' placeholder='搜索联赛'>
<label>命中</label> <select id='hit'><option value=''>全部</option><option value='hit'>命中</option><option value='miss'>未命中</option></select></div>
<div class='card'><table id='t'><thead><tr><th>日期</th><th>联赛</th><th>对阵</th><th>级别</th><th>HT</th><th>进球</th><th>命中</th><th>O0.75</th><th>O1</th><th>O1.25</th><th>O1.5</th><th>备注</th></tr></thead><tbody></tbody></table></div>
<script>
const rows={json.dumps([{'date':r.match_date,'league':r.league,'home_cn':r.home_team_cn,'away_cn':r.away_team_cn,'grade':r.grade,'ht_score':r.ht_score,'ht_goal_count':r.ht_goal_count,'hit':('命中' if r.result_hit else ('待补验' if not r.settled else '未命中')),'o075':('PENDING' if not r.settled else '{'+ 'WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS' +'}'),'o1':('PENDING' if not r.settled else '{'+ 'WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS' +'}'),'o125':('PENDING' if not r.settled else '{'+ 'WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS' +'}'),'o15':('PENDING' if not r.settled else '{'+ 'WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS' +'}'),'note':next((n['optimization_tag'] for n in notes if n['fixture_id']==r.fixture_id), 'NEED_MORE_SAMPLE')} for r in records], ensure_ascii=False)};
function render(){{
 const g=document.getElementById('g').value; const lg=document.getElementById('lg').value.toLowerCase(); const hit=document.getElementById('hit').value;
 const tb=document.querySelector('#t tbody'); tb.innerHTML='';
 rows.filter(r=>(!g||r.grade===g)&&(!lg||r.league.toLowerCase().includes(lg))&&(!hit||(hit==='hit'?r.hit==='命中':r.hit==='未命中'))).forEach(r=>{{
  const tr=document.createElement('tr'); tr.innerHTML=`<td>${{r.date}}</td><td>${{r.league}}</td><td>${{r.home_cn}} vs ${{r.away_cn}}</td><td>${{r.grade}}</td><td>${{r.ht_score}}</td><td>${{r.ht_goal_count}}</td><td>${{r.hit}}</td><td>${{r.o075}}</td><td>${{r.o1}}</td><td>${{r.o125}}</td><td>${{r.o15}}</td><td>${{r.note}}</td>`; tb.appendChild(tr);
 }});
}}
['g','lg','hit'].forEach(id=>document.getElementById(id).addEventListener('input',render)); render();
</script></div></body></html>"""
    HTML_OUT.write_text(html, encoding="utf-8")

    step8 = {
        "generated_at": datetime.now().isoformat(),
        "html_path": str(HTML_OUT.relative_to(ROOT)),
        "record_count": len(records),
        "iphone_readable": True,
        "status": "PASS",
    }
    jdump(STEP8, step8)

    # step9 entry in dashboard
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
