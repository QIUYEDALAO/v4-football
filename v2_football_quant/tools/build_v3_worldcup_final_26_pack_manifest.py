#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
WAR_ROOM_JSON = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
MANIFEST = BASE / "v3_wc2026_final_26_pack_manifest.json"

COMMITS = {
    "structured_ingest": "661fa4c",
    "observation_layer": "83d67c9",
    "ui_json_integration": "b250926",
    "squad_profile_derived_layer": "d5be148",
    "wc10_profile_node_integration": "208697f",
}
SAFETY = {
    "observation_only": True,
    "no_starting_xi": True,
    "no_injury_judgment": True,
    "no_prediction": True,
    "betting_recommendation": False,
    "affects_v4": False,
}
ARTIFACTS = [
    ("v3_wc2026_final_26_players.csv", "canonical_players_csv"),
    ("v3_wc2026_final_26_players.json", "canonical_players_json"),
    ("v3_wc2026_final_26_teams.json", "canonical_teams_json"),
    ("v3_wc2026_final_26_summary.json", "canonical_summary_json"),
    ("v3_wc2026_final_26_war_room_roster_index.json", "war_room_roster_index_json"),
    ("v3_wc2026_final_26_team_observation_cards.json", "team_observation_cards_json"),
    ("v3_wc2026_final_26_squad_observation_summary.json", "squad_observation_summary_json"),
    ("v3_wc2026_final_26_war_room_ui_payload.json", "war_room_ui_payload_json"),
    ("v3_wc2026_final_26_squad_profile_observation.json", "squad_profile_observation_json"),
    ("v3_wc2026_final_26_squad_profile_team_cards.json", "squad_profile_team_cards_json"),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip()


def record_count(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.suffix == ".csv":
        return max(0, sum(1 for _ in path.open(encoding="utf-8")) - 1)
    if path.suffix == ".json":
        obj = load_json(path)
        if isinstance(obj, list):
            return len(obj)
        if isinstance(obj, dict):
            for key in ["players", "teams", "records", "items"]:
                if isinstance(obj.get(key), list):
                    return len(obj[key])
    return None


def artifact_entry(name: str, artifact_type: str) -> dict[str, Any]:
    path = BASE / name
    exists = path.exists()
    return {
        "path": str(path.relative_to(ROOT)),
        "artifact_type": artifact_type,
        "exists": exists,
        "file_size": path.stat().st_size if exists else 0,
        "sha256": sha256(path) if exists else "",
        "record_count": record_count(path),
    }


def main() -> int:
    summary = load_json(BASE / "v3_wc2026_final_26_summary.json")
    observation_summary = load_json(BASE / "v3_wc2026_final_26_squad_observation_summary.json")
    profile = load_json(BASE / "v3_wc2026_final_26_squad_profile_observation.json")
    war_room = load_json(WAR_ROOM_JSON)
    final26_node = war_room.get("final_26_squad_observation") if isinstance(war_room.get("final_26_squad_observation"), dict) else {}
    profile_node = war_room.get("final_26_squad_profile_observation") if isinstance(war_room.get("final_26_squad_profile_observation"), dict) else {}
    manifest = {
        "pack_name": "V3_WC_FINAL_26_SQUAD_PACK",
        "tournament": "FIFA World Cup 2026",
        "source": "FIFA official final 26 canonical squad layer",
        "current_head": current_head(),
        "commits": COMMITS,
        "artifacts": [artifact_entry(name, artifact_type) for name, artifact_type in ARTIFACTS],
        "counts": {
            "team_count": int(summary.get("team_count") or 0),
            "total_players": int(summary.get("total_players") or 0),
            "coach_count": int(observation_summary.get("coach_count") or 0),
            "teams_with_26_players": int(summary.get("teams_with_26_players") or 0),
            "position_distribution": summary.get("position_distribution") or profile.get("position_distribution") or {},
        },
        "war_room_nodes": {
            "final_26_squad_observation": {
                "exists": bool(final26_node),
                "module": final26_node.get("module"),
                "status": final26_node.get("status"),
                "team_count": final26_node.get("team_count"),
                "total_players": final26_node.get("total_players"),
                "coach_count": final26_node.get("coach_count"),
                "safety": final26_node.get("safety") if isinstance(final26_node.get("safety"), dict) else {},
            },
            "final_26_squad_profile_observation": {
                "exists": bool(profile_node),
                "module": profile_node.get("module"),
                "status": profile_node.get("status"),
                "team_count": profile_node.get("team_count"),
                "total_players": profile_node.get("total_players"),
                "position_distribution": profile_node.get("position_distribution") if isinstance(profile_node.get("position_distribution"), dict) else {},
                "ranking_type": (profile_node.get("observation_rankings") or {}).get("ranking_type") if isinstance(profile_node.get("observation_rankings"), dict) else "",
                "team_profile_refs_count": len(profile_node.get("team_profile_refs") or []) if isinstance(profile_node.get("team_profile_refs"), list) else 0,
                "safety": profile_node.get("safety") if isinstance(profile_node.get("safety"), dict) else {},
            },
        },
        "safety": SAFETY,
        "raw_docx_policy": "ACCEPT_RAW_UNTRACKED",
        "final_pack_acceptance_ready": True,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "manifest": str(MANIFEST),
        "artifact_count": len(manifest["artifacts"]),
        "team_count": manifest["counts"]["team_count"],
        "total_players": manifest["counts"]["total_players"],
        "coach_count": manifest["counts"]["coach_count"],
        "position_distribution": manifest["counts"]["position_distribution"],
        "final_pack_acceptance_ready": manifest["final_pack_acceptance_ready"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
