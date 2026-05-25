#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = ROOT / "data/runtime/live_bets"
LIVE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG = LIVE_DIR / "live_bet_tracker_audit.log"


def _day_file(date: str) -> Path:
    return LIVE_DIR / f"v4_live_bets_{date}.jsonl"


def _daily_summary_file(date: str) -> Path:
    return LIVE_DIR / f"daily_summary_{date}.json"


def _cum_file() -> Path:
    return LIVE_DIR / "cumulative_summary.json"


def _backup(path: Path) -> None:
    if path.exists():
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak_{ts}"))


def _log(msg: str) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()}Z {msg}\n")


def _load_day(date: str) -> List[Dict[str, Any]]:
    path = _day_file(date)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _is_test_record(r: Dict[str, Any]) -> bool:
    if bool(r.get("is_test")):
        return True
    txt = " ".join([
        str(r.get("league") or ""),
        str(r.get("home_cn") or ""),
        str(r.get("away_cn") or ""),
        str(r.get("notes") or ""),
        str(r.get("official_source") or ""),
    ]).lower()
    if "test" in txt or "测试" in txt:
        return True
    fid = str(r.get("fixture_id") or "")
    if fid.startswith("9"):
        return True
    return False


def _effective_bet_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        r for r in rows
        if r.get("bet_status") == "BET" and not _is_test_record(r)
    ]


def _calc_financials(r: Dict[str, Any]) -> Dict[str, float]:
    """Recompute financials from raw settlement fields (do not trust legacy rebate fields)."""
    stake = float(r.get("stake") or 0.0)
    odds = float(r.get("odds_water") or 0.0)
    rr = float(r.get("rebate_rate") or 0.025)
    sr = str(r.get("settlement_result") or "PENDING").upper()

    if sr == "WIN":
        gross = stake * odds
        effective = gross
    elif sr == "HALF_WIN":
        gross = stake * odds * 0.5
        effective = gross
    elif sr == "LOSS":
        gross = -stake
        effective = stake
    elif sr == "HALF_LOSS":
        gross = -stake * 0.5
        effective = stake * 0.5
    else:
        # PUSH / PENDING / VOID
        gross = 0.0
        effective = 0.0

    rebate = effective * rr
    net = gross + rebate
    return {
        "stake_amount": stake,
        "gross_pnl": gross,
        "effective_turnover": effective,
        "rebate": rebate,
        "net_pnl": net,
    }


def _save_day(date: str, rows: List[Dict[str, Any]]) -> None:
    path = _day_file(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = LIVE_DIR / ".lock"
    with lock.open("w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        _backup(path)
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def add_bet(rec: Dict[str, Any]) -> Dict[str, Any]:
    date = rec["date"]
    rows = _load_day(date)
    rows.append(rec)
    _save_day(date, rows)
    _log(f"ADD {rec['bet_id']} date={date}")
    refresh_summaries(date)
    return rec


def update_bet(date: str, bet_id: str, patch: Dict[str, Any]) -> Dict[str, Any] | None:
    rows = _load_day(date)
    found = None
    for r in rows:
        if r.get("bet_id") == bet_id:
            r.update(patch)
            r["updated_at"] = datetime.utcnow().isoformat() + "Z"
            found = r
            break
    if found is None:
        return None
    _save_day(date, rows)
    _log(f"UPDATE {bet_id} date={date}")
    refresh_summaries(date)
    return found


def void_bet(date: str, bet_id: str, reason: str = "") -> Dict[str, Any] | None:
    return update_bet(date, bet_id, {
        "bet_status": "VOID",
        "settlement_result": "PUSH",
        "gross_pnl": 0,
        "rebate": 0,
        "net_pnl": 0,
        "notes": reason,
    })


def settle_bet(date: str, bet_id: str, settlement_patch: Dict[str, Any]) -> Dict[str, Any] | None:
    return update_bet(date, bet_id, settlement_patch)


def day_summary(date: str) -> Dict[str, Any]:
    rows = _load_day(date)
    bet_rows = _effective_bet_rows(rows)
    settled = [r for r in bet_rows if str(r.get("settlement_result") or "").upper() not in {"PENDING"}]
    stake_amount = sum(float(r.get("stake") or 0) for r in bet_rows)
    settled_fin = [_calc_financials(r) for r in settled]
    gross = sum(x["gross_pnl"] for x in settled_fin)
    effective_turnover = sum(x["effective_turnover"] for x in settled_fin)
    rebate = sum(x["rebate"] for x in settled_fin)
    net = sum(x["net_pnl"] for x in settled_fin)
    roi = (net / stake_amount) if stake_amount else None
    betting_roi = (gross / stake_amount) if stake_amount else None
    effective_roi = (net / effective_turnover) if effective_turnover else None

    by_grade = {}
    by_line = {}
    for key, bucket_name in (("v4_grade", by_grade), ("market_line", by_line)):
        buckets = {}
        for r in settled:
            g = r.get(key) or "UNKNOWN"
            f = _calc_financials(r)
            b = buckets.setdefault(g, {"count": 0, "stake_amount": 0.0, "gross_pnl": 0.0, "effective_turnover": 0.0, "rebate": 0.0, "net_pnl": 0.0})
            b["count"] += 1
            b["stake_amount"] += f["stake_amount"]
            b["gross_pnl"] += f["gross_pnl"]
            b["effective_turnover"] += f["effective_turnover"]
            b["rebate"] += f["rebate"]
            b["net_pnl"] += f["net_pnl"]
        for g, b in buckets.items():
            b["roi"] = (b["net_pnl"] / b["stake_amount"]) if b["stake_amount"] else None
            b["roi_pct"] = round((b["roi"] * 100.0), 4) if b["roi"] is not None else None
        bucket_name.update(buckets)

    return {
        "date": date,
        "initial_bankroll": 30000,
        "today_stake_amount": round(stake_amount, 4),
        "today_turnover": round(stake_amount, 4),  # backward compatibility
        "today_gross_pnl": round(gross, 4),
        "today_effective_turnover": round(effective_turnover, 4),
        "today_rebate": round(rebate, 4),
        "today_net_pnl": round(net, 4),
        "today_roi": round(roi, 6) if roi is not None else None,
        "today_roi_pct": round((roi * 100.0), 4) if roi is not None else None,
        "today_betting_roi": round(betting_roi, 6) if betting_roi is not None else None,
        "today_betting_roi_pct": round((betting_roi * 100.0), 4) if betting_roi is not None else None,
        "today_effective_roi": round(effective_roi, 6) if effective_roi is not None else None,
        "today_effective_roi_pct": round((effective_roi * 100.0), 4) if effective_roi is not None else None,
        "records": len(rows),
        "settled_records": len(settled),
        "effective_bet_records": len(bet_rows),
        "excluded_test_records": sum(1 for r in rows if _is_test_record(r)),
        "risk_status_base": "today_gross_pnl",
        "rebate_formula_version": "effective_turnover_v1",
        "recalculated_by": "tools/live_bet_store.py::day_summary",
        "by_grade": by_grade,
        "by_line": by_line,
    }


def cumulative_summary() -> Dict[str, Any]:
    files = sorted(LIVE_DIR.glob("v4_live_bets_*.jsonl"))
    all_rows = []
    for p in files:
        all_rows.extend(_load_day(p.stem.split("_")[-1]))
    bet_rows = _effective_bet_rows(all_rows)
    settled = [r for r in bet_rows if str(r.get("settlement_result") or "").upper() not in {"PENDING"}]
    stake_amount = sum(float(r.get("stake") or 0) for r in bet_rows)
    settled_fin = [_calc_financials(r) for r in settled]
    gross = sum(x["gross_pnl"] for x in settled_fin)
    effective_turnover = sum(x["effective_turnover"] for x in settled_fin)
    rebate = sum(x["rebate"] for x in settled_fin)
    net = sum(x["net_pnl"] for x in settled_fin)
    roi = (net / stake_amount) if stake_amount else None
    return {
        "initial_bankroll": 30000,
        "current_bankroll": round(30000 + net, 4),
        "cumulative_stake_amount": round(stake_amount, 4),
        "cumulative_stake": round(stake_amount, 4),  # backward compatibility
        "cumulative_turnover": round(stake_amount, 4),  # backward compatibility
        "cumulative_gross_pnl": round(gross, 4),
        "cumulative_effective_turnover": round(effective_turnover, 4),
        "cumulative_rebate": round(rebate, 4),
        "cumulative_net_pnl": round(net, 4),
        "cumulative_roi": round(roi, 6) if roi is not None else None,
        "cumulative_roi_pct": round((roi * 100.0), 4) if roi is not None else None,
        "records": len(all_rows),
        "settled_records": len(settled),
        "effective_bet_records": len(bet_rows),
        "excluded_test_records": sum(1 for r in all_rows if _is_test_record(r)),
        "rebate_formula_version": "effective_turnover_v1",
        "recalculated_by": "tools/live_bet_store.py::cumulative_summary",
    }


def refresh_summaries(date: str) -> None:
    ds = day_summary(date)
    _daily_summary_file(date).write_text(json.dumps(ds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cs = cumulative_summary()
    _cum_file().write_text(json.dumps(cs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_day_records(date: str):
    return _load_day(date)


def mark_existing_test_records(date: str | None = None) -> Dict[str, Any]:
    touched = 0
    files = [_day_file(date)] if date else sorted(LIVE_DIR.glob("v4_live_bets_*.jsonl"))
    for fp in files:
        if not fp.exists():
            continue
        day = fp.stem.split("_")[-1]
        rows = _load_day(day)
        changed = False
        for r in rows:
            if _is_test_record(r) and not bool(r.get("is_test")):
                r["is_test"] = True
                r["updated_at"] = datetime.utcnow().isoformat() + "Z"
                changed = True
                touched += 1
        if changed:
            _save_day(day, rows)
            _log(f"MARK_TEST date={day} touched={touched}")
    if date:
        refresh_summaries(date)
    else:
        # refresh all available date summaries and cumulative
        for fp in files:
            if fp.exists():
                d = fp.stem.split("_")[-1]
                ds = day_summary(d)
                _daily_summary_file(d).write_text(json.dumps(ds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _cum_file().write_text(json.dumps(cumulative_summary(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"touched": touched}
