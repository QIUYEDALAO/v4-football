#!/usr/bin/env python3
"""Decommission guard: active system must be V3/V4 only.

This is not a production checker for the retired module. It only verifies that
retired active sources are absent from current dashboard, manifest, cron, cloud,
and code paths.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "data/runtime/status"
DASH = ROOT / "data/runtime/dashboard/intel_ops_console.html"
TZ = timezone(timedelta(hours=8))
DATE = "20260523"
LEGACY_VISIBLE = re.compile(r"V2 active|\bV2\b|BET_LOCKED|V2历史池|V2锁仓|V2验证|V2 QQ|V2_ONLY|v2_window|v2_daily_pool|WATCH_EARLY|V33 active|\bV33\b", re.I)


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def active_manifest_text(manifest: dict) -> str:
    parts=[]
    for data in manifest.get("active_systems",{}).values():
        if isinstance(data, dict):
            for key in ("active_sources","allowed_tasks","entrypoint","review_mode"):
                val=data.get(key)
                if isinstance(val, list): parts.extend(map(str,val))
                elif val is not None: parts.append(str(val))
    return "\n".join(parts)


def active_code_hits() -> list[str]:
    hits=[]
    allowed={"tools/check_v2_decommission_v3_v4_only.py", "tools/check_local_v2_full_purge.py"}
    for base in ["engine","tools","config"]:
        root=ROOT/base
        if not root.exists(): continue
        for p in root.rglob("*"):
            if not p.is_file() or "archive" in p.parts or "__pycache__" in p.parts: continue
            rel=str(p.relative_to(ROOT))
            if rel in allowed: continue
            name=p.name.lower()
            if name.startswith("v2") or name.startswith("check_v2") or "_v2_" in name or "bet_locked" in name:
                hits.append(rel)
    return hits


def main() -> int:
    manifest=load(STATUS_DIR/"current_ops_manifest_20260521.json") or load(STATUS_DIR/"current_ops_manifest_v3_v4_only_20260521.json")
    cron=load(STATUS_DIR/"check_gateway_cron_policy_hardening_result_20260521.json") or load(STATUS_DIR/"v3v4_gateway_cron_policy_20260521.json")
    cloud=load(STATUS_DIR/"check_cloud_bundle_excludes_archive_result_20260521.json") or load(STATUS_DIR/"v3v4_cloud_bundle_filter_20260521.json")
    refresh=load(STATUS_DIR/"check_v3v4_intel_ops_console_daily_refresh_pipeline_result_20260523.json")
    html=DASH.read_text(encoding="utf-8",errors="replace") if DASH.exists() else ""
    text=active_manifest_text(manifest)
    blockers=[]
    v2_active_in_manifest=bool(re.search(r"\bv2\b|bet_locked", text, re.I))
    v33_active=bool(re.search(r"\bv33\b", text, re.I))
    v3_active=bool(manifest.get("active_systems",{}).get("V3",{}).get("active_sources"))
    v4_active=bool(manifest.get("active_systems",{}).get("V4",{}).get("active_sources"))
    dashboard_v2_visible=bool(LEGACY_VISIBLE.search(html))
    code_hits=active_code_hits()
    if v2_active_in_manifest: blockers.append("v2_active_in_manifest")
    if v33_active: blockers.append("v33_active_in_manifest")
    if not v3_active: blockers.append("v3_missing")
    if not v4_active: blockers.append("v4_missing")
    if dashboard_v2_visible: blockers.append("dashboard_legacy_visible")
    if code_hits: blockers.append(f"active_legacy_code_hits:{len(code_hits)}")
    if cron.get("active_v2_cron_count") not in (0, None): blockers.append("active_v2_cron_count_not_zero")
    if cloud.get("cloud_bundle_v2_active_count") not in (0, None): blockers.append("cloud_bundle_v2_active_count_not_zero")
    if refresh and refresh.get("daily_refresh_v2_dependency") is not False: blockers.append("daily_refresh_legacy_dependency")
    status="BLOCKER" if blockers else "PASS"
    result={
        "checker":"tools/check_v2_decommission_v3_v4_only.py",
        "phase":"V3V4-INTEL-OPS-CONSOLE-UI-REFIT-AND-V2-PURGE-CLOSEOUT-20260523",
        "generated_at":datetime.now(TZ).isoformat(),
        "check_status":status,
        "v2_active_in_manifest":v2_active_in_manifest,
        "v3_active_exists":v3_active,
        "v4_active_exists":v4_active,
        "v33_active_reference_count":1 if v33_active else 0,
        "dashboard_v2_modules_found":1 if dashboard_v2_visible else 0,
        "v2_active_files":len(code_hits),
        "v2_active_files_sample":code_hits[:20],
        "active_cron_v2_refs_found":cron.get("active_v2_cron_count",0),
        "daily_refresh_v2_dependency":refresh.get("daily_refresh_v2_dependency") if refresh else False,
        "cloud_bundle_v2_refs_found":cloud.get("cloud_bundle_v2_active_count",0),
        "capture_ran":False,
        "qq_push":False,
        "cloud_publish":False,
        "cron_enabled":False,
        "strategy_changed":False,
        "v4_candidate_numbers_changed":False,
        "blockers":blockers,
        "warnings":[],
    }
    out=STATUS_DIR/f"v2_decommission_v3_v4_only_check_{DATE}.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if blockers else 0

if __name__=='__main__':
    raise SystemExit(main())
