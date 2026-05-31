from __future__ import annotations

import re
from typing import Any

BOOKMAKER_PRIORITY = [
    "Pinnacle",
    "Bet365",
    "William Hill",
    "10Bet",
    "Marathonbet",
    "1xBet",
    "Betfair",
]

_PRIORITY_INDEX = {name.lower(): idx + 1 for idx, name in enumerate(BOOKMAKER_PRIORITY)}

_HT_TOKENS = ("first half", "1st half", "half time", "ht", "1h")
_OU_TOKENS = ("over/under", "over under", "over", "under", "goals")
_BLOCKED_FULLTIME_TOKENS = (
    "full time",
    "match goals",
    "total goals",
    "goals over/under",
    "over/under (match)",
)


def _to_num(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        # Some feeds encode decimal odds as 67 => 1.67, 26 => 1.26.
        if 10.0 <= x < 1000.0:
            x = 1.0 + (x / 100.0)
        return x
    except Exception:
        return None


def _is_ht_ou_bet_name(bet_name: str) -> bool:
    s = str(bet_name or "").strip().lower()
    if not s:
        return False
    if not any(t in s for t in _HT_TOKENS):
        return False
    if any(t in s for t in _BLOCKED_FULLTIME_TOKENS):
        return False
    if not any(t in s for t in _OU_TOKENS):
        return False
    return True


def _extract_lines_from_bet(values: list[dict]) -> list[dict[str, float | str | None]]:
    line_map: dict[str, dict[str, float | None]] = {}
    for v in values or []:
        val_str = str(v.get("value", "") or "")
        odd_val = _to_num(v.get("odd"))
        nums = re.findall(r"[\d.]+", val_str)
        line_num = nums[0] if nums else val_str.strip()
        if not line_num:
            continue
        entry = line_map.setdefault(line_num, {"over": None, "under": None})
        low = val_str.lower()
        if "over" in low:
            entry["over"] = odd_val
        elif "under" in low:
            entry["under"] = odd_val
        else:
            if entry["over"] is None:
                entry["over"] = odd_val
            else:
                entry["under"] = odd_val

    def _sort_key(k: str):
        try:
            return float(k)
        except Exception:
            return 9999.0

    out: list[dict[str, float | str | None]] = []
    for line_num in sorted(line_map.keys(), key=_sort_key):
        entry = line_map[line_num]
        out.append({"line": line_num, "over": entry["over"], "under": entry["under"]})
    return out


def capture_ht_ou_snapshot(odds_resp: dict | None) -> dict[str, Any]:
    """
    Capture HT OU lines with bookmaker fallback.

    Returns:
      ht_ou_lines: list[{line, over, under}]
      bookmaker_used: str
      bookmaker_priority: int
      market_name: str
      bet_name: str
      market_source: PINNACLE_PRIMARY / BOOKMAKER_FALLBACK / NO_HT_OU / NO_ODDS
      no_ht_ou_reason: str
      bookmaker_count: int
      ht_ou_detected: bool
    """
    if not odds_resp or not odds_resp.get("response"):
        return {
            "ht_ou_lines": [],
            "bookmaker_used": "",
            "bookmaker_priority": 0,
            "market_name": "",
            "bet_name": "",
            "market_source": "NO_ODDS",
            "no_ht_ou_reason": "NO_ODDS_RESPONSE",
            "bookmaker_count": 0,
            "ht_ou_detected": False,
        }

    first = (odds_resp.get("response") or [{}])[0] or {}
    bookmakers = first.get("bookmakers") or []
    if not bookmakers:
        return {
            "ht_ou_lines": [],
            "bookmaker_used": "",
            "bookmaker_priority": 0,
            "market_name": "",
            "bet_name": "",
            "market_source": "NO_ODDS",
            "no_ht_ou_reason": "NO_BOOKMAKER_DATA",
            "bookmaker_count": 0,
            "ht_ou_detected": False,
        }

    candidates: list[dict[str, Any]] = []
    for idx, bo in enumerate(bookmakers):
        bo_name = str(bo.get("name", "") or "")
        bo_name_key = bo_name.lower()
        bo_priority = _PRIORITY_INDEX.get(bo_name_key, 100 + idx)
        bets = bo.get("bets") or []
        for bet in bets:
            bet_name = str(bet.get("name", "") or "")
            if not _is_ht_ou_bet_name(bet_name):
                continue
            lines = _extract_lines_from_bet(bet.get("values") or [])
            if not lines:
                continue
            candidates.append(
                {
                    "bookmaker_used": bo_name,
                    "bookmaker_priority": bo_priority,
                    "market_name": bet_name,
                    "bet_name": bet_name,
                    "ht_ou_lines": lines,
                }
            )

    if not candidates:
        return {
            "ht_ou_lines": [],
            "bookmaker_used": "",
            "bookmaker_priority": 0,
            "market_name": "",
            "bet_name": "",
            "market_source": "NO_HT_OU",
            "no_ht_ou_reason": "API_HAS_ODDS_BUT_NO_HT_OU",
            "bookmaker_count": len(bookmakers),
            "ht_ou_detected": False,
        }

    candidates.sort(key=lambda x: int(x["bookmaker_priority"]))
    chosen = candidates[0]
    used = str(chosen["bookmaker_used"] or "")
    source = "PINNACLE_PRIMARY" if used.lower() == "pinnacle" else "BOOKMAKER_FALLBACK"
    return {
        "ht_ou_lines": chosen["ht_ou_lines"],
        "bookmaker_used": used,
        "bookmaker_priority": int(chosen["bookmaker_priority"]),
        "market_name": str(chosen["market_name"] or ""),
        "bet_name": str(chosen["bet_name"] or ""),
        "market_source": source,
        "no_ht_ou_reason": "",
        "bookmaker_count": len(bookmakers),
        "ht_ou_detected": True,
    }
