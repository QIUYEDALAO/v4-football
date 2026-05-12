from __future__ import annotations

from typing import Callable, Optional


def _safe_rows(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    rows = resp.get("response")
    return rows if isinstance(rows, list) else []


def fetch_live_odds_paged(fixture_id: int, api_get: Callable[[str], Optional[dict]]) -> dict:
    first = api_get(f"odds/live?fixture={fixture_id}&page=1") or {}
    responses = []
    responses.extend(_safe_rows(first))
    paging = first.get("paging") if isinstance(first, dict) else {}
    total_pages = int((paging or {}).get("total") or 1)

    for p in range(2, total_pages + 1):
        nxt = api_get(f"odds/live?fixture={fixture_id}&page={p}") or {}
        responses.extend(_safe_rows(nxt))

    merged = dict(first) if isinstance(first, dict) else {}
    merged["response"] = responses
    merged["paging"] = {"current": 1, "total": total_pages}
    return merged


def fetch_fixture_state(fixture_id: int, api_get: Callable[[str], Optional[dict]]) -> Optional[dict]:
    resp = api_get(f"fixtures?id={fixture_id}")
    rows = _safe_rows(resp)
    return rows[0] if rows else None


def fetch_fixture_events(fixture_id: int, api_get: Callable[[str], Optional[dict]]) -> dict:
    return api_get(f"fixtures/events?fixture={fixture_id}") or {}


def fetch_fixture_statistics(fixture_id: int, api_get: Callable[[str], Optional[dict]]) -> dict:
    return api_get(f"fixtures/statistics?fixture={fixture_id}") or {}
