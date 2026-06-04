#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_SOURCE = ROOT / "data/v3_wc2026/group_schedule.json"
DEFAULT_OUT_DIR = ROOT / "data/runtime/v3_worldcup/odds_snapshot_dryrun/20260604"
DEFAULT_FREE_PLAN_REQUEST_LIMIT = 80

TIMELINE_FIELDS = [
    "snapshot_time",
    "api_update_time",
    "fixture_id",
    "year",
    "home",
    "away",
    "bookmaker",
    "market_type",
    "market_name_raw",
    "selection",
    "line",
    "odds",
    "source",
    "is_current_snapshot",
    "has_native_opening",
    "has_native_closing",
    "movement_requires_timeline",
]

SAFETY_FIELDS = [
    "observation_only",
    "betting_recommendation",
    "affects_v4",
    "scoring_changed",
    "dry_run_sample",
]

MARKET_ALIASES = {
    "MATCH_WINNER_1X2": {
        "1x2",
        "match winner",
        "winner",
        "home/draw/away",
        "full time result",
    },
    "ASIAN_HANDICAP": {
        "asian handicap",
        "asian handicaps",
        "asian handicap first half",
    },
    "GOALS_OVER_UNDER": {
        "goals over/under",
        "over/under",
        "goals over under",
        "total goals",
        "match goals",
    },
    "BOTH_TEAMS_TO_SCORE": {
        "btts",
        "both teams score",
        "both teams to score",
        "both teams scoring",
    },
    "DOUBLE_CHANCE": {
        "double chance",
    },
    "FIRST_HALF_WINNER": {
        "1st half winner",
        "first half winner",
        "1st half result",
        "half time result",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_fixtures(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        fixtures = data.get("fixtures") or data.get("response") or []
    else:
        fixtures = data
    if not isinstance(fixtures, list):
        raise ValueError(f"fixture source is not a list: {path}")
    return [f for f in fixtures if isinstance(f, dict)]


def _fixture_id(fixture: dict[str, Any]) -> str:
    raw = fixture.get("fixture_id") or fixture.get("id")
    if isinstance(raw, dict):
        raw = raw.get("id")
    return str(raw or "").strip()


def _team_name(fixture: dict[str, Any], side: str) -> str:
    candidates = [
        f"{side}_team",
        side,
        f"{side}_name",
    ]
    teams = fixture.get("teams")
    if isinstance(teams, dict) and isinstance(teams.get(side), dict):
        candidates.append(("teams", side, "name"))  # type: ignore[arg-type]
    for key in candidates:
        if isinstance(key, tuple):
            value = fixture.get(key[0], {}).get(key[1], {}).get(key[2])
        else:
            value = fixture.get(key)
        if value:
            return str(value)
    return side.upper()


def select_fixtures(fixtures: list[dict[str, Any]], fixture_ids: list[str], limit: int) -> list[dict[str, Any]]:
    wanted = {str(x).strip() for x in fixture_ids if str(x).strip()}
    selected = [f for f in fixtures if not wanted or _fixture_id(f) in wanted]
    if limit >= 0:
        selected = selected[:limit]
    return selected


def normalize_market_name(raw: str) -> str:
    value = re.sub(r"\s+", " ", str(raw or "").strip().lower())
    for normalized, aliases in MARKET_ALIASES.items():
        if value in aliases:
            return normalized
    if "asian" in value and "handicap" in value:
        return "ASIAN_HANDICAP"
    if ("over" in value and "under" in value) or "total goals" in value:
        return "GOALS_OVER_UNDER"
    if "both teams" in value or value == "btts":
        return "BOTH_TEAMS_TO_SCORE"
    if "double chance" in value:
        return "DOUBLE_CHANCE"
    if "half" in value and ("winner" in value or "result" in value):
        return "FIRST_HALF_WINNER"
    if value in {"1x2", "match winner"} or "winner" in value:
        return "MATCH_WINNER_1X2"
    return "OTHER_MARKET"


def extract_line(selection: str, market_type: str) -> str:
    if market_type not in {"ASIAN_HANDICAP", "GOALS_OVER_UNDER"}:
        return ""
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(selection or ""))
    return match.group(0) if match else ""


def _sample_bets() -> list[dict[str, Any]]:
    return [
        {
            "name": "Match Winner",
            "values": [
                {"value": "Home", "odd": "2.10"},
                {"value": "Draw", "odd": "3.20"},
                {"value": "Away", "odd": "3.50"},
            ],
        },
        {
            "name": "Asian Handicap",
            "values": [
                {"value": "Home -0.25", "odd": "1.92"},
                {"value": "Away +0.25", "odd": "1.88"},
            ],
        },
        {
            "name": "Goals Over/Under",
            "values": [
                {"value": "Over 2.5", "odd": "1.95"},
                {"value": "Under 2.5", "odd": "1.85"},
            ],
        },
        {
            "name": "BTTS",
            "values": [
                {"value": "Yes", "odd": "1.90"},
                {"value": "No", "odd": "1.90"},
            ],
        },
        {
            "name": "Double Chance",
            "values": [
                {"value": "1X", "odd": "1.35"},
                {"value": "12", "odd": "1.28"},
                {"value": "X2", "odd": "1.72"},
            ],
        },
        {
            "name": "1st Half Winner",
            "values": [
                {"value": "Home", "odd": "2.70"},
                {"value": "Draw", "odd": "2.05"},
                {"value": "Away", "odd": "4.20"},
            ],
        },
    ]


def dry_run_payload_for_fixture(fixture: dict[str, Any], snapshot_time: str) -> dict[str, Any]:
    return {
        "get": "odds",
        "parameters": {"fixture": _fixture_id(fixture)},
        "response": [
            {
                "fixture": {
                    "id": int(_fixture_id(fixture)),
                    "date": fixture.get("date"),
                },
                "update": snapshot_time,
                "bookmakers": [
                    {
                        "id": 0,
                        "name": "API-Football Dry Run Template",
                        "bets": _sample_bets(),
                    }
                ],
            }
        ],
    }


def fetch_live_payload(fixture_id: str) -> dict[str, Any] | None:
    from engine.net_utils import api_get  # imported only for explicit live mode

    return api_get(f"odds?fixture={fixture_id}", retries=0)


def records_from_payload(payload: dict[str, Any], fixture: dict[str, Any], snapshot_time: str, *, dry_run: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    response = payload.get("response") if isinstance(payload, dict) else []
    if not isinstance(response, list):
        return records
    year = str(fixture.get("date") or "")[:4] or "2026"
    home = _team_name(fixture, "home")
    away = _team_name(fixture, "away")
    for item in response:
        if not isinstance(item, dict):
            continue
        api_update_time = str(item.get("update") or snapshot_time)
        bookmakers = item.get("bookmakers") or []
        if not isinstance(bookmakers, list):
            continue
        for bookmaker in bookmakers:
            if not isinstance(bookmaker, dict):
                continue
            bookmaker_name = str(bookmaker.get("name") or "UNKNOWN_BOOKMAKER")
            bets = bookmaker.get("bets") or []
            if not isinstance(bets, list):
                continue
            for market in bets:
                if not isinstance(market, dict):
                    continue
                raw_name = str(market.get("name") or "")
                market_type = normalize_market_name(raw_name)
                values = market.get("values") or []
                if not isinstance(values, list):
                    continue
                for value in values:
                    if not isinstance(value, dict):
                        continue
                    selection = str(value.get("value") or "")
                    row = {
                        "snapshot_time": snapshot_time,
                        "api_update_time": api_update_time,
                        "fixture_id": _fixture_id(fixture),
                        "year": year,
                        "home": home,
                        "away": away,
                        "bookmaker": bookmaker_name,
                        "market_type": market_type,
                        "market_name_raw": raw_name,
                        "selection": selection,
                        "line": extract_line(selection, market_type),
                        "odds": str(value.get("odd") or ""),
                        "source": "API_FOOTBALL_DRY_RUN_TEMPLATE" if dry_run else "API_FOOTBALL_ODDS_SNAPSHOT",
                        "is_current_snapshot": True,
                        "has_native_opening": False,
                        "has_native_closing": False,
                        "movement_requires_timeline": True,
                        "observation_only": True,
                        "betting_recommendation": False,
                        "affects_v4": False,
                        "scoring_changed": False,
                        "dry_run_sample": bool(dry_run),
                    }
                    records.append(row)
    return records


def write_outputs(out_dir: Path, payload: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "v3_worldcup_odds_snapshot_dryrun_20260604.json"
    csv_path = out_dir / "v3_worldcup_odds_snapshot_timeline_20260604.csv"
    payload = dict(payload)
    payload["records"] = records
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = TIMELINE_FIELDS + SAFETY_FIELDS
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return {"json": str(json_path), "csv": str(csv_path)}


def parse_fixture_ids(values: list[str]) -> list[str]:
    ids: list[str] = []
    for item in values:
        ids.extend(x.strip() for x in str(item).split(",") if x.strip())
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="V3 World Cup odds snapshot timeline foundation dry-run")
    parser.add_argument("--fixture-source", default=str(DEFAULT_FIXTURE_SOURCE))
    parser.add_argument("--fixture-id", action="append", default=[], help="Fixture id, repeatable or comma-separated")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_FREE_PLAN_REQUEST_LIMIT)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--live", action="store_true", help="Explicitly call API-Football odds endpoint")
    args = parser.parse_args()

    fixture_source = Path(args.fixture_source)
    fixtures = _load_fixtures(fixture_source)
    fixture_ids = parse_fixture_ids(args.fixture_id)
    selected = select_fixtures(fixtures, fixture_ids, args.limit)
    request_limit = min(int(args.max_requests), DEFAULT_FREE_PLAN_REQUEST_LIMIT)
    planned_requests = len(selected)
    snapshot_time = _now()
    dry_run = not bool(args.live)

    quota_warning = ""
    status = "DRY_RUN_READY" if dry_run else "LIVE_SNAPSHOT_READY"
    records: list[dict[str, Any]] = []
    api_errors: list[dict[str, Any]] = []

    if planned_requests > request_limit:
        quota_warning = (
            f"quota_guard_stop: planned_requests={planned_requests} exceeds "
            f"request_limit={request_limit}; no remote request executed"
        )
        status = "QUOTA_GUARD_STOP"
    else:
        for fixture in selected:
            if dry_run:
                payload = dry_run_payload_for_fixture(fixture, snapshot_time)
            else:
                payload = fetch_live_payload(_fixture_id(fixture))
                if not payload:
                    api_errors.append({"fixture_id": _fixture_id(fixture), "reason": "API_FOOTBALL_ODDS_EMPTY_OR_BLOCKED"})
                    continue
            records.extend(records_from_payload(payload, fixture, snapshot_time, dry_run=dry_run))

    normalized_market_types = sorted({str(r["market_type"]) for r in records})
    result = {
        "schema_version": "v3_worldcup_odds_snapshot_timeline_foundation.v1",
        "generated_at": snapshot_time,
        "status": status,
        "dry_run": dry_run,
        "fixture_source": str(fixture_source),
        "fixture_count_available": len(fixtures),
        "fixture_count_selected": len(selected),
        "fixture_ids_selected": [_fixture_id(f) for f in selected],
        "quota": {
            "plan": "FREE_DEFAULT",
            "default_free_plan_limit": DEFAULT_FREE_PLAN_REQUEST_LIMIT,
            "configured_max_requests": int(args.max_requests),
            "effective_request_limit": request_limit,
            "planned_requests": planned_requests,
            "remote_requests_executed": 0 if dry_run or status == "QUOTA_GUARD_STOP" else planned_requests - len(api_errors),
            "quota_warning": quota_warning,
        },
        "timeline_schema": TIMELINE_FIELDS,
        "normalized_market_types": normalized_market_types,
        "standardized_markets_required": sorted(MARKET_ALIASES),
        "safety": {
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4": False,
            "scoring_changed": False,
            "no_native_opening": True,
            "no_native_closing": True,
            "movement_requires_timeline": True,
            "secret_printed": False,
        },
        "api_errors": api_errors,
    }
    paths = write_outputs(Path(args.out_dir), result, records)
    result["outputs"] = paths
    Path(paths["json"]).write_text(json.dumps({**result, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "records": len(records), "quota_warning": quota_warning, "outputs": paths}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
