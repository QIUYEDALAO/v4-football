from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = BASE_DIR / "config" / "live_capture_profile.yaml"


def load_profile(profile_name: str = "ultra", path: str | None = None) -> dict:
    p = Path(path) if path else DEFAULT_PROFILE
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    # backward-compatible: allow old flat format
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if isinstance(profiles, dict):
        return profiles.get(profile_name) or profiles.get("ultra") or {}
    return data


def tier_conf(profile: dict, tier: str) -> dict:
    return ((profile or {}).get("tiers") or {}).get(tier, {})
