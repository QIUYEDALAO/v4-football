from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST = BASE_DIR / "config" / "v4_release_manifest.json"


def freeze_release(
    *,
    release_tag: str,
    model_version: str,
    rule_version: str,
    feature_version: str,
    settlement_version: str,
    notes: str = "",
) -> dict:
    payload = {
        "release_tag": release_tag,
        "frozen_at": datetime.now().isoformat(),
        "model_version": model_version,
        "rule_version": rule_version,
        "feature_version": feature_version,
        "settlement_version": settlement_version,
        "notes": notes,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--release-tag", default="V4.6")
    p.add_argument("--model-version", default="V4.6_RULE_REPLAY_EV")
    p.add_argument("--rule-version", default="V4_HT_LIVE_PULLBACK_EV_NET")
    p.add_argument("--feature-version", default="V4_FEATURE_SET_P0_P8")
    p.add_argument("--settlement-version", default="V4_SETTLEMENT_AH_v1")
    p.add_argument("--notes", default="")
    args = p.parse_args()
    out = freeze_release(
        release_tag=args.release_tag,
        model_version=args.model_version,
        rule_version=args.rule_version,
        feature_version=args.feature_version,
        settlement_version=args.settlement_version,
        notes=args.notes,
    )
    print(json.dumps({"path": str(MANIFEST), "manifest": out}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

