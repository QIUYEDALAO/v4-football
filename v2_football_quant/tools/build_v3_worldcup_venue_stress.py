#!/usr/bin/env python3
"""Build V3 World Cup venue stress observation data from the OpenClaw pack."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    from tools.v3_worldcup_venue_stress_schema import FOCUS_VENUES, SAFETY_GUARD, STRESS_TAGS
except ModuleNotFoundError:
    from v3_worldcup_venue_stress_schema import FOCUS_VENUES, SAFETY_GUARD, STRESS_TAGS

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
LOCAL_REPORTS = ROOT / "reports"
EXTERNAL_REPORTS = WORKSPACE / "v4-football/reports"
CSV_CANDIDATES = [
    LOCAL_REPORTS / "v3_wc_venue_stress_pack.csv",
    EXTERNAL_REPORTS / "v3_wc_venue_stress_pack.csv",
]
MD_CANDIDATES = [
    LOCAL_REPORTS / "v3_wc_venue_stress_pack.md",
    EXTERNAL_REPORTS / "v3_wc_venue_stress_pack.md",
]
OUT_DIR = ROOT / "data/v3_worldcup/venue_stress"
RUNTIME_DIR = ROOT / "data/runtime/v3_worldcup/venue_stress"
STATUS_DIR = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))


def _first_existing(paths: list[Path]) -> Path | None:
    return next((p for p in paths if p.exists()), None)


def _risk_level(value: str) -> str:
    text = str(value or "").upper()
    if "HIGH" in text:
        return "HIGH"
    if "MEDIUM" in text:
        return "MEDIUM"
    if "LOW" in text:
        return "LOW"
    return "UNKNOWN"


def _num(value: str) -> float | None:
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _tags(row: dict[str, str]) -> list[str]:
    tags = ["WATCH_ONLY"]
    if _risk_level(row.get("HeatRisk", "")) == "HIGH":
        tags.append("HEAT_STRESS")
    if _risk_level(row.get("HumidityRisk", "")) == "HIGH":
        tags.append("HUMIDITY_STRESS")
    if _risk_level(row.get("AltitudeRisk", "")) == "HIGH":
        tags.append("ALTITUDE_STRESS")
    if _risk_level(row.get("AfternoonKickoffRisk", "")) == "HIGH":
        tags.append("MIDDAY_KICKOFF_RISK")
    if row.get("Stadium") in FOCUS_VENUES or _risk_level(row.get("CompositeRisk", "")) == "HIGH":
        tags.append("VENUE_UPSET_WATCH")
    return [tag for tag in STRESS_TAGS if tag in tags]


def _source_quality(row: dict[str, str]) -> str:
    if row.get("Stadium") in FOCUS_VENUES:
        return "HIGH_SOURCE_CROSS_CHECKED_VIDEO_CLAIM_OBSERVATION_ONLY"
    if str(row.get("HasAC", "")).upper() == "TRUE":
        return "HIGH_SOURCE_INDOOR_VENUE_CONFIRMED"
    return "MEDIUM_HIGH_SOURCE_CLIMATE_NORMALS"


def _reason(row: dict[str, str], tags: list[str]) -> str:
    reasons: list[str] = []
    if "HEAT_STRESS" in tags:
        reasons.append(f"heat={row.get('HeatRisk')}")
    if "HUMIDITY_STRESS" in tags:
        reasons.append(f"humidity={row.get('HumidityRisk')}")
    if "ALTITUDE_STRESS" in tags:
        reasons.append(f"altitude={row.get('Altitude_m')}m")
    if "MIDDAY_KICKOFF_RISK" in tags:
        reasons.append(f"midday={row.get('AfternoonKickoffRisk')}")
    if not reasons:
        reasons.append("low or indoor controlled venue stress")
    return "; ".join(reasons)


def build() -> dict[str, Any]:
    csv_path = _first_existing(CSV_CANDIDATES)
    md_path = _first_existing(MD_CANDIDATES)
    if not csv_path:
        raise FileNotFoundError("reports/v3_wc_venue_stress_pack.csv not found")

    rows: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        for idx, raw in enumerate(reader, 1):
            if len(raw) > len(header):
                extra = len(raw) - len(header)
                raw = [",".join(raw[:extra + 1])] + raw[extra + 1:]
            row = dict(zip(header, raw))
            tags = _tags(row)
            venue = row.get("Stadium", "").strip()
            rows.append({
                "index": idx,
                "venue": venue,
                "city": row.get("HostCity", "").strip(),
                "country": row.get("Country", "").strip(),
                "capacity": int(row.get("Capacity") or 0),
                "roof_type": row.get("RoofType", "").strip(),
                "has_ac": str(row.get("HasAC", "")).upper() == "TRUE",
                "altitude": _num(row.get("Altitude_m", "")),
                "altitude_ft": _num(row.get("Altitude_ft", "")),
                "temperature_june_c": _num(row.get("Temp_June_C", "")),
                "temperature_july_c": _num(row.get("Temp_July_C", "")),
                "humidity_june_pct": _num(row.get("Humidity_June_Pct", "")),
                "humidity_july_pct": _num(row.get("Humidity_July_Pct", "")),
                "temperature_risk": _risk_level(row.get("HeatRisk", "")),
                "humidity_risk": _risk_level(row.get("HumidityRisk", "")),
                "altitude_risk": _risk_level(row.get("AltitudeRisk", "")),
                "midday_risk": _risk_level(row.get("AfternoonKickoffRisk", "")),
                "physical_exertion_risk": _risk_level(row.get("PhysicalExertionRisk", "")),
                "composite_risk": _risk_level(row.get("CompositeRisk", "")),
                "stress_tags": tags,
                "stress_reason": _reason(row, tags),
                "source_quality": _source_quality(row),
                "video_claim_allowed": venue in FOCUS_VENUES,
                "video_claim_used_for_score": False,
            })

    focus = [x for x in rows if x["venue"] in FOCUS_VENUES]
    payload = {
        "schema_version": "v3_worldcup_venue_stress.v1",
        "generated_at": datetime.now(TZ).isoformat(),
        "source_pack_csv": str(csv_path),
        "source_pack_markdown": str(md_path) if md_path else "NOT_FOUND",
        "venue_count": len(rows),
        "focus_venue_count": len(focus),
        "focus_venues": FOCUS_VENUES,
        "stress_tags_allowed": STRESS_TAGS,
        "venues": rows,
        "focus_venue_rows": focus,
        "safety_guard": SAFETY_GUARD,
        "policy_note": "V3 venue stress is observation-only. It is not a win/loss signal and not a betting recommendation.",
    }
    return payload


def main() -> int:
    payload = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "v3_worldcup_venue_stress_20260603.json"
    runtime = RUNTIME_DIR / "v3_worldcup_venue_stress_20260603.json"
    status = STATUS_DIR / "v3_worldcup_venue_stress_20260603.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    runtime.write_text(text, encoding="utf-8")
    status.write_text(json.dumps({
        "generated_at": payload["generated_at"],
        "conclusion": "PASS",
        "venue_count": payload["venue_count"],
        "focus_venue_count": payload["focus_venue_count"],
        "observation_only": True,
        "betting_recommendation": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": "PASS", "output": str(out), "venue_count": payload["venue_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
