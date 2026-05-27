"""v4_lab/profile_loader.py — Load lab strategy profiles with isolation guard."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT / "config" / "v4_lab_profiles"


def load_profile(profile_path: str | Path) -> dict:
    path = Path(profile_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Lab profile not found: {path}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not profile.get("lab_only"):
        raise ValueError(f"Profile {profile.get('profile_id')} is not lab_only — rejected")
    return profile


def list_profiles() -> list[dict]:
    profiles = []
    for f in sorted(PROFILES_DIR.glob("*.json")):
        try:
            p = json.loads(f.read_text())
            if p.get("lab_only"):
                profiles.append(p)
        except Exception:
            pass
    return profiles


def profile_hash(profile: dict) -> str:
    import hashlib
    raw = json.dumps(profile, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
