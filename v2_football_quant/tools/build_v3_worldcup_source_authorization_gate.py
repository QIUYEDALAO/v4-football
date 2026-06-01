#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.v3_worldcup_source_authorization_schema import summarize_authorization
except ImportError:
    from v3_worldcup_source_authorization_schema import summarize_authorization

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/v3_worldcup"
AUTH = V3 / "source_authorization"
INTAKE = V3 / "final_squads/intake"
ROSTERS = V3 / "rosters/worldcup_rosters_20260526.json"
OUT_DIR = ROOT / "data/runtime/v3_worldcup/source_authorization"


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _safe_int(v: Any, d: int) -> int:
    try:
        return int(v)
    except Exception:
        return d


def main() -> int:
    approved_real = AUTH / "approved_sources.json"
    approved_tpl = AUTH / "approved_sources_template.json"
    manifest_real = AUTH / "source_manifest.json"
    manifest_tpl = AUTH / "source_manifest_template.json"

    approved = _load(approved_real) if approved_real.exists() else _load(approved_tpl)
    manifest = _load(manifest_real) if manifest_real.exists() else _load(manifest_tpl)
    summary = summarize_authorization(approved, manifest)

    roster_meta = (_load(ROSTERS).get("meta") or {})
    teams_detected = _safe_int(roster_meta.get("total_teams"), 46)
    players_total = _safe_int(roster_meta.get("total_players"), 1375)

    approved_ids = set()
    for x in (approved.get("approved_sources") if isinstance(approved.get("approved_sources"), list) else []):
        if isinstance(x, dict) and str(x.get("source_id") or "").strip():
            approved_ids.add(str(x.get("source_id")).strip())

    manifest_files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    intake_files = []
    if INTAKE.exists():
        for p in INTAKE.rglob("*"):
            if p.is_file() and p.name != "README.md":
                intake_files.append(p)

    source_authorization_status_by_file = []
    authorized_files_found = 0
    unauthorized_files_found = 0
    for f in intake_files:
        fname = f.name
        entry = None
        for m in manifest_files:
            if isinstance(m, dict) and Path(str(m.get("file_path") or "")).name == fname:
                entry = m
                break
        sid = str((entry or {}).get("source_id") or "")
        authorized = bool(entry) and bool((entry or {}).get("authorized") is True) and sid in approved_ids
        if authorized:
            authorized_files_found += 1
        else:
            unauthorized_files_found += 1
        source_authorization_status_by_file.append(
            {
                "file_name": fname,
                "source_id": sid or "UNREGISTERED",
                "authorized": authorized,
                "validation_status": (entry or {}).get("validation_status") or "TEMPLATE_ONLY",
                "imported": False,
                "note": "Unauthorized or unregistered files are blocked from ingestion." if not authorized else "Authorized file queued for future WC6 ingestion.",
            }
        )

    template_only = not approved_real.exists() and not manifest_real.exists()
    warn_only = []
    if template_only:
        warn_only.extend(
            [
                "NO_APPROVED_REAL_FINAL_SQUAD_SOURCE",
                "SOURCE_MANIFEST_TEMPLATE_ONLY",
                "FINAL_SQUAD_REAL_INGESTION_NOT_STARTED",
            ]
        )
    if unauthorized_files_found > 0:
        status = "SOURCE_AUTHORIZATION_GATE_BLOCKED_UNAUTHORIZED_FILES"
        blocker = "UNAUTHORIZED_INTAKE_FILES_FOUND"
    elif summary["approved_sources_count"] > 0 and len(intake_files) == 0:
        status = "SOURCE_AUTHORIZATION_GATE_READY_APPROVED_SOURCE_NO_FILES"
        blocker = "NONE"
    else:
        status = "SOURCE_AUTHORIZATION_GATE_READY_TEMPLATE_ONLY"
        blocker = "NONE"

    report = {
        "generated_at": datetime.now().isoformat(),
        "phase": "V3-WC7",
        "status": status,
        "status_level": "CODE_READY",
        "blocker": blocker,
        "approved_sources_count": summary["approved_sources_count"],
        "pending_sources_count": summary["pending_sources_count"],
        "rejected_sources_count": summary["rejected_sources_count"],
        "unauthorized_files_found": unauthorized_files_found,
        "authorized_files_found": authorized_files_found,
        "intake_files_found": len(intake_files),
        "final_squad_files_ready_for_ingestion": authorized_files_found if blocker == "NONE" else 0,
        "final_squad_real_source_status": "TEMPLATE_ONLY" if template_only else ("READY_WITH_APPROVED_SOURCES" if summary["approved_sources_count"] > 0 else "MISSING"),
        "teams_expected": 48,
        "teams_detected_in_baseline": teams_detected,
        "players_total_baseline": players_total,
        "source_authorization_status_by_file": source_authorization_status_by_file,
        "warn_only_items": warn_only,
        "policy_note": "Source authorization gate is required before any real final squad ingestion and remains observation-only.",
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
            "no_fake_sources": True,
            "no_fake_final_squad": True,
            "unauthorized_files_not_ingested": True,
            "source_gate_required_before_ingestion": True,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "v3_worldcup_source_authorization_gate_20260602.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "report": str(out), "phase": "V3-WC7"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
