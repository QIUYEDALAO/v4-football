#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/v3_worldcup/tactical_profile"
STATUS_DIR = ROOT / "data/runtime/status"
RUN_DATE = "20260604"

REPORT_CANDIDATES = [
    ROOT / "reports",
    ROOT.parent / "v4-football/reports",
]

PROFILE_CSV = "v3_wc4f_tactical_profiles.csv"
MATCHUP_CSV = "v3_wc4f_formation_matchups.csv"
OBSERVATION_CSV = "v3_wc4f_observations.csv"
PROFILE_MD = "v3_wc4f_tactical_profiles.md"

OUT_JSON = OUT_DIR / f"v3_worldcup_tactical_profile_layer_{RUN_DATE}.json"
STATUS_JSON = STATUS_DIR / f"v3_worldcup_tactical_profile_layer_{RUN_DATE}.json"

ALLOWED_OBSERVATION_TAGS = [
    "LOW_BLOCK_WATCH",
    "COUNTER_ATTACK_WATCH",
    "OPEN_GAME_WATCH",
    "HIGH_PRESS_FATIGUE_WATCH",
    "MIDFIELD_CONGESTION_WATCH",
    "FORMATION_DATA_INSUFFICIENT",
]


def _reports_dir() -> Path:
    for base in REPORT_CANDIDATES:
        if all((base / name).exists() for name in [PROFILE_CSV, MATCHUP_CSV, OBSERVATION_CSV, PROFILE_MD]):
            return base
    searched = [str(base) for base in REPORT_CANDIDATES]
    raise FileNotFoundError(f"WC4F tactical profile reports missing; searched={searched}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value or "0")))
    except Exception:
        return 0


def _quality_bucket(data_quality: str) -> str:
    value = str(data_quality or "").upper()
    if value.startswith("HIGH"):
        return "HIGH"
    if value.startswith("MEDIUM"):
        return "MEDIUM"
    if value.startswith("LOW"):
        return "LOW"
    return "NO_LINEUP_DATA"


def _confidence(data_quality: str, sample_count: int) -> str:
    bucket = _quality_bucket(data_quality)
    if bucket == "HIGH" and sample_count >= 5:
        return "HIGH"
    if bucket in {"HIGH", "MEDIUM"} and sample_count >= 2:
        return "MEDIUM"
    if bucket == "LOW" and sample_count >= 1:
        return "LOW"
    return "DATA_INSUFFICIENT"


def _split_tags(value: str) -> list[str]:
    return [x.strip() for x in str(value or "").split(";") if x.strip()]


def build_payload() -> dict[str, Any]:
    reports_dir = _reports_dir()
    profiles_raw = _read_csv(reports_dir / PROFILE_CSV)
    matchups_raw = _read_csv(reports_dir / MATCHUP_CSV)
    observations_raw = _read_csv(reports_dir / OBSERVATION_CSV)

    observations_by_team: dict[str, list[dict[str, str]]] = {}
    for row in observations_raw:
        team = str(row.get("team") or "").strip()
        tag = str(row.get("tag") or "").strip()
        if not team or tag not in ALLOWED_OBSERVATION_TAGS:
            continue
        observations_by_team.setdefault(team, []).append({"tag": tag, "rationale": str(row.get("rationale") or "")})

    profiles: list[dict[str, Any]] = []
    for row in profiles_raw:
        team = str(row.get("team_name") or "").strip()
        sample_count = _safe_int(row.get("formation_samples"))
        primary = str(row.get("primary_formation") or "").strip()
        data_quality = str(row.get("data_quality") or "").strip()
        obs = observations_by_team.get(team, [])
        tags = [x["tag"] for x in obs]
        if sample_count == 0 or _quality_bucket(data_quality) == "NO_LINEUP_DATA":
            primary = primary or "FORMATION_DATA_INSUFFICIENT"
            if "FORMATION_DATA_INSUFFICIENT" not in tags:
                tags.append("FORMATION_DATA_INSUFFICIENT")
        profiles.append(
            {
                "team": team,
                "group": str(row.get("group") or ""),
                "common_formation": primary,
                "alternative_formations": _split_tags(str(row.get("alt_formation") or "").replace("|", ";")),
                "formation_data_source": str(row.get("data_sources") or "DATA_MISSING"),
                "formation_sample_count": sample_count,
                "formation_years": _split_tags(str(row.get("formation_years") or "").replace(",", ";")),
                "tactical_tags": tags or ["FORMATION_DATA_INSUFFICIENT"] if sample_count == 0 else tags,
                "tactical_source_labels": _split_tags(row.get("tactical_labels") or ""),
                "observation_confidence": _confidence(data_quality, sample_count),
                "data_quality": data_quality,
                "data_quality_bucket": _quality_bucket(data_quality),
                "observation_notes": [x["rationale"] for x in obs],
                "no_scoring": True,
                "observation_only": True,
                "betting_recommendation": False,
                "affects_v4_grade": False,
                "scoring_changed": False,
            }
        )

    matchup_formations = sorted(
        {
            str(row.get(field) or "").strip()
            for row in matchups_raw
            for field in ["home_formation", "away_formation"]
            if str(row.get(field) or "").strip()
        }
    )
    matchups = [
        {
            "year": _safe_int(row.get("year")),
            "home": str(row.get("home") or ""),
            "away": str(row.get("away") or ""),
            "home_formation": str(row.get("home_formation") or ""),
            "away_formation": str(row.get("away_formation") or ""),
            "match_id": str(row.get("match_id") or ""),
            "observation_only": True,
            "no_scoring": True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
        }
        for row in matchups_raw
    ]
    sample_known_count = sum(1 for row in profiles if int(row["formation_sample_count"]) > 0)
    insufficient_count = sum(1 for row in profiles if "FORMATION_DATA_INSUFFICIENT" in row["tactical_tags"])
    payload = {
        "schema_version": "v3_worldcup_tactical_profile_layer.v1",
        "phase": "V3-WC4G",
        "status": "TACTICAL_PROFILE_LAYER_READY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_reports_dir": str(reports_dir),
        "source_files": {
            "profiles_csv": str(reports_dir / PROFILE_CSV),
            "formation_matchups_csv": str(reports_dir / MATCHUP_CSV),
            "observations_csv": str(reports_dir / OBSERVATION_CSV),
            "profiles_md": str(reports_dir / PROFILE_MD),
        },
        "allowed_observation_tags": ALLOWED_OBSERVATION_TAGS,
        "teams_profiled_count": len(profiles),
        "teams_with_real_formation_samples": sample_known_count,
        "teams_formation_data_insufficient": insufficient_count,
        "formation_matchup_samples_count": len(matchups),
        "unique_formations_count": len(matchup_formations),
        "unique_formations": matchup_formations,
        "profiles": profiles,
        "formation_matchups": matchups,
        "safety_guard": {
            "observation_only": True,
            "no_scoring": True,
            "betting_recommendation": False,
            "affects_v4_grade": False,
            "scoring_changed": False,
            "no_v4_changes": True,
        },
    }
    return payload


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_JSON.write_text(
        json.dumps(
            {
                "generated_at_utc": payload["generated_at_utc"],
                "status": payload["status"],
                "teams_profiled_count": payload["teams_profiled_count"],
                "teams_with_real_formation_samples": payload["teams_with_real_formation_samples"],
                "teams_formation_data_insufficient": payload["teams_formation_data_insufficient"],
                "formation_matchup_samples_count": payload["formation_matchup_samples_count"],
                "unique_formations_count": payload["unique_formations_count"],
                "safety_guard": payload["safety_guard"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "output": str(OUT_JSON), "status_json": str(STATUS_JSON)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
