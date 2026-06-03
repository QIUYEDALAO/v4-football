#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260603"
OUT_DIR = ROOT / "data/runtime/v3_worldcup/perception_gap_dryrun"

HISTORICAL_MARKET_SUMMARY = ROOT / "data/runtime/v3_worldcup/historical_market_baseline/20260602/v3_wc4a_historical_market_summary_v1.json"
WC5D_REVIEW_ARTIFACT = ROOT / "data/runtime/v3_worldcup/final_squads/v3_wc5d_candidate_review_artifact_20260602.json"
VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
MATCH_CACHE = ROOT / "data/runtime/v3_worldcup/thestatsapi_cache/20260602/world_cup_2026/matches_2026_all.json"
CACHE_COVERAGE = ROOT / "data/runtime/v3_worldcup/thestatsapi_cache/20260602/reports/v3_thestatsapi_worldcup_cache_coverage.json"

CSV_OUT = OUT_DIR / f"v3_wc4d_match_level_perception_gap_dryrun_{RUN_DATE}.csv"
MD_OUT = OUT_DIR / f"V3_WC4D_MATCH_LEVEL_PERCEPTION_GAP_DRYRUN_{RUN_DATE}.md"
STATUS_OUT = OUT_DIR / f"v3_wc4d_match_level_perception_gap_dryrun_status_{RUN_DATE}.json"

VENUE_SIGNAL_TAGS = {
    "HEAT_STRESS",
    "HUMIDITY_STRESS",
    "ALTITUDE_STRESS",
    "MIDDAY_KICKOFF_RISK",
    "VENUE_UPSET_WATCH",
}

SAMPLES = [
    {
        "sample_id": "WC4D-HUMID-001",
        "match_id": "mt_641915383",
        "venue": "Hard Rock Stadium",
        "sample_priority": "高温高湿场馆 + 热门强队",
        "popular_strong_team": "Brazil",
    },
    {
        "sample_id": "WC4D-ALTITUDE-001",
        "match_id": "mt_153637999",
        "venue": "Estadio Azteca",
        "sample_priority": "高原场馆 + 东道主场景",
        "popular_strong_team": "Mexico",
    },
    {
        "sample_id": "WC4D-ORDINARY-001",
        "match_id": "mt_732525756",
        "venue": "AT&T Stadium",
        "sample_priority": "普通/低压力场馆 + 候选资料较完整",
        "popular_strong_team": "Belgium",
    },
    {
        "sample_id": "WC4D-POPULAR-001",
        "match_id": "mt_028383092",
        "venue": "Arrowhead Stadium",
        "sample_priority": "热门强队场次 + 午间压力观察",
        "popular_strong_team": "England",
    },
    {
        "sample_id": "WC4D-MIXED-001",
        "match_id": "mt_209798011",
        "venue": "Estadio Akron",
        "sample_priority": "高原/湿度混合压力 + 强队对话",
        "popular_strong_team": "Spain",
    },
]


def _load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return obj


def _team_quality(team_name: str, team_by_name: dict[str, dict[str, Any]]) -> tuple[str, str]:
    info = team_by_name.get(team_name)
    if not info:
        return "TEAM_CACHE_MISSING", f"{team_name}: candidate review cache missing"
    status = str(info.get("candidate_status") or "UNKNOWN")
    safe = bool(info.get("safe_for_candidate_review"))
    hold = str(info.get("hold_reason") or "").strip()
    if safe:
        return "CANDIDATE_REVIEW_OK", f"{team_name}: {status}"
    note = f"{team_name}: {status}"
    if hold:
        note = f"{note}; {hold}"
    return "CANDIDATE_REVIEW_HOLD", note


def _squad_quality(home: str, away: str, team_by_name: dict[str, dict[str, Any]]) -> tuple[str, str]:
    home_quality, home_note = _team_quality(home, team_by_name)
    away_quality, away_note = _team_quality(away, team_by_name)
    qualities = {home_quality, away_quality}
    if "TEAM_CACHE_MISSING" in qualities:
        combined = "SQUAD_DATA_INSUFFICIENT"
    elif "CANDIDATE_REVIEW_HOLD" in qualities:
        combined = "SQUAD_REVIEW_HOLD"
    else:
        combined = "SQUAD_CANDIDATE_REVIEW_OK"
    return combined, f"{home_note} | {away_note}"


def _venue_stress_tag(venue: dict[str, Any]) -> str:
    tags = venue.get("stress_tags") if isinstance(venue.get("stress_tags"), list) else []
    active = [str(tag) for tag in tags if str(tag) in VENUE_SIGNAL_TAGS]
    return ";".join(active or ["WATCH_ONLY"])


def _data_insufficient_reason(match: dict[str, Any], squad_quality: str) -> str:
    reasons: list[str] = []
    if match.get("odds_available") is not True:
        reasons.append("current_market_or_api_odds_cache_missing")
    if match.get("xg_available") is not True:
        reasons.append("api_prediction_or_xg_cache_missing")
    if squad_quality != "SQUAD_CANDIDATE_REVIEW_OK":
        reasons.append("candidate_squad_requires_review_or_team_cache_missing")
    reasons.extend(["official_final_squad_not_confirmed", "starting_xi_not_available"])
    return ";".join(dict.fromkeys(reasons))


def build_rows() -> tuple[list[dict[str, str]], dict[str, Any]]:
    historical = _load(HISTORICAL_MARKET_SUMMARY)
    candidate = _load(WC5D_REVIEW_ARTIFACT)
    venue_payload = _load(VENUE_STRESS)
    match_payload = _load(MATCH_CACHE)
    coverage = _load(CACHE_COVERAGE)

    teams = candidate.get("teams") if isinstance(candidate.get("teams"), list) else []
    venues = venue_payload.get("venues") if isinstance(venue_payload.get("venues"), list) else []
    matches = match_payload.get("data") if isinstance(match_payload.get("data"), list) else []
    team_by_name = {str(t.get("team_name") or "").strip(): t for t in teams if isinstance(t, dict)}
    venue_by_name = {str(v.get("venue") or "").strip(): v for v in venues if isinstance(v, dict)}
    match_by_id = {str(m.get("id") or ""): m for m in matches if isinstance(m, dict)}

    rows: list[dict[str, str]] = []
    for sample in SAMPLES:
        match = match_by_id.get(sample["match_id"])
        venue = venue_by_name.get(sample["venue"])
        if not match:
            raise ValueError(f"sample match missing from local cache: {sample['match_id']}")
        if not venue:
            raise ValueError(f"sample venue missing from venue stress layer: {sample['venue']}")

        home = str((match.get("home_team") or {}).get("name") or "")
        away = str((match.get("away_team") or {}).get("name") or "")
        squad_quality, squad_note = _squad_quality(home, away, team_by_name)
        rows.append(
            {
                "run_date": RUN_DATE,
                "sample_id": sample["sample_id"],
                "match_id": str(match.get("id") or ""),
                "utc_date": str(match.get("utc_date") or ""),
                "group_label": str(match.get("group_label") or ""),
                "home_team": home,
                "away_team": away,
                "match": f"{home} vs {away}",
                "venue": str(venue.get("venue") or ""),
                "dryrun_venue": str(venue.get("venue") or ""),
                "dryrun_venue_city": str(venue.get("city") or ""),
                "dryrun_venue_country": str(venue.get("country") or ""),
                "sample_priority": sample["sample_priority"],
                "popular_strong_team": sample["popular_strong_team"],
                "odds_available": str(match.get("odds_available") is True).lower(),
                "xg_available": str(match.get("xg_available") is True).lower(),
                "market_gap_tag": "CURRENT_MARKET_DATA_MISSING",
                "venue_stress_tag": _venue_stress_tag(venue),
                "squad_data_quality": squad_quality,
                "perception_gap_tag": "DATA_INSUFFICIENT;WATCH_ONLY",
                "data_insufficient_reason": _data_insufficient_reason(match, squad_quality),
                "venue_reason": (
                    f"temperature={venue.get('temperature_risk')};"
                    f"humidity={venue.get('humidity_risk')};"
                    f"altitude={venue.get('altitude_risk')};"
                    f"midday={venue.get('midday_risk')};"
                    f"altitude_m={venue.get('altitude')}"
                ),
                "squad_quality_note": squad_note,
                "historical_market_baseline_note": (
                    f"WC finals sample={historical.get('total_world_cup_finals_matches')};"
                    f"favorite_failed_rate={historical.get('favorite_failed_rate')};"
                    f"underdog_upset_count={historical.get('underdog_upset_count')}"
                ),
                "api_prediction_or_odds_note": "2026 local cache has odds_available=false and xg_available=false for selected samples",
                "observation_only": "true",
                "betting_recommendation": "false",
                "affects_v4_grade": "false",
                "scoring_changed": "false",
                "source_layers": "historical_market_baseline|candidate_review_artifact|venue_stress_layer|local_api_cache_if_present",
            }
        )

    context = {
        "historical": historical,
        "coverage": coverage,
        "source_files": [
            HISTORICAL_MARKET_SUMMARY,
            WC5D_REVIEW_ARTIFACT,
            VENUE_STRESS,
            MATCH_CACHE,
            CACHE_COVERAGE,
        ],
    }
    return rows, context


def write_outputs(rows: list[dict[str, str]], context: dict[str, Any]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    coverage = context["coverage"]
    lines = [
        "# V3 WC4D Match-Level Perception Gap Dry Run",
        "",
        f"- run_date: {RUN_DATE}",
        "- mode: DRY_RUN",
        "- observation_only: true",
        "- betting_recommendation: false",
        "- affects_v4_grade: false",
        "- scoring_changed: false",
        "- recommendation_output: false",
        "",
        "## Source Layers",
        "",
        f"- historical_market_baseline: {HISTORICAL_MARKET_SUMMARY.relative_to(ROOT)}",
        f"- candidate_review_artifact: {WC5D_REVIEW_ARTIFACT.relative_to(ROOT)}",
        f"- venue_stress_layer: {VENUE_STRESS.relative_to(ROOT)}",
        "- api_prediction_or_odds_cache: local 2026 match cache present; selected samples have odds_available=false and xg_available=false",
        (
            "- local_cache_coverage: "
            f"world_cup_2026_matches={coverage.get('world_cup_2026_matches')}; "
            f"odds_2022_matches={coverage.get('odds_2022_matches')}; "
            f"odds_2018_matches={coverage.get('odds_2018_matches')}"
        ),
        "",
        "## Sample Matches",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['sample_id']} | {row['match']}",
                "",
                f"- match_id: {row['match_id']}",
                f"- utc_date: {row['utc_date']}",
                f"- dryrun_venue: {row['dryrun_venue']} ({row['dryrun_venue_city']}, {row['dryrun_venue_country']})",
                f"- sample_priority: {row['sample_priority']}",
                f"- market_gap_tag: {row['market_gap_tag']}",
                f"- venue_stress_tag: {row['venue_stress_tag']}",
                f"- squad_data_quality: {row['squad_data_quality']}",
                f"- perception_gap_tag: {row['perception_gap_tag']}",
                f"- data_insufficient_reason: {row['data_insufficient_reason']}",
                f"- venue_reason: {row['venue_reason']}",
                f"- squad_quality_note: {row['squad_quality_note']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Safety",
            "",
            "- This dry run is an observation artifact only.",
            "- It does not update scoring, recommendation, V4 grade, validation, QQ, or live-bet records.",
        ]
    )
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = {
        "run_date": RUN_DATE,
        "mode": "DRY_RUN",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "csv_path": str(CSV_OUT.relative_to(ROOT)),
        "md_path": str(MD_OUT.relative_to(ROOT)),
        "sample_count": len(rows),
        "has_high_heat_or_humidity_sample": any(
            "HEAT_STRESS" in row["venue_stress_tag"] or "HUMIDITY_STRESS" in row["venue_stress_tag"] for row in rows
        ),
        "has_altitude_sample": any("ALTITUDE_STRESS" in row["venue_stress_tag"] for row in rows),
        "has_ordinary_sample": any(row["venue_stress_tag"] == "WATCH_ONLY" for row in rows),
        "has_popular_strong_team_sample": True,
        "has_mixed_pressure_sample": any(
            "HUMIDITY_STRESS" in row["venue_stress_tag"] and "ALTITUDE_STRESS" in row["venue_stress_tag"] for row in rows
        ),
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4_grade": False,
        "scoring_changed": False,
        "local_2026_odds_or_prediction_available_for_samples": False,
        "source_files": [str(path.relative_to(ROOT)) for path in context["source_files"]],
    }
    STATUS_OUT.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> int:
    rows, context = build_rows()
    status = write_outputs(rows, context)
    print(json.dumps({"status": "PASS", **status}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
