#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_wc10_war_room_20260602.json"
BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
HTML = ROOT / "data/runtime/dashboard/v3_worldcup_wc10_war_room.html"

BAD_HINTS = {"BET", "STAKE", "BUY", "SELL", "AUTO_BET", "RECOMMENDATION", "LOCKED_PICK"}
ALLOW_HINTS = {"OBSERVE_ONLY", "WATCHLIST_ONLY", "NEED_SUPPLEMENT", "DO_NOT_CONCLUDE", "DATA_GAP_REVIEW"}


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "war_room_json_exists", WAR.exists(), str(WAR))
    add(checks, "dashboard_html_exists", HTML.exists(), str(HTML))
    payload = _load(WAR)
    add(checks, "teams_with_roster_46", int(payload.get("teams_with_roster") or 0) == 46, payload.get("teams_with_roster"))
    add(checks, "teams_total_46", int(payload.get("teams_total") or 0) == 46, payload.get("teams_total"))
    add(checks, "players_total_1375", int(payload.get("players_total") or 0) == 1375, payload.get("players_total"))
    add(checks, "status_ok", payload.get("status") == "WAR_ROOM_READY_WITH_WARN_ONLY", payload.get("status"))
    add(checks, "status_level_ok", payload.get("status_level") == "CODE_READY", payload.get("status_level"))
    add(checks, "blocker_none", payload.get("blocker") == "NONE", payload.get("blocker"))
    warn = payload.get("warn_only_items") or []
    for x in ["CAPS_GOALS_MINUTES_SUPPLEMENT_MISSING", "INJURY_SUPPLEMENT_MISSING", "FRIENDLY_FORM_SUPPLEMENT_MISSING", "MARKET_BASELINE_SUPPLEMENT_MISSING"]:
        add(checks, f"warn_has_{x}", x in warn, warn)
    wl = payload.get("perception_gap_watchlist") or []
    add(checks, "watchlist_count_ge_1", int(payload.get("perception_gap_watchlist_count") or len(wl)) >= 1, payload.get("perception_gap_watchlist_count"))
    guard = payload.get("safety_guard") or {}
    add(checks, "guard_observation_only", guard.get("observation_only") is True, guard)
    add(checks, "guard_no_betting", guard.get("no_betting_recommendations") is True, guard)
    add(checks, "guard_no_v4_changes", guard.get("no_v4_changes") is True, guard)
    add(checks, "supplement_coverage_status_present", bool(payload.get("supplement_coverage_status")), payload.get("supplement_coverage_status"))
    add(checks, "supplement_coverage_by_category_present", isinstance(payload.get("supplement_coverage_by_category"), dict), type(payload.get("supplement_coverage_by_category")).__name__)
    add(checks, "final_squad_status_present", bool(payload.get("final_squad_status")), payload.get("final_squad_status"))
    add(checks, "teams_expected_final_squad_48", int(payload.get("teams_expected_final_squad") or 0) == 48, payload.get("teams_expected_final_squad"))
    add(checks, "teams_detected_in_baseline_46", int(payload.get("teams_detected_in_baseline") or 0) == 46, payload.get("teams_detected_in_baseline"))
    add(checks, "players_total_baseline_1375", int(payload.get("players_total_baseline") or 0) == 1375, payload.get("players_total_baseline"))
    add(checks, "baseline_pool_not_final_26_flag", payload.get("baseline_pool_not_final_26") is True, payload.get("baseline_pool_not_final_26"))
    add(checks, "source_gate_status_present", bool(payload.get("source_authorization_gate_status")), payload.get("source_authorization_gate_status"))
    add(checks, "source_gate_approved_count_present", int(payload.get("source_authorization_approved_sources_count") or 0) >= 0, payload.get("source_authorization_approved_sources_count"))
    add(checks, "source_gate_intake_count_present", int(payload.get("source_authorization_intake_files_found") or 0) >= 0, payload.get("source_authorization_intake_files_found"))
    add(checks, "wc6_dryrun_status_present", bool(payload.get("wc6_ingestion_dryrun_status")), payload.get("wc6_ingestion_dryrun_status"))
    add(checks, "wc6_official_not_written", payload.get("wc6_ingestion_dryrun_official_written") is False, payload.get("wc6_ingestion_dryrun_official_written"))
    add(checks, "candidate_review_status_present", bool(payload.get("candidate_review_status")), payload.get("candidate_review_status"))
    csum = payload.get("candidate_review_summary") if isinstance(payload.get("candidate_review_summary"), dict) else {}
    cc = payload.get("candidate_review_counts") if isinstance(payload.get("candidate_review_counts"), dict) else {}
    add(checks, "candidate_review_only", csum.get("source_status") in {"CANDIDATE_REVIEW_ONLY", "WC5D_MISSING_WARN_ONLY"}, csum.get("source_status"))
    add(checks, "candidate_review_not_official", csum.get("official_final_squad_written") is False and csum.get("final_squad_complete") is False, csum)
    add(checks, "candidate_safe_29", int(csum.get("teams_safe") or 0) in {0, 29}, csum.get("teams_safe"))
    add(checks, "candidate_hold_19", int(csum.get("teams_hold") or 0) in {48, 19}, csum.get("teams_hold"))
    add(checks, "candidate_counts_expected", all([
        int(cc.get("OFFICIAL_CONFIRMED") or 0) in {0, 1},
        int(cc.get("API_CLEAN_CANDIDATE") or 0) in {0, 25},
        int(cc.get("API_WIKI_ALIGNED_CANDIDATE") or 0) in {0, 3},
        int(cc.get("WIKI_PREFERRED_API_POOL_OVERFULL") or 0) in {0, 15},
        int(cc.get("API_INCOMPLETE_NEED_REVIEW") or 0) in {0, 3},
        int(cc.get("PROVISIONAL_OVERFULL_NEED_REVIEW") or 0) in {0, 1},
    ]), cc)
    hints = [str(x.get("action_hint") or "") for x in wl if isinstance(x, dict)]
    add(checks, "action_hint_whitelist", all(h in ALLOW_HINTS for h in hints), hints[:12])
    add(checks, "action_hint_no_bad", all(h not in BAD_HINTS for h in hints), hints[:12])
    text = (json.dumps(payload, ensure_ascii=False) + "\n" + (HTML.read_text(encoding="utf-8", errors="ignore") if HTML.exists() else "")).lower()
    sanitized = (
        text.replace("no betting recommendation", "")
        .replace("no betting recommendations", "")
        .replace("not a betting recommendation", "")
        .replace("不输出投注建议", "")
        .replace("任何 watchlist 都不是推荐下注", "")
        .replace("no_stake", "")
    )
    banned = ["bet ready", "recommendation_ready", "auto_trade_ready", "wager", "推荐下注", "投注建议", "auto bet", "locked pick"]
    add(checks, "no_betting_terms", all(x not in sanitized for x in banned), banned)
    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_v4_scan", "scan_and_brief" not in src and "fullscan" not in src)
    add(
        checks,
        "no_qq_pending_validation_livebet_cron",
        all(x not in src for x in ["send_qq(", "pending_route(", "recompute_validation(", "append_live_bet(", "crontab"]),
    )
    add(checks, "no_touch_outside57_scanner", "v4_outside57_scanner.py" not in src)
    add(checks, "no_secrets", all(x not in src for x in ["api-key", "token=", "secret"]), "source_scan")

    blockers = [c["name"] for c in checks if not c["ok"]]
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
