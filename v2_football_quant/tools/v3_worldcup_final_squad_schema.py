#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

DATA_STATUS = {"PRESENT", "PARTIAL", "MISSING", "TEMPLATE_ONLY", "STALE", "NEED_REVIEW"}
FINAL_SQUAD_STATUS = {"CONFIRMED_FINAL", "PROVISIONAL", "TEMPLATE_ONLY", "MISSING", "NEED_REVIEW"}

TEAM_REQUIRED = ["team_name", "source", "source_date", "data_status"]
PLAYER_REQUIRED = [
    "player_name",
    "position",
    "goalkeeper_flag",
    "final_squad_status",
    "source",
    "source_date",
    "data_status",
]


def _missing_keys(record: dict[str, Any], required: list[str]) -> list[str]:
    return [k for k in required if k not in record]


def validate_team(team: dict[str, Any]) -> dict[str, Any]:
    missing = _missing_keys(team, TEAM_REQUIRED)
    status = str(team.get("data_status") or "")
    return {
        "ok": len(missing) == 0 and status in DATA_STATUS,
        "missing_fields": missing,
        "invalid_data_status": status not in DATA_STATUS,
    }


def validate_player(player: dict[str, Any]) -> dict[str, Any]:
    missing = _missing_keys(player, PLAYER_REQUIRED)
    data_status = str(player.get("data_status") or "")
    squad_status = str(player.get("final_squad_status") or "")
    return {
        "ok": len(missing) == 0 and data_status in DATA_STATUS and squad_status in FINAL_SQUAD_STATUS,
        "missing_fields": missing,
        "invalid_data_status": data_status not in DATA_STATUS,
        "invalid_final_squad_status": squad_status not in FINAL_SQUAD_STATUS,
    }


def validate_final_squad_file(payload: dict[str, Any]) -> dict[str, Any]:
    teams = payload.get("teams") if isinstance(payload.get("teams"), list) else []
    issues: list[dict[str, Any]] = []
    ok = True
    for i, t in enumerate(teams):
        if not isinstance(t, dict):
            issues.append({"index": i, "error": "team_not_dict"})
            ok = False
            continue
        tv = validate_team(t)
        if not tv["ok"]:
            issues.append({"index": i, "team_name": t.get("team_name"), "team_validation": tv})
            ok = False
        players = t.get("players") if isinstance(t.get("players"), list) else []
        for j, p in enumerate(players):
            if not isinstance(p, dict):
                issues.append({"index": i, "player_index": j, "error": "player_not_dict"})
                ok = False
                continue
            pv = validate_player(p)
            if not pv["ok"]:
                issues.append({"index": i, "player_index": j, "player_name": p.get("player_name"), "player_validation": pv})
                ok = False
    return {"ok": ok, "issues": issues}
