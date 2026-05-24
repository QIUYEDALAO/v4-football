#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple
import uuid

ALLOWED_GRADES = {"A", "B", "C", "SKIP"}
ALLOWED_MARKET_LINES = {"O0.75", "O1", "O1.25", "O1.5"}
ALLOWED_SETTLEMENT = {"WIN", "HALF_WIN", "PUSH", "HALF_LOSS", "LOSS", "PENDING"}
ALLOWED_BET_STATUS = {"BET", "NO_BET", "VOID"}
ALLOWED_SOURCE = {"official_57", "outside_57_observation", "manual"}

DEFAULT_BANKROLL = 30000.0
DEFAULT_REBATE_RATE = 0.025


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def default_stake(grade: str, market_line: str) -> float:
    grade = (grade or "").upper()
    market_line = market_line or ""
    mapping = {
        ("A", "O0.75"): 300,
        ("A", "O1"): 250,
        ("A", "O1.25"): 150,
        ("A", "O1.5"): 0,
        ("B", "O0.75"): 150,
        ("B", "O1"): 120,
        ("B", "O1.25"): 0,
        ("B", "O1.5"): 0,
    }
    return float(mapping.get((grade, market_line), 0))


def build_default_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    grade = str(payload.get("v4_grade") or "B").upper()
    line = str(payload.get("market_line") or "O1")
    stake = float(payload.get("stake") or default_stake(grade, line))
    now = now_iso()
    return {
        "bet_id": payload.get("bet_id") or f"bet_{uuid.uuid4().hex[:12]}",
        "date": str(payload.get("date") or datetime.utcnow().strftime("%Y%m%d")),
        "fixture_id": payload.get("fixture_id"),
        "league": payload.get("league") or "",
        "home_cn": payload.get("home_cn") or "",
        "away_cn": payload.get("away_cn") or "",
        "home_en": payload.get("home_en") or "",
        "away_en": payload.get("away_en") or "",
        "kickoff_time": payload.get("kickoff_time") or "",
        "v4_grade": grade,
        "v4_script": payload.get("v4_script") or "",
        "ht_model_score": payload.get("ht_model_score"),
        "official_source": payload.get("official_source") or "manual",
        "bet_status": payload.get("bet_status") or "BET",
        "no_bet_reason": payload.get("no_bet_reason") or "",
        "entry_minute": payload.get("entry_minute"),
        "score_at_entry": payload.get("score_at_entry") or "",
        "market_line": line,
        "odds_water": float(payload.get("odds_water") or 0),
        "stake": stake,
        "ht_score": payload.get("ht_score") or "",
        "ht_goal_count": payload.get("ht_goal_count"),
        "settlement_result": payload.get("settlement_result") or "PENDING",
        "gross_pnl": float(payload.get("gross_pnl") or 0),
        "rebate_rate": float(payload.get("rebate_rate") or DEFAULT_REBATE_RATE),
        "rebate": float(payload.get("rebate") or 0),
        "net_pnl": float(payload.get("net_pnl") or 0),
        "bankroll_before": float(payload.get("bankroll_before") or DEFAULT_BANKROLL),
        "bankroll_after": float(payload.get("bankroll_after") or DEFAULT_BANKROLL),
        "notes": payload.get("notes") or "",
        "created_at": payload.get("created_at") or now,
        "updated_at": now,
    }


def validate_record(rec: Dict[str, Any]) -> Tuple[bool, str]:
    if rec.get("v4_grade") not in ALLOWED_GRADES:
        return False, "invalid v4_grade"
    if rec.get("market_line") not in ALLOWED_MARKET_LINES:
        return False, "invalid market_line"
    if rec.get("settlement_result") not in ALLOWED_SETTLEMENT:
        return False, "invalid settlement_result"
    if rec.get("bet_status") not in ALLOWED_BET_STATUS:
        return False, "invalid bet_status"
    if rec.get("official_source") not in ALLOWED_SOURCE:
        return False, "invalid official_source"
    try:
        float(rec.get("odds_water"))
        float(rec.get("stake"))
        float(rec.get("rebate_rate"))
    except Exception:
        return False, "numeric field parse error"
    return True, "OK"
