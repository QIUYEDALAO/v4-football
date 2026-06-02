#!/usr/bin/env python3
"""Schema constants for the V3 World Cup venue stress observation layer."""
from __future__ import annotations

REQUIRED_VENUE_FIELDS = [
    "venue",
    "city",
    "country",
    "altitude",
    "temperature_risk",
    "humidity_risk",
    "altitude_risk",
    "midday_risk",
    "stress_tags",
    "source_quality",
    "video_claim_allowed",
]

STRESS_TAGS = [
    "HEAT_STRESS",
    "HUMIDITY_STRESS",
    "ALTITUDE_STRESS",
    "MIDDAY_KICKOFF_RISK",
    "VENUE_UPSET_WATCH",
    "WATCH_ONLY",
]

FOCUS_VENUES = [
    "Hard Rock Stadium",
    "Arrowhead Stadium",
    "Estadio BBVA",
    "Estadio Azteca",
    "Estadio Akron",
]

SAFETY_GUARD = {
    "observation_only": True,
    "betting_recommendation": False,
    "no_stake": True,
    "no_v4_changes": True,
    "video_claim_not_scoring_input": True,
}
