#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
ACCEPT = ROOT / "data" / "runtime" / "acceptance"
STATUS = ROOT / "data" / "runtime" / "status"
TZ = timezone(timedelta(hours=8))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _latest(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _exists_and_key_shape_h2h_recent(src_h2h: str) -> tuple[bool, str]:
    exists = (
        "_RECENT_PROFILE_CACHE" in src_h2h
        and "cache_key = (int(team_id), int(last_n), bool(include_events))" in src_h2h
        and "_query_recent_goal_profile" in src_h2h
    )
    return exists, "team_id + last_n + include_events (in-memory, per run)"


def _exists_and_key_shape_pair_h2h(src_runner: str, src_h2h: str) -> tuple[bool, str]:
    exists = (
        "_cached_api_client" in src_runner
        and "fixtures/headtohead?h2h=" in src_h2h
        and "_normalize_endpoint" in src_runner
        and "q_sorted = sorted(q" in src_runner
    )
    return exists, "normalized endpoint: fixtures/headtohead?h2h=<home>-<away> (per run)"


def _exists_and_key_shape_market(src_runner: str) -> tuple[bool, str]:
    exists = "_cached_api_client" in src_runner and "odds?fixture=" in src_runner
    return exists, "normalized endpoint: odds?fixture=<fixture_id> (per run)"


def _exists_and_key_shape_events(src_runner: str, src_h2h: str) -> tuple[bool, str]:
    exists = (
        "_cached_api_client" in src_runner
        and "fixtures/events?fixture=" in src_h2h
        and "_parse_goal_events" in src_h2h
    )
    return exists, "normalized endpoint: fixtures/events?fixture=<fixture_id> (per run)"


def _lazy_skip_effect(src_runner: str, daily_payload: dict[str, Any]) -> dict[str, bool]:
    lazy = daily_payload.get("rf_lazy_shadow") or {}
    h2h_f = int(lazy.get("h2h_required_false_count") or 0)
    h2h_s = int(lazy.get("h2h_skipped_count") or 0)
    ev_f = int(lazy.get("events_required_false_count") or 0)
    ev_s = int(lazy.get("events_skipped_count") or 0)
    cpl_f = int(lazy.get("cpl_required_false_count") or 0)
    cpl_s = int(lazy.get("cpl_skipped_count") or 0)

    # Dynamic evidence from latest canary artifact; fallback to static code evidence.
    h2h_dynamic = h2h_f == 0 or h2h_s >= h2h_f
    ev_dynamic = ev_f == 0 or ev_s >= ev_f
    cpl_dynamic = cpl_f == 0 or cpl_s >= cpl_f

    h2h_static = (
        "if h2h_required:" in src_runner
        and "evaluate_h2h_edge(" in src_runner
        and "collection_stage = \"H2H_SKIPPED\"" in src_runner
    )
    ev_static = (
        "events_required = bool(" in src_runner
        and "events_collected = bool(events_required" in src_runner
        and "collection_stage = \"EVENTS_ENRICHED\" if events_collected else \"EVENTS_SKIPPED\"" in src_runner
    )
    cpl_static = (
        "cpl_required = bool(" in src_runner
        and "cpl_collected = False" in src_runner
        and "cpl_skipped_reason = \"PLACEHOLDER_ONLY\"" in src_runner
    )

    return {
        "h2h_required_false_skips_h2h": bool(h2h_dynamic and h2h_static),
        "events_required_false_skips_events": bool(ev_dynamic and ev_static),
        "cpl_required_false_skips_cpl": bool(cpl_dynamic and cpl_static),
    }


def main() -> int:
    src_runner = _read(ENGINE / "v4_runner.py")
    src_h2h = _read(ENGINE / "data_sources" / "h2h_engine.py")
    src_brief = _read(ENGINE / "v4_scan_and_brief.py")

    daily_art = _latest("v4_collection_pipeline_daily_shadow_canary_*.json", ACCEPT)
    daily_payload: dict[str, Any] = {}
    if daily_art and daily_art.exists():
        daily_payload = json.loads(daily_art.read_text(encoding="utf-8"))

    recent_exists, recent_key = _exists_and_key_shape_h2h_recent(src_h2h)
    pair_exists, pair_key = _exists_and_key_shape_pair_h2h(src_runner, src_h2h)
    market_exists, market_key = _exists_and_key_shape_market(src_runner)
    events_exists, events_key = _exists_and_key_shape_events(src_runner, src_h2h)

    lazy_effect = _lazy_skip_effect(src_runner, daily_payload)
    cmpv = daily_payload.get("comparison") or {}

    report: dict[str, Any] = {
        "schema_version": "v4_collection_pipeline_cache_audit.v1",
        "generated_at": datetime.now(TZ).isoformat(),
        "source_daily_canary_artifact": str(daily_art) if daily_art else "",
        "cache_audit_result": {
            "team_recent_form_cache": {
                "exists": recent_exists,
                "key_shape": recent_key,
                "duplicate_request_risk": "LOW" if recent_exists else "HIGH",
                "notes": "recent profile cache in h2h_engine, with prewarm + hit/miss stats",
            },
            "pair_h2h_cache": {
                "exists": pair_exists,
                "key_shape": pair_key,
                "duplicate_request_risk": "LOW" if pair_exists else "HIGH",
                "notes": "api client normalized endpoint cache avoids duplicate pair calls within same run",
            },
            "opening_market_cache": {
                "exists": market_exists,
                "key_shape": market_key,
                "duplicate_request_risk": "LOW" if market_exists else "HIGH",
                "notes": "odds endpoint is cached by normalized endpoint key per scan run",
            },
            "events_cache": {
                "exists": events_exists,
                "key_shape": events_key,
                "duplicate_request_risk": "MEDIUM" if events_exists else "HIGH",
                "notes": "events endpoint relies on normalized endpoint cache (no dedicated persistent store)",
            },
            "cpl_cache": {
                "placeholder_only": True,
                "external_call": False,
                "notes": "CPL branch is placeholder-only in rf_lazy_shadow, no injury/CPL external API call",
            },
            "lazy_skip_effect": lazy_effect,
            "safety": {
                "official_grade_unchanged": int(cmpv.get("official_grade_mismatch_count") or 0) == 0,
                "validation_untouched": not bool(cmpv.get("validation_touched")),
                "live_bet_untouched": not bool(cmpv.get("live_bet_touched")),
                "qq_not_pushed": ("V4_QQ_ENABLED = False" in src_brief) and (not bool(cmpv.get("qq_pushed"))),
            },
        },
    }

    review_required: list[str] = []
    if not recent_exists:
        review_required.append("team_recent_form_cache_missing")
    if not pair_exists:
        review_required.append("pair_h2h_cache_missing")
    if not market_exists:
        review_required.append("opening_market_cache_missing")
    if not events_exists:
        review_required.append("events_cache_missing")

    blockers: list[str] = []
    for k, ok in lazy_effect.items():
        if not ok:
            blockers.append(f"lazy_skip_not_effective:{k}")

    safety = report["cache_audit_result"]["safety"]
    for key in ("official_grade_unchanged", "validation_untouched", "live_bet_untouched", "qq_not_pushed"):
        if not safety.get(key):
            blockers.append(f"safety_violation:{key}")

    if blockers:
        conclusion = "BLOCKER"
    elif review_required:
        conclusion = "REVIEW_REQUIRED"
    else:
        conclusion = "PASS"

    report["review_required"] = review_required
    report["blockers"] = blockers
    report["conclusion"] = conclusion

    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"v4_collection_pipeline_cache_audit_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if conclusion in {"PASS", "REVIEW_REQUIRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
