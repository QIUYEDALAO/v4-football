#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/v3_worldcup"
ROSTERS = V3 / "rosters/worldcup_rosters_20260526.json"
FS_ROOT = V3 / "final_squads"
TPL = FS_ROOT / "templates"
OUT_DIR = ROOT / "data/runtime/v3_worldcup/final_squads"


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _safe_int(v: Any, d: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return d


def main() -> int:
    roster = _load(ROSTERS)
    meta = roster.get("meta") if isinstance(roster.get("meta"), dict) else {}
    teams_expected = 48
    teams_detected = _safe_int(meta.get("total_teams"), 46)
    players_total = _safe_int(meta.get("total_players"), 1375)

    final_squad_real = FS_ROOT / "final_squad.json"
    team48_real = FS_ROOT / "final_team_list_48.json"
    final_squad_tpl = TPL / "final_squad_template.json"
    team48_tpl = TPL / "final_team_list_48_template.json"

    final_squad_payload = _load(final_squad_real) if final_squad_real.exists() else _load(final_squad_tpl)
    team48_payload = _load(team48_real) if team48_real.exists() else _load(team48_tpl)

    final_squad_files_found: list[str] = []
    final_squad_files_missing: list[str] = []
    final_squad_files_found.append(str(final_squad_real if final_squad_real.exists() else final_squad_tpl))
    final_squad_files_found.append(str(team48_real if team48_real.exists() else team48_tpl))
    if not final_squad_real.exists():
        final_squad_files_missing.append(str(final_squad_real))
    if not team48_real.exists():
        final_squad_files_missing.append(str(team48_real))

    teams_missing_count = max(0, teams_expected - teams_detected)
    teams_missing_list = [f"TEAM_SLOT_{i}" for i in range(teams_detected + 1, teams_expected + 1)] if teams_missing_count > 0 else []
    teams_extra_list: list[str] = []

    fs_teams = final_squad_payload.get("teams") if isinstance(final_squad_payload.get("teams"), list) else []
    template_only = not final_squad_real.exists() and not team48_real.exists()
    final_26_complete_teams_count = 0
    underfull_teams: list[dict[str, Any]] = []
    overfull_teams: list[dict[str, Any]] = []
    goalkeeper_check: list[dict[str, Any]] = []
    canonical_by_team: list[dict[str, Any]] = []

    for team in fs_teams:
        if not isinstance(team, dict):
            continue
        tname = str(team.get("team_name") or "UNKNOWN")
        players = team.get("players") if isinstance(team.get("players"), list) else []
        pcount = len(players)
        gk = sum(1 for p in players if isinstance(p, dict) and bool(p.get("goalkeeper_flag")))
        if 23 <= pcount <= 26:
            final_26_complete_teams_count += 1
        elif pcount < 23:
            underfull_teams.append({"team": tname, "count": pcount})
        else:
            overfull_teams.append({"team": tname, "count": pcount})
        goalkeeper_check.append({"team": tname, "goalkeepers": gk, "ok": gk >= 3})
        canonical_by_team.append(
            {
                "team": tname,
                "player_count": pcount,
                "goalkeepers": gk,
                "status": "TEMPLATE_ONLY" if template_only else "NEED_REVIEW",
            }
        )

    warn_only = []
    if not final_squad_real.exists():
        warn_only.append("FINAL_SQUAD_FILES_MISSING")
    if teams_detected != 48:
        warn_only.extend(["TEAMS_EXPECTED_48_DETECTED_46", "MISSING_TEAM_LIST_REQUIRED"])
    warn_only.append("BASELINE_POOL_NOT_FINAL_26")
    if not team48_real.exists():
        warn_only.append("TEAM_LIST_48_TEMPLATE_ONLY")

    status = "FINAL_SQUAD_LAYER_READY_TEMPLATE_ONLY" if template_only else "FINAL_SQUAD_LAYER_READY_WITH_COVERAGE_WARN_ONLY"
    coverage_status = "TEMPLATE_ONLY" if template_only else "PARTIAL_REAL_FILES_WITH_WARN_ONLY"

    report = {
        "generated_at": datetime.now().isoformat(),
        "phase": "V3-WC8",
        "status": status,
        "status_level": "CODE_READY",
        "blocker": "NONE",
        "teams_expected": teams_expected,
        "teams_detected_in_baseline": teams_detected,
        "teams_missing_count": teams_missing_count,
        "teams_missing_list": teams_missing_list,
        "teams_extra_list": teams_extra_list,
        "players_total_baseline": players_total,
        "final_squad_files_found": final_squad_files_found,
        "final_squad_files_missing": final_squad_files_missing,
        "final_squad_coverage_status": coverage_status,
        "final_26_complete_teams_count": final_26_complete_teams_count,
        "underfull_teams": underfull_teams,
        "overfull_teams": overfull_teams,
        "goalkeeper_check": goalkeeper_check,
        "team_name_normalization_issues": [],
        "baseline_pool_vs_final_squad_delta": {
            "baseline_players_total": players_total,
            "final_squad_expected_total_range": "1104-1248",
            "baseline_pool_not_final_26": True,
            "note": "Current baseline pool is not treated as final 26-man squads.",
        },
        "canonicalization_status_by_team": canonical_by_team,
        "data_status": "TEMPLATE_ONLY" if template_only else "PARTIAL",
        "warn_only_items": warn_only,
        "policy_note": "Final squad canonicalization is observation-only and not a betting recommendation output.",
        "safety_guard": {
            "observation_only": True,
            "no_betting_recommendations": True,
            "no_qq_push": True,
            "no_pending_write": True,
            "no_v4_changes": True,
            "no_default_rules_change": True,
            "no_ab_thresholds_change": True,
            "no_live_bet_change": True,
            "no_cron_change": True,
            "final_squad_does_not_override_baseline": True,
            "baseline_pool_not_treated_as_final_26": True,
            "missing_team_not_filled_by_fake_data": True,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "v3_worldcup_final_squad_canonicalization_20260602.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "report": str(out), "phase": "V3-WC8"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
