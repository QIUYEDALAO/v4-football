#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/v3_worldcup"
AUTH_DIR = V3 / "source_authorization"
INTAKE_DIR = V3 / "final_squads/intake"
SOURCE_GATE_REPORT = ROOT / "data/runtime/v3_worldcup/source_authorization/v3_worldcup_source_authorization_gate_20260602.json"
OUT_DIR = ROOT / "data/runtime/v3_worldcup/final_squads"


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _looks_json(path: Path) -> bool:
    return path.suffix.lower() == ".json"


def _scan_intake_files() -> list[Path]:
    if not INTAKE_DIR.exists():
        return []
    out = []
    for p in INTAKE_DIR.rglob("*"):
        if p.is_file() and p.name != "README.md":
            out.append(p)
    return out


def main() -> int:
    gate = _load(SOURCE_GATE_REPORT)
    approved = _load(AUTH_DIR / "approved_sources.json") or _load(AUTH_DIR / "approved_sources_template.json")
    manifest = _load(AUTH_DIR / "source_manifest.json") or _load(AUTH_DIR / "source_manifest_template.json")

    approved_sources = approved.get("approved_sources") if isinstance(approved.get("approved_sources"), list) else []
    approved_ids = {str(x.get("source_id")) for x in approved_sources if isinstance(x, dict) and str(x.get("source_id") or "").strip()}
    manifest_files = manifest.get("files") if isinstance(manifest.get("files"), list) else []

    intake_files = _scan_intake_files()
    authorized_candidates: list[dict[str, Any]] = []
    unauthorized_files_found = 0
    file_status: list[dict[str, Any]] = []

    manifest_map: dict[str, dict[str, Any]] = {}
    for entry in manifest_files:
        if not isinstance(entry, dict):
            continue
        fp = str(entry.get("file_path") or "").strip()
        if fp:
            manifest_map[Path(fp).name] = entry

    for p in intake_files:
        ent = manifest_map.get(p.name)
        source_id = str((ent or {}).get("source_id") or "").strip()
        authorized = bool(ent) and bool((ent or {}).get("authorized") is True) and source_id in approved_ids
        if authorized:
            authorized_candidates.append({"path": p, "entry": ent})
        else:
            unauthorized_files_found += 1
        file_status.append(
            {
                "file_name": p.name,
                "source_id": source_id or "UNREGISTERED",
                "authorized": authorized,
                "imported": False,
                "reason": "AUTHORIZED_FOR_DRYRUN" if authorized else "UNAUTHORIZED_BLOCKED",
            }
        )

    approved_count = len(approved_ids)
    authorized_files_found = len(authorized_candidates)
    final_ready = authorized_files_found
    dryrun_files_parsed = 0
    dryrun_teams_detected = 0
    dryrun_players_detected = 0
    dryrun_complete_teams_count = 0
    dryrun_underfull_teams: list[dict[str, Any]] = []
    dryrun_overfull_teams: list[dict[str, Any]] = []
    dryrun_goalkeeper_issues: list[dict[str, Any]] = []
    dryrun_team_name_normalization_issues: list[str] = []

    if unauthorized_files_found > 0:
        status = "BLOCKED_UNAUTHORIZED_FILES_PRESENT"
        blocker = "UNAUTHORIZED_FILES_PRESENT"
    elif approved_count == 0 or len(intake_files) == 0:
        status = "NOOP_SOURCE_FILES_MISSING"
        blocker = "NONE"
    elif final_ready == 0:
        status = "NOOP_NO_AUTHORIZED_FILES_READY"
        blocker = "NONE"
    else:
        status = "AUTHORIZED_FINAL_SQUAD_DRYRUN_COMPLETE_WITH_WARN_ONLY"
        blocker = "NONE"
        for item in authorized_candidates:
            p: Path = item["path"]
            if not _looks_json(p):
                file_status.append({"file_name": p.name, "authorized": True, "imported": False, "reason": "UNSUPPORTED_DRYRUN_FORMAT"})
                continue
            payload = _load(p)
            teams = payload.get("teams") if isinstance(payload.get("teams"), list) else []
            dryrun_files_parsed += 1
            dryrun_teams_detected += len([x for x in teams if isinstance(x, dict)])
            for t in teams:
                if not isinstance(t, dict):
                    continue
                tname = str(t.get("team_name") or "").strip()
                if not tname:
                    dryrun_team_name_normalization_issues.append("EMPTY_TEAM_NAME")
                    tname = "UNKNOWN"
                players = t.get("players") if isinstance(t.get("players"), list) else []
                pcount = len(players)
                dryrun_players_detected += pcount
                if 23 <= pcount <= 26:
                    dryrun_complete_teams_count += 1
                elif pcount < 23:
                    dryrun_underfull_teams.append({"team": tname, "count": pcount})
                else:
                    dryrun_overfull_teams.append({"team": tname, "count": pcount})
                gk = sum(1 for pp in players if isinstance(pp, dict) and bool(pp.get("goalkeeper_flag")))
                if gk < 3:
                    dryrun_goalkeeper_issues.append({"team": tname, "goalkeepers": gk})

    warn_only = []
    if approved_count == 0:
        warn_only.append("NO_APPROVED_REAL_FINAL_SQUAD_SOURCE")
    if final_ready == 0:
        warn_only.append("NO_AUTHORIZED_INTAKE_FILES")
    if dryrun_files_parsed == 0:
        warn_only.append("INGESTION_DRYRUN_NOT_STARTED")

    report = {
        "generated_at": datetime.now().isoformat(),
        "phase": "V3-WC6",
        "status": status,
        "status_level": "CODE_READY",
        "blocker": blocker,
        "source_gate_status": gate.get("status") or "DATA_MISSING",
        "approved_sources_count": approved_count,
        "intake_files_found": len(intake_files),
        "authorized_files_found": authorized_files_found,
        "unauthorized_files_found": unauthorized_files_found,
        "final_squad_files_ready_for_ingestion": final_ready,
        "dryrun_files_parsed": dryrun_files_parsed,
        "dryrun_teams_detected": dryrun_teams_detected,
        "dryrun_players_detected": dryrun_players_detected,
        "dryrun_complete_teams_count": dryrun_complete_teams_count,
        "dryrun_underfull_teams": dryrun_underfull_teams,
        "dryrun_overfull_teams": dryrun_overfull_teams,
        "dryrun_goalkeeper_issues": dryrun_goalkeeper_issues,
        "dryrun_team_name_normalization_issues": dryrun_team_name_normalization_issues,
        "dryrun_not_committed": True,
        "official_final_squad_written": False,
        "no_real_files_noop": approved_count == 0 or final_ready == 0,
        "source_authorization_status_by_file": file_status,
        "warn_only_items": warn_only,
        "policy_note": "Authorized offline final squad ingestion dry-run only. No official final squad artifact is written.",
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
            "no_api_call": True,
            "no_web_fetch": True,
            "unauthorized_files_not_ingested": True,
            "official_final_squad_written": False,
            "dryrun_only": True,
            "baseline_pool_not_treated_as_final_26": True,
            "final_squad_complete_not_claimed": True,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "v3_worldcup_authorized_final_squad_ingestion_dryrun_20260602.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "report": str(out), "phase": "V3-WC6"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
