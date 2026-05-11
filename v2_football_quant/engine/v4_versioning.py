from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST = BASE_DIR / "config" / "v4_release_manifest.json"


def get_v4_versions() -> dict:
    default = {
        "release_tag": "V4.UNSET",
        "model_version": "V4.UNSET",
        "rule_version": "V4.UNSET",
        "feature_version": "V4.UNSET",
        "settlement_version": "V4.UNSET",
    }
    if not MANIFEST.exists():
        return default
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "release_tag": data.get("release_tag", default["release_tag"]),
            "model_version": data.get("model_version", default["model_version"]),
            "rule_version": data.get("rule_version", default["rule_version"]),
            "feature_version": data.get("feature_version", default["feature_version"]),
            "settlement_version": data.get("settlement_version", default["settlement_version"]),
        }
    except Exception:
        return default

