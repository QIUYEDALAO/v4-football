#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

SOURCE_TYPES = {
    "OFFICIAL_PDF",
    "OFFICIAL_CSV",
    "OFFICIAL_JSON",
    "MANUAL_VERIFIED_CSV",
    "MANUAL_VERIFIED_JSON",
    "CLUB_RELEASE",
    "FEDERATION_RELEASE",
    "TOURNAMENT_RELEASE",
    "BOSS_APPROVED_OFFLINE_FILE",
}
DATA_STATUS = {"APPROVED", "PENDING_REVIEW", "REJECTED", "TEMPLATE_ONLY", "STALE", "NEED_REVIEW"}
TRUST_LEVEL = {"OFFICIAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}

SOURCE_REQUIRED = [
    "source_id",
    "source_name",
    "source_type",
    "scope",
    "allowed_file_patterns",
    "allowed_categories",
    "approved_by",
    "approved_at",
    "source_date",
    "license_note",
    "data_status",
    "trust_level",
    "notes",
]
MANIFEST_REQUIRED = [
    "manifest_id",
    "created_at",
    "files",
    "expected_teams",
    "expected_players_range",
    "source_authorization_status",
    "policy_note",
    "safety_guard",
]


def validate_source(item: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in SOURCE_REQUIRED if k not in item]
    src_type = str(item.get("source_type") or "")
    status = str(item.get("data_status") or "")
    trust = str(item.get("trust_level") or "")
    return {
        "ok": not missing and src_type in SOURCE_TYPES and status in DATA_STATUS and trust in TRUST_LEVEL,
        "missing_fields": missing,
        "invalid_source_type": src_type not in SOURCE_TYPES,
        "invalid_data_status": status not in DATA_STATUS,
        "invalid_trust_level": trust not in TRUST_LEVEL,
    }


def validate_manifest_file(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in MANIFEST_REQUIRED if k not in payload]
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    bad = []
    required_file_keys = ["file_path", "source_id", "category", "team_scope", "imported", "authorized", "validation_status", "notes"]
    for i, f in enumerate(files):
        if not isinstance(f, dict):
            bad.append({"index": i, "error": "file_entry_not_dict"})
            continue
        mm = [k for k in required_file_keys if k not in f]
        if mm:
            bad.append({"index": i, "missing_fields": mm})
    return {"ok": not missing and not bad, "missing_fields": missing, "bad_file_entries": bad}


def summarize_authorization(approved: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    approved_list = approved.get("approved_sources") if isinstance(approved.get("approved_sources"), list) else []
    pending_list = approved.get("pending_sources") if isinstance(approved.get("pending_sources"), list) else []
    rejected_list = approved.get("rejected_sources") if isinstance(approved.get("rejected_sources"), list) else []
    manifest_files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    return {
        "approved_sources_count": len(approved_list),
        "pending_sources_count": len(pending_list),
        "rejected_sources_count": len(rejected_list),
        "manifest_files_count": len(manifest_files),
    }
