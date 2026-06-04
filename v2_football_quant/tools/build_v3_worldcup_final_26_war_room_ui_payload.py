#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
ROSTER_INDEX = BASE / "v3_wc2026_final_26_war_room_roster_index.json"
TEAM_CARDS = BASE / "v3_wc2026_final_26_team_observation_cards.json"
OBS_SUMMARY = BASE / "v3_wc2026_final_26_squad_observation_summary.json"
UI_PAYLOAD = BASE / "v3_wc2026_final_26_war_room_ui_payload.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload() -> dict[str, Any]:
    roster_index = load_json(ROSTER_INDEX)
    team_cards = load_json(TEAM_CARDS)
    summary = load_json(OBS_SUMMARY)
    roster_by_slug = {str(item.get("team_slug") or ""): item for item in roster_index}
    teams = []
    for card in sorted(team_cards, key=lambda x: str(x.get("team") or "")):
        slug = str(card.get("team_slug") or "")
        roster = roster_by_slug.get(slug, {})
        teams.append({
            "team": card.get("team"),
            "team_slug": slug,
            "head_coach": card.get("head_coach"),
            "player_count": card.get("player_count"),
            "position_counts": roster.get("position_counts") or {
                "GK": card.get("gk_count"),
                "DF": card.get("df_count"),
                "MF": card.get("mf_count"),
                "FW": card.get("fw_count"),
            },
            "avg_age": card.get("avg_age"),
            "avg_height_cm": card.get("avg_height_cm"),
            "club_count": card.get("club_count"),
            "top_clubs": card.get("top_clubs") or [],
            "roster_ref": {
                "team_slug": slug,
                "player_ids": roster.get("roster_player_ids") or [],
            },
            "observation_card_ref": {
                "team_slug": slug,
                "metrics": ["avg_age", "avg_height_cm", "club_count", "top_clubs"],
            },
            "safety": {
                "observation_only": True,
                "no_starting_xi": True,
                "no_injury_judgment": True,
                "betting_recommendation": False,
                "affects_v4": False,
            },
        })
    return {
        "tournament": "FIFA World Cup 2026",
        "source": "FIFA official final 26 war room observation layer",
        "generated_from": {
            "roster_index": str(ROSTER_INDEX),
            "team_observation_cards": str(TEAM_CARDS),
            "squad_observation_summary": str(OBS_SUMMARY),
        },
        "module": "final_26_squad_observation",
        "team_count": summary.get("team_count"),
        "total_players": summary.get("total_players"),
        "coach_count": summary.get("coach_count"),
        "global_position_distribution": summary.get("global_position_distribution"),
        "avg_age_global": summary.get("avg_age_global"),
        "avg_height_global": summary.get("avg_height_global"),
        "club_count_global": summary.get("club_count_global"),
        "teams": teams,
        "safety": {
            "observation_only": True,
            "no_starting_xi": True,
            "no_injury_judgment": True,
            "betting_recommendation": False,
            "affects_v4": False,
        },
    }


def main() -> int:
    for path in [ROSTER_INDEX, TEAM_CARDS, OBS_SUMMARY]:
        if not path.exists():
            raise FileNotFoundError(path)
    payload = build_payload()
    UI_PAYLOAD.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "ui_payload": str(UI_PAYLOAD),
        "module": payload["module"],
        "team_count": payload["team_count"],
        "total_players": payload["total_players"],
        "coach_count": payload["coach_count"],
        "teams": len(payload["teams"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
