#!/usr/bin/env python3
"""Run a small api-football data-completeness smoke for V4 research cards.

This is not a V4 daily scan. It only samples a few whitelisted fixtures, writes
raw API payloads to gitignored runtime, and emits a compact coverage summary.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_v4_five_dimension_lite import sample_from_row
from tools.build_v4_market_strategy_research_cards import card_from_five_dimension


API_BASE = "https://v3.football.api-sports.io"
SECRET_ENV = Path.home() / ".openclaw/secrets/v4_daily_scan.env"
OUT_DIR = ROOT / "data/runtime/v4_research_card_smoke"
RAW_DIR = OUT_DIR / "raw"
SUMMARY = OUT_DIR / "v4_research_card_data_completeness_smoke_summary_20260607.json"
SAMPLES = OUT_DIR / "v4_research_card_data_completeness_smoke_samples_20260607.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

LEAGUE_PLAN = [
    {"league_id": 98, "league_name": "J1 League", "season": 2026, "admission_group": "INCLUDE_CURRENT"},
    {"league_id": 169, "league_name": "CSL", "season": 2026, "admission_group": "INCLUDE_CURRENT"},
    {"league_id": 71, "league_name": "Serie A Brazil", "season": 2026, "admission_group": "INCLUDE_CURRENT"},
    {"league_id": 144, "league_name": "Belgian Pro League", "season": 2025, "admission_group": "INCLUDE_CURRENT"},
    {"league_id": 2, "league_name": "UCL", "season": 2025, "admission_group": "INCLUDE_CURRENT"},
]

REQUIRED_MARKETS = {
    "1X2": ("MATCH WINNER", "1X2"),
    "FT_OU": ("GOALS OVER/UNDER", "OVER/UNDER", "TOTAL GOALS"),
    "AH_OR_HANDICAP": ("ASIAN HANDICAP", "HANDICAP"),
    "DOUBLE_CHANCE": ("DOUBLE CHANCE",),
}
FORBIDDEN_TEXT_RE = re.compile(
    r"推荐|投注|下注|实单|必中|稳胆|资金流|steam|drift|sharp|betting signal|must bet",
    re.IGNORECASE,
)


def load_key() -> str:
    key = os.environ.get("APIFOOTBALL_KEY") or os.environ.get("OPENCLAW_APIFOOTBALL_KEY") or ""
    if key:
        return key.strip()
    if SECRET_ENV.exists():
        for line in SECRET_ENV.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            name, value = raw.split("=", 1)
            name = name.strip()
            if name.startswith("export "):
                name = name.split(None, 1)[1].strip()
            clean = value.strip().strip('"').strip("'")
            if name == "APIFOOTBALL_KEY" and clean:
                return clean
            if name == "OPENCLAW_APIFOOTBALL_KEY" and clean:
                key = clean
    return key.strip()


def api_get(endpoint: str, params: dict[str, Any], key: str) -> dict[str, Any]:
    url = f"{API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"x-apisports-key": key})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    time.sleep(0.25)
    return payload


def write_raw(name: str, payload: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def response_list(payload: dict[str, Any]) -> list[Any]:
    response = payload.get("response")
    return response if isinstance(response, list) else []


def find_fixtures(key: str, limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()
    for league in LEAGUE_PLAN:
        payload = api_get("fixtures", {"league": league["league_id"], "season": league["season"], "next": 5}, key)
        write_raw(f"fixtures_league_{league['league_id']}_{league['season']}", payload)
        league_take = 0
        for fixture in response_list(payload):
            fixture_id = ((fixture.get("fixture") or {}).get("id"))
            if not fixture_id or int(fixture_id) in seen:
                continue
            selected.append({"league_plan": league, "fixture": fixture})
            seen.add(int(fixture_id))
            league_take += 1
            if league_take >= 3 or len(selected) >= limit:
                break
        if len(selected) >= limit:
            break
    return selected


def market_type_for(name: str) -> str:
    upper = name.upper()
    for market_type, tokens in REQUIRED_MARKETS.items():
        if any(token in upper for token in tokens):
            return market_type
    return "UNKNOWN"


def line_from_value(value: Any) -> float | None:
    text = str(value or "")
    matches = re.findall(r"[-+]?\d+(?:\.\d+)?", text)
    return float(matches[-1]) if matches else None


def odds_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = response_list(payload)
    bookmakers: list[dict[str, Any]] = []
    for row in rows:
        books = row.get("bookmakers")
        if isinstance(books, list):
            bookmakers.extend(book for book in books if isinstance(book, dict))
    market_counts: Counter[str] = Counter()
    market_raw: set[str] = set()
    price_candidates: list[dict[str, Any]] = []
    line_exists = False
    odds_exists = False
    for book in bookmakers:
        for bet in book.get("bets") or []:
            if not isinstance(bet, dict):
                continue
            bet_name = str(bet.get("name") or "")
            market_type = market_type_for(bet_name)
            market_counts[market_type] += 1
            market_raw.add(bet_name)
            for value in bet.get("values") or []:
                if not isinstance(value, dict):
                    continue
                line = line_from_value(value.get("value"))
                odd = value.get("odd")
                if line is not None and market_type in {"FT_OU", "AH_OR_HANDICAP"}:
                    line_exists = True
                if odd not in (None, ""):
                    odds_exists = True
                if market_type != "UNKNOWN" and odd not in (None, ""):
                    price_candidates.append({
                        "market_type": market_type,
                        "bookmaker": book.get("name") or "",
                        "market": bet_name,
                        "line": line,
                        "odds": odd,
                        "snapshot_time": book.get("update") or BUILD_TIMESTAMP,
                    })
    priority = {"FT_OU": 0, "AH_OR_HANDICAP": 1, "DOUBLE_CHANCE": 2, "1X2": 3}
    price_candidates.sort(
        key=lambda item: (
            item.get("line") is None,
            priority.get(str(item.get("market_type")), 9),
        )
    )
    first_price = price_candidates[0] if price_candidates else {}
    return {
        "bookmaker_count": len({str(book.get("name") or book.get("id")) for book in bookmakers}),
        "market_type_counts": dict(market_counts),
        "market_names_raw": sorted(market_raw),
        "has_1x2": market_counts["1X2"] > 0,
        "has_ft_ou": market_counts["FT_OU"] > 0,
        "has_ah_or_handicap": market_counts["AH_OR_HANDICAP"] > 0,
        "has_double_chance": market_counts["DOUBLE_CHANCE"] > 0,
        "line_exists": line_exists,
        "odds_exists": odds_exists,
        "first_price": first_price,
    }


def has_response(payload: dict[str, Any]) -> bool:
    return bool(response_list(payload))


def build_row(
    fixture_record: dict[str, Any],
    odds: dict[str, Any],
    standings: dict[str, Any],
    home_stats: dict[str, Any],
    away_stats: dict[str, Any],
    lineups: dict[str, Any],
    injuries: dict[str, Any],
    h2h: dict[str, Any],
) -> dict[str, Any]:
    fixture = fixture_record["fixture"]
    league_plan = fixture_record["league_plan"]
    fixture_meta = fixture.get("fixture") or {}
    teams = fixture.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    league = fixture.get("league") or {}
    odds_info = odds_summary(odds)
    price = odds_info["first_price"]
    row = {
        "fixture_id": fixture_meta.get("id"),
        "home": home.get("name") or "",
        "away": away.get("name") or "",
        "league_id": league.get("id") or league_plan["league_id"],
        "league_name": league.get("name") or league_plan["league_name"],
        "league_type": "League",
        "kickoff_time": fixture_meta.get("date") or "",
        "official_grade": "SMOKE_ONLY_NOT_OFFICIAL",
        "standings": response_list(standings),
        "home_team_stats": home_stats.get("response") or {},
        "away_team_stats": away_stats.get("response") or {},
        "lineup": {"status": "PRESENT" if has_response(lineups) else "LINEUP_WAIT_EVENT"},
        "injury_status": "PRESENT" if has_response(injuries) else "INJURY_SOURCE_MISSING",
        "h2h_recent5_sample_count": len(response_list(h2h)),
        "h2h_recent5_support_status": "PRESENT" if has_response(h2h) else "LOW_SAMPLE_OR_MISSING",
        "h2h_low_sample": len(response_list(h2h)) < 3,
        "price_source": "api_football_smoke_runtime" if price else "",
        "bookmaker": price.get("bookmaker", ""),
        "market": price.get("market", ""),
        "line": price.get("line"),
        "odds": price.get("odds"),
        "snapshot_time": price.get("snapshot_time", ""),
        "venue": (fixture_meta.get("venue") or {}).get("name") or "",
        "smoke_field_coverage": {
            "fixtures": True,
            "odds": has_response(odds),
            "standings": has_response(standings),
            "team_statistics": bool(home_stats.get("response") or away_stats.get("response")),
            "lineups": has_response(lineups),
            "injuries": has_response(injuries),
            "h2h": has_response(h2h),
            **{k: odds_info[k] for k in [
                "has_1x2",
                "has_ft_ou",
                "has_ah_or_handicap",
                "has_double_chance",
                "bookmaker_count",
                "line_exists",
                "odds_exists",
            ]},
        },
    }
    return row


def fetch_sample_details(key: str, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in selected:
        fixture = item["fixture"]
        league_plan = item["league_plan"]
        fixture_id = (fixture.get("fixture") or {}).get("id")
        teams = fixture.get("teams") or {}
        home_id = (teams.get("home") or {}).get("id")
        away_id = (teams.get("away") or {}).get("id")
        league_id = league_plan["league_id"]
        season = league_plan["season"]
        odds = api_get("odds", {"fixture": fixture_id}, key)
        standings = api_get("standings", {"league": league_id, "season": season}, key)
        home_stats = api_get("teams/statistics", {"league": league_id, "season": season, "team": home_id}, key)
        away_stats = api_get("teams/statistics", {"league": league_id, "season": season, "team": away_id}, key)
        lineups = api_get("fixtures/lineups", {"fixture": fixture_id}, key)
        injuries = api_get("injuries", {"fixture": fixture_id}, key)
        h2h = api_get("fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": 10}, key)
        stem = f"fixture_{fixture_id}"
        write_raw(f"{stem}_odds", odds)
        write_raw(f"{stem}_standings", standings)
        write_raw(f"{stem}_home_stats", home_stats)
        write_raw(f"{stem}_away_stats", away_stats)
        write_raw(f"{stem}_lineups", lineups)
        write_raw(f"{stem}_injuries", injuries)
        write_raw(f"{stem}_h2h", h2h)
        rows.append(build_row(item, odds, standings, home_stats, away_stats, lineups, injuries, h2h))
    return rows


def aggregate(rows: list[dict[str, Any]], five_samples: list[dict[str, Any]], cards: list[dict[str, Any]]) -> dict[str, Any]:
    conclusion_counts = {label: sum(1 for card in cards if card.get("conclusion") == label) for label in ("OBSERVE", "WAIT", "PASS")}
    missing_counts: Counter[str] = Counter()
    for sample in five_samples:
        missing_counts.update(sample.get("missing_context") or [])
    coverage_counts: Counter[str] = Counter()
    for row in rows:
        coverage = row.get("smoke_field_coverage") or {}
        for key, value in coverage.items():
            if isinstance(value, bool) and value:
                coverage_counts[key] += 1
    return {
        "sample_count": len(rows),
        "conclusion_counts": conclusion_counts,
        "missing_context_counts": dict(sorted(missing_counts.items())),
        "field_coverage_counts": dict(sorted(coverage_counts.items())),
        "still_blocking_observe": sorted(tag for tag, count in missing_counts.items() if count),
    }


def main() -> int:
    key = load_key()
    if not key:
        print(json.dumps({"conclusion": "BLOCKER", "blockers": ["api_key_missing"], "key_present": False}, ensure_ascii=False, indent=2))
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected = find_fixtures(key, 5)
    if len(selected) < 3:
        print(json.dumps({"conclusion": "FAIL", "blockers": ["sample_fixture_count_lt_3"], "sample_count": len(selected)}, ensure_ascii=False, indent=2))
        return 2
    rows = fetch_sample_details(key, selected[:5])
    five_samples = [sample_from_row(row, SUMMARY) for row in rows]
    cards = [card_from_five_dimension(sample) for sample in five_samples]
    payload = {
        "schema_version": "v4_research_card_data_completeness_smoke.v1",
        "generated_at": BUILD_TIMESTAMP,
        "runtime_only": True,
        "live_api_called": True,
        "key_present": True,
        "raw_payload_dir": str(RAW_DIR.relative_to(ROOT)),
        "source_leagues": [
            {
                "league_id": row.get("league_id"),
                "league": row.get("league_name"),
                "fixture_id": row.get("fixture_id"),
                "home": row.get("home"),
                "away": row.get("away"),
            }
            for row in rows
        ],
        "samples": [
            {
                "fixture_id": row.get("fixture_id"),
                "match_info": sample.get("match_info"),
                "field_coverage": row.get("smoke_field_coverage"),
                "five_dimension_conclusion": (sample.get("conclusion_guard") or {}).get("conclusion"),
                "strategy_card_conclusion": card.get("conclusion"),
                "missing_context": sample.get("missing_context"),
                "policy_lock": card.get("policy_lock"),
            }
            for row, sample, card in zip(rows, five_samples, cards)
        ],
        "aggregate": aggregate(rows, five_samples, cards),
        "policy_lock": {
            "official_grade_changed": False,
            "ab_threshold_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "b_realtime_restored": False,
            "rf_shadow_promotion_released": False,
            "not_recommendation": True,
            "not_betting_advice": True,
        },
    }
    SAMPLES.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "schema_version": "v4_research_card_data_completeness_smoke_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "sample_count": len(rows),
        "source_leagues": payload["source_leagues"],
        **payload["aggregate"],
        "policy_lock": payload["policy_lock"],
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    text = json.dumps(payload, ensure_ascii=False)
    if FORBIDDEN_TEXT_RE.search(text):
        print(json.dumps({"conclusion": "BLOCKER", "blockers": ["forbidden_word_in_smoke_payload"]}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({
        "conclusion": "PASS",
        "sample_count": len(rows),
        "summary": str(SUMMARY.relative_to(ROOT)),
        "samples": str(SAMPLES.relative_to(ROOT)),
        "conclusion_counts": summary["conclusion_counts"],
        "missing_context_counts": summary["missing_context_counts"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
